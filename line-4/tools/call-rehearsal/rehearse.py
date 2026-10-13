#!/usr/bin/env python3
"""Read-only contract call rehearsal. Python standard library; no wallet access."""
import argparse
import json
from pathlib import Path
import re
import sys
import urllib.request

TOKENS = {'ZTO': '0xd782bdea4ef02a0bd391eb9089470c8080f0a68e',
          'IMD': '0xd34a99bc0f67ae1bbd63c660e6d0b0dd03e263b7'}
ENDPOINTS = ('https://ethereum-rpc.publicnode.com', 'https://eth.drpc.org')
SCHEMA = 'call-rehearsal-v1'
LIMIT = 90_000


def require(ok, message):
    if not ok:
        raise ValueError(message)


def address(value):
    require(isinstance(value, str) and re.fullmatch(r'0x[0-9a-fA-F]{40}', value),
            'address must contain exactly 20 bytes')
    require(int(value, 16) != 0, 'zero address is not accepted')
    return value.lower()


def data(value, size=None):
    require(isinstance(value, str) and re.fullmatch(r'0x(?:[0-9a-fA-F]{2})*', value),
            'data must be even-length hexadecimal with 0x prefix')
    require(len(value) <= 65538, 'data exceeds 32 KiB')
    require(size is None or len(value) == 2 + size * 2, 'unexpected data length')
    return value.lower()


def quantity(value):
    require(isinstance(value, str) and re.fullmatch(r'0x(?:0|[1-9a-fA-F][0-9a-fA-F]*)', value),
            'invalid RPC quantity')
    result = int(value, 16)
    require(result < 2**256, 'quantity exceeds uint256')
    return result


def amount(value):
    require(isinstance(value, str) and re.fullmatch(r'0|[1-9][0-9]*', value),
            'amount must be an unsigned decimal integer in base units')
    require(len(value) <= 78 and int(value) < 2**256, 'amount exceeds uint256')
    return int(value)


def transaction(value):
    require(isinstance(value, dict) and set(value) <= {'to', 'from', 'data', 'value'}
            and {'to', 'data', 'value'} <= set(value), 'invalid call fields')
    tx = {'to': address(value['to']), 'data': data(value['data']),
          'value': hex(quantity(value['value']))}
    if 'from' in value:
        tx['from'] = address(value['from'])
    else:
        require(tx['data'] == '0x18160ddd' and tx['value'] == '0x0'
                and tx['to'] in TOKENS.values(), 'custom calls require an explicit sender')
    return tx


def transfer(token, sender, recipient, units):
    return transaction({'to': TOKENS[token], 'from': address(sender), 'value': '0x0',
                        'data': '0xa9059cbb' + address(recipient)[2:].rjust(64, '0')
                        + format(amount(units), '064x')})


def header(value):
    require(isinstance(value, dict), 'missing block header')
    return {'number': hex(quantity(value['number'])), 'hash': data(value['hash'], 32),
            'timestamp': hex(quantity(value['timestamp']))}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError('redirects are not accepted')


class RPCError(Exception):
    def __init__(self, error):
        require(isinstance(error, dict) and type(error.get('code')) is int
                and isinstance(error.get('message'), str), 'malformed RPC error')
        self.error = error
        super().__init__(error['message'])


class RPC:
    METHODS = {'eth_chainId', 'eth_getBlockByNumber', 'eth_getCode', 'eth_call'}

    def __init__(self, endpoint, relay=None):
        require(endpoint in ENDPOINTS, 'unsupported public RPC')
        if relay is not None:
            match = re.fullmatch(r'http://127\.0\.0\.1:([1-9][0-9]{0,4})/rpc/1', relay)
            require(match is not None and int(match[1]) <= 65535,
                    'relay must be http://127.0.0.1:<port>/rpc/1')
        self.endpoint = endpoint
        self.transport = relay if relay is not None else endpoint
        self.via_relay = relay is not None
        self.counter = 0
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())

    def call(self, method, params):
        require(method in self.METHODS, 'RPC method is not read-only allowlisted')
        self.counter += 1
        request = urllib.request.Request(self.transport, data=json.dumps({
            'jsonrpc': '2.0', 'id': self.counter, 'method': method, 'params': params}).encode(),
            headers={'Content-Type': 'application/json', 'User-Agent': 'Pepeolithic-CallRehearsal/1.0'})
        with self.opener.open(request, timeout=25) as response:
            raw = response.read(LIMIT + 1)
        require(len(raw) <= LIMIT, 'RPC response exceeds byte limit')
        result = json.loads(raw)
        require(isinstance(result, dict) and result.get('jsonrpc') == '2.0'
                and type(result.get('id')) is int and result['id'] == self.counter,
                'RPC response envelope mismatch')
        require(('result' in result) != ('error' in result), 'ambiguous RPC response')
        if 'error' in result:
            raise RPCError(result['error'])
        return result['result']


def decode_revert(raw):
    raw = data(raw)
    body = bytes.fromhex(raw[10:])
    if raw.startswith('0x08c379a0') and len(body) >= 64:
        offset, length = int.from_bytes(body[:32], 'big'), int.from_bytes(body[32:64], 'big')
        if offset == 32 and length <= len(body) - 64:
            return {'kind': 'Error(string)', 'reason': body[64:64+length].decode('utf-8', 'replace')}
    if raw.startswith('0x4e487b71') and len(body) == 32:
        return {'kind': 'Panic(uint256)', 'code': hex(int.from_bytes(body, 'big'))}
    return {'kind': 'custom_or_unknown' if len(raw) >= 10 else 'empty_or_truncated',
            'selector': raw[:10], 'raw': raw}


def interpret(outcome, returns):
    require(returns in ('raw', 'uint256', 'bool'), 'unsupported return interpretation')
    require(isinstance(outcome, dict) and len(outcome) == 1, 'invalid outcome')
    if 'error' in outcome:
        error = RPCError(outcome['error']).error
        reverted = error['code'] == 3 or 'execution reverted' in error['message'].lower()
        result = {'status': 'reverted' if reverted else 'inconclusive', 'rpc_error': error}
        raw = error.get('data')
        if isinstance(raw, str) and re.fullmatch(r'0x(?:[0-9a-fA-F]{2})*', raw):
            result['revert'] = decode_revert(raw)
        return result
    require('result' in outcome, 'missing outcome result')
    raw = data(outcome['result'])
    result = {'status': 'returned', 'raw': raw}
    if returns != 'raw':
        if len(raw) != 66:
            result.update(status='unexpected_return', expected=returns)
        else:
            number = int(raw, 16)
            if returns == 'uint256':
                result['uint256'] = str(number)
            elif number not in (0, 1):
                result.update(status='unexpected_return', expected='canonical ABI bool')
            else:
                result.update(status='returned_true' if number else 'returned_false', boolean=bool(number))
    return result


def capture(rpc, tx, returns):
    tx = transaction(tx)
    require(returns in ('raw', 'uint256', 'bool'), 'unsupported return interpretation')
    require(rpc.call('eth_chainId', []) == '0x1', 'expected Ethereum mainnet')
    block = header(rpc.call('eth_getBlockByNumber', ['finalized', False]))
    pin = {'blockHash': block['hash'], 'requireCanonical': True}
    code = data(rpc.call('eth_getCode', [tx['to'], pin]))
    require(code != '0x', 'target has no code; refusing to treat an empty EOA call as success')
    try:
        outcome = {'result': data(rpc.call('eth_call', [tx, pin]))}
    except RPCError as exc:
        outcome = {'error': exc.error}
    after = header(rpc.call('eth_getBlockByNumber', [block['number'], False]))
    require(after == block, 'block changed during rehearsal; discard and retry')
    observation = {'schema': SCHEMA, 'source': rpc.endpoint, 'chain_id': 1, 'block': block,
                   'call': tx, 'returns': returns, 'code_present': True, 'outcome': outcome}
    if getattr(rpc, 'via_relay', False):
        observation['transport'] = {'kind': 'contributor-relay',
                                    'source_is_attribution_only': True,
                                    'independent_provider_verified': False}
    report(observation)
    return observation


def report(observation):
    require(isinstance(observation, dict) and observation.get('schema') == SCHEMA,
            'unsupported observation schema')
    require(type(observation['chain_id']) is int and observation['chain_id'] == 1, 'wrong chain')
    require(observation['source'] in ENDPOINTS, 'unknown source')
    require(observation['code_present'] is True, 'target code was not confirmed')
    tx, block = transaction(observation['call']), header(observation['block'])
    result = interpret(observation['outcome'], observation['returns'])
    result_report = {'chain_id': 1, 'block_number': quantity(block['number']), 'block_hash': block['hash'],
            'call': tx, 'result': result,
            'limits': 'Provider-reported simulation at a finalized historical state; no transaction sent. '
                      'No gas estimate, receipt, state diff, authenticity proof or guarantee of future execution.'}
    if 'transport' in observation:
        require(observation['transport'] == {
            'kind': 'contributor-relay', 'source_is_attribution_only': True,
            'independent_provider_verified': False}, 'invalid relay provenance')
        # Equality alone accepts integers as booleans in Python.
        require(type(observation['transport']['source_is_attribution_only']) is bool
                and type(observation['transport']['independent_provider_verified']) is bool,
                'invalid relay provenance flags')
        result_report['transport'] = observation['transport']
        result_report['limits'] += (' Contributor relay used; source is public attribution only. '
                                    'Upstream provider identity and independence are not verified.')
    return result_report


def workspace_path(value):
    path = Path(value).resolve()
    require(path.is_relative_to(Path.cwd().resolve()), 'file must stay within the workspace')
    return path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='mode', required=True)
    for name in ('demo', 'call', 'transfer'):
        cmd = sub.add_parser(name)
        cmd.add_argument('--rpc', choices=ENDPOINTS, default=ENDPOINTS[0])
        cmd.add_argument('--relay', help='explicit contributor loopback transport: http://127.0.0.1:<port>/rpc/1; --rpc supplies public attribution')
        cmd.add_argument('--save', help='write a bounded observation inside the workspace')
        if name in ('demo', 'transfer'):
            cmd.add_argument('--token', choices=TOKENS, default='ZTO')
        if name == 'call':
            cmd.add_argument('--to', required=True)
            cmd.add_argument('--sender', required=True)
            cmd.add_argument('--data', required=True)
            cmd.add_argument('--value', default='0', help='native ETH value in wei')
            cmd.add_argument('--returns', choices=('raw', 'uint256', 'bool'), default='raw')
        if name == 'transfer':
            cmd.add_argument('--sender', required=True)
            cmd.add_argument('--recipient', required=True)
            cmd.add_argument('--amount', required=True, help='token base units, decimal integer')
    replay = sub.add_parser('replay')
    replay.add_argument('observation')
    args = parser.parse_args(argv)
    try:
        if args.mode == 'replay':
            with workspace_path(args.observation).open('rb') as handle:
                raw = handle.read(LIMIT + 1)
            require(len(raw) <= LIMIT, 'observation exceeds byte limit')
            observation = json.loads(raw)
        else:
            if args.mode == 'demo':
                tx = {'to': TOKENS[args.token], 'data': '0x18160ddd', 'value': '0x0'}
                returns = 'uint256'
            elif args.mode == 'transfer':
                tx = transfer(args.token, args.sender, args.recipient, args.amount)
                returns = 'bool'
            else:
                tx = {'to': args.to, 'from': args.sender, 'data': args.data,
                      'value': hex(amount(args.value))}
                returns = args.returns
            # Validate before any network request.
            tx = transaction(tx)
            destination = workspace_path(args.save) if args.save else None
            observation = capture(RPC(args.rpc, relay=args.relay), tx, returns)
            if destination:
                encoded = json.dumps(observation, indent=2) + '\n'
                require(len(encoded.encode()) <= LIMIT, 'observation exceeds byte limit')
                # Exclusive creation prevents accidental replacement of an earlier observation.
                with destination.open('x', encoding='utf-8') as handle:
                    handle.write(encoded)
        result = report(observation)
        print(json.dumps(result, indent=2))
        status = result['result']['status']
        return 0 if status in ('returned', 'returned_true') else (1 if status in ('reverted', 'returned_false') else 2)
    except (ValueError, KeyError, TypeError, OSError, RPCError) as exc:
        print(json.dumps({'error': str(exc)}), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
