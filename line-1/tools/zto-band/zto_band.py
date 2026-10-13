#!/usr/bin/env python3
"""Read-only, standard-library ZTO/IMD Uniswap v4 interval calculator."""

import argparse
import datetime
import json
import ipaddress
from pathlib import Path
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

from keccak import keccak256, selector
from math_core import Q96, capacity, interior_target, sqrt_at_tick, swap_step, total_fee

MANAGER = '0x000000000004444c5dc75cb358380d2e3de08a90'
STATE_VIEW = '0x7ffe42c4a5deea5b0fec41c94c136cf115597227'
IMD = '0xd34a99bc0f67ae1bbd63c660e6d0b0dd03e263b7'
ZTO = '0xd782bdea4ef02a0bd391eb9089470c8080f0a68e'
POOL = '0x888b07bd282f587d3c6b0fcb23e7fc55bbb33abe8910dd7492db815dc8dc5592'
INIT_BLOCK = 26129224
PUBLIC_RPC = 'https://ethereum-rpc.publicnode.com'
INIT_TOPIC = '0x' + keccak256(b'Initialize(bytes32,address,address,uint24,int24,address,uint160,int24)').hex()
SCHEMA = 'zto-band-observation-v1'


def require(ok, message):
    if not ok:
        raise ValueError(message)


def word(n):
    return (n % (1 << 256)).to_bytes(32, 'big')


def words(data, count):
    require(isinstance(data, str) and re.fullmatch(r'0x[0-9a-fA-F]*', data) is not None,
            'invalid ABI hex')
    require(len(data) == 2 + count * 64, 'unexpected ABI return length')
    return [int(data[2+i*64:2+(i+1)*64], 16) for i in range(count)]


def uint(n, bits, label):
    require(type(n) is int and 0 <= n < (1 << bits), 'invalid ' + label)
    return n


def signed(n, bits):
    value = n if n < 1 << 255 else n - (1 << 256)
    require(-(1 << (bits-1)) <= value < 1 << (bits-1), 'noncanonical signed ABI word')
    return value


def address_word(data):
    return '0x' + uint(words(data, 1)[0], 160, 'address').to_bytes(20, 'big').hex()


def workspace_file(value):
    path = Path(value).resolve()
    require(path.is_relative_to(Path.cwd().resolve()), 'file must be inside the current workspace')
    return path


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError('RPC redirects are not accepted')


def validate_endpoint(endpoint):
    """HTTPS, or an explicitly supplied literal loopback HTTP relay. No discovery."""
    require(isinstance(endpoint, str) and endpoint and
            not any(c.isspace() or ord(c) < 32 or ord(c) == 127 for c in endpoint),
            'invalid RPC URL')
    parsed = urllib.parse.urlsplit(endpoint)
    require(parsed.username is None and parsed.password is None, 'credential URLs are not accepted')
    require(bool(parsed.hostname) and not parsed.query and not parsed.fragment and
            '?' not in endpoint and '#' not in endpoint and '\\' not in endpoint,
            'invalid RPC URL')
    port = parsed.port  # Also validates malformed/out-of-range ports.
    require(port is None or 1 <= port <= 65535, 'invalid RPC port')
    try:
        loopback = ipaddress.ip_address(parsed.hostname).is_loopback
    except ValueError:
        loopback = False
    require(parsed.scheme == 'https' or
            (parsed.scheme == 'http' and loopback and port is not None),
            'use HTTPS or an explicit literal loopback HTTP relay with a port')
    return parsed


class RPC:
    """Only public reads; no wallet, environment, proxy, signing or send methods."""
    METHODS = {'eth_chainId', 'eth_getBlockByNumber', 'eth_getLogs', 'eth_call'}

    def __init__(self, endpoint):
        validate_endpoint(endpoint)
        self.endpoint = endpoint
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
        self.counter = 0

    def call(self, method, params):
        require(method in self.METHODS, 'RPC method is not read-only allowlisted')
        self.counter += 1
        body = {'jsonrpc': '2.0', 'id': self.counter, 'method': method, 'params': params}
        req = urllib.request.Request(self.endpoint, data=json.dumps(body).encode(), headers={
            'Content-Type': 'application/json', 'User-Agent': 'Pepeolithic-ZtoBand/1.0'})
        with self.opener.open(req, timeout=30) as response:
            payload = response.read(2_000_001)
        require(len(payload) <= 2_000_000, 'RPC response exceeds size bound')
        result = json.loads(payload)
        require(isinstance(result, dict) and result.get('id') == self.counter
                and result.get('jsonrpc') == '2.0', 'RPC response envelope mismatch')
        if 'error' in result:
            raise ValueError('RPC error: ' + json.dumps(result['error']))
        require('result' in result, 'missing RPC result')
        return result['result']


def capture(endpoint, block_tag):
    rpc = RPC(endpoint)
    chain_id = rpc.call('eth_chainId', [])
    require(chain_id == '0x1', 'expected Ethereum chain 1')
    block = rpc.call('eth_getBlockByNumber', [block_tag, False])
    require(isinstance(block, dict), 'block unavailable')
    block = {k: block[k] for k in ('number', 'hash', 'timestamp')}
    require(int(block['number'], 16) >= INIT_BLOCK, 'block predates ZTO pool')
    pin = {'blockHash': block['hash'], 'requireCanonical': True}
    init_header = rpc.call('eth_getBlockByNumber', [hex(INIT_BLOCK), False])
    logs = rpc.call('eth_getLogs', [{'address': MANAGER, 'blockHash': init_header['hash'],
                                   'topics': [INIT_TOPIC, POOL]}])
    require(isinstance(logs, list) and len(logs) == 1, 'expected one canonical pool Initialize event')
    require(logs[0]['blockHash'] == init_header['hash'], 'Initialize block hash mismatch')

    def call(to, signature, arg=''):
        return rpc.call('eth_call', [{'to': to, 'data': selector(signature) + arg}, pin])

    observation = {
        'schema': SCHEMA, 'source': endpoint,
        'chain_id': chain_id, 'block': block,
        'initialize': logs[0],
        'raw': {
            'state_view_manager': call(STATE_VIEW, 'poolManager()'),
            'slot0': call(STATE_VIEW, 'getSlot0(bytes32)', POOL[2:]),
            'liquidity': call(STATE_VIEW, 'getLiquidity(bytes32)', POOL[2:]),
            'imd_decimals': call(IMD, 'decimals()'),
            'zto_decimals': call(ZTO, 'decimals()'),
        },
    }
    end = rpc.call('eth_getBlockByNumber', [block['number'], False])
    require(end and end['hash'] == block['hash'], 'block changed during capture; retry')
    decode(observation)
    return observation


def decode(observation):
    require(isinstance(observation, dict), 'observation must be an object')
    require(observation['schema'] == SCHEMA and observation['chain_id'] == '0x1',
            'wrong observation schema or chain')
    block = observation['block']
    require(isinstance(block, dict), 'block must be an object')
    require(re.fullmatch(r'0x[0-9a-fA-F]{64}', block['hash']) is not None, 'invalid block hash')
    require(int(block['number'], 16) >= INIT_BLOCK, 'block predates pool')
    require(int(block['timestamp'], 16) > 0, 'invalid block timestamp')
    init = observation['initialize']
    require(isinstance(init, dict), 'initialize must be an object')
    require(init['address'].lower() == MANAGER and init.get('removed') is False,
            'wrong manager or removed initialization')
    require(int(init['blockNumber'], 16) == INIT_BLOCK, 'unexpected initialization block')
    require(init['topics'] == [INIT_TOPIC, POOL, '0x' + word(int(IMD, 16)).hex(),
                              '0x' + word(int(ZTO, 16)).hex()], 'wrong pool or currency order')
    fee, spacing, hook, initial_price, initial_tick_word = words(init['data'], 5)
    require(fee == 12500 and spacing == 60, 'unexpected pool fee or spacing')
    uint(hook, 160, 'hook address')
    uint(initial_price, 160, 'initial sqrt price')
    initial_tick = signed(initial_tick_word, 24)
    require(sqrt_at_tick(initial_tick) <= initial_price < sqrt_at_tick(initial_tick+1),
            'invalid initialization price/tick')
    key = b''.join(word(v) for v in (int(IMD, 16), int(ZTO, 16), fee, spacing, hook))
    require('0x' + keccak256(key).hex() == POOL, 'PoolKey hash does not match assigned pool')
    # beforeSwap, afterSwap and both swap-return-delta permissions.
    require(hook & ((1 << 7) | (1 << 6) | (1 << 3) | (1 << 2)) == 0,
            'swap hooks are unsupported; no core-only estimate can be issued')
    raw = observation['raw']
    require(isinstance(raw, dict), 'raw must be an object')
    require(address_word(raw['state_view_manager']) == MANAGER, 'StateView manager mismatch')
    price, tick_word, protocol, lp = words(raw['slot0'], 4)
    tick = signed(tick_word, 24)
    require(-887272 <= tick < 887272, 'tick out of range')
    uint(price, 160, 'sqrt price')
    require(sqrt_at_tick(tick) <= price <= sqrt_at_tick(tick+1), 'inconsistent price/tick')
    uint(protocol, 24, 'protocol fee')
    require(lp == fee, 'unexpected LP fee')
    require((protocol & 4095) <= 1000 and protocol >> 12 <= 1000, 'invalid protocol fee')
    liquidity = uint(words(raw['liquidity'], 1)[0], 128, 'liquidity')
    decimals = [uint(words(raw[k], 1)[0], 8, k) for k in ('imd_decimals', 'zto_decimals')]
    require(all(d <= 36 for d in decimals), 'decimals greater than 36 are unsupported')
    return {'price': price, 'tick': tick, 'liquidity': liquidity, 'protocol': protocol,
            'lp': lp, 'spacing': spacing, 'decimals': decimals, 'hook': '0x' + hook.to_bytes(20, 'big').hex()}


def units(raw, decimals):
    if decimals == 0:
        return str(raw)
    q, r = divmod(raw, 10 ** decimals)
    return (str(q) + '.' + str(r).zfill(decimals)).rstrip('0').rstrip('.')


def parse_amount(text, decimals):
    require(len(text) <= 120 and re.fullmatch(r'[0-9]+(?:\.[0-9]+)?', text) is not None,
            'amount must be a nonnegative plain decimal')
    whole, _, fraction = text.partition('.')
    require(len(fraction) <= decimals, 'amount has more precision than the token')
    n = int(whole) * 10 ** decimals + int(fraction.ljust(decimals, '0') or '0')
    require(0 < n < (1 << 255), 'amount must be positive and fit int256')
    return n


def ratio_text(n, d):
    return units(n * 10**24 // d, 24)


def report(observation, input_token='ZTO', amount=None):
    state = decode(observation)
    require(input_token in ('ZTO', 'IMD'), 'input token must be ZTO or IMD')
    zero_for_one = input_token == 'IMD'
    din, dout = state['decimals'] if zero_for_one else state['decimals'][::-1]
    target, edge = interior_target(state['tick'], state['spacing'], zero_for_one)
    fee = total_fee(state['protocol'], state['lp'], zero_for_one)
    cap = capacity(state['price'], target, state['liquidity'], fee, zero_for_one)
    gross = cap if amount is None else parse_amount(amount, din)
    price = state['price']
    out = {
        'schema': 'zto-band-report-v1', 'pool_id': POOL, 'chain_id': 1,
        'block_number': int(observation['block']['number'], 16),
        'block_hash': observation['block']['hash'],
        'block_time_utc': datetime.datetime.fromtimestamp(int(observation['block']['timestamp'], 16),
                                                         datetime.timezone.utc).isoformat(),
        'input_token': input_token, 'output_token': 'ZTO' if zero_for_one else 'IMD',
        'pool_tick': state['tick'], 'active_liquidity_raw': str(state['liquidity']),
        'hook': state['hook'], 'swap_hook_permissions': False, 'fee_pips': fee,
        'boundary_tick': edge, 'sqrt_price_limit_x96': str(target),
        'spot_imd_per_zto': ratio_text(Q96**2 * 10**state['decimals'][1],
                                       price**2 * 10**state['decimals'][0]),
        'interval_input_cap_raw': str(cap), 'interval_input_cap': units(cap, din),
        'requested_input_raw': str(gross), 'requested_input': units(gross, din),
        'scope': 'Core pool estimate inside one tick-spacing interval; not an executable quote.',
        'limitations': ['No initialized tick is crossed; larger trades are refused.',
                        'No token transfer behavior, router, gas, slippage tolerance or MEV simulation.',
                        'Observation is RPC data, not a cryptographic state proof or a freshness guarantee.'],
    }
    if cap == 0:
        out['status'] = 'no_interval_capacity'
    elif gross > cap:
        out['status'] = 'outside_interval'
    else:
        out['status'] = 'estimated'
        quote = swap_step(price, target, state['liquidity'], fee, gross, zero_for_one)
        quote['output'] = units(int(quote['output_raw']), dout)
        quote['fee'] = units(int(quote['fee_raw']), din)
        after = int(quote['sqrt_price_after_x96'])
        quote['spot_movement_bps'] = ratio_text(abs(after**2 - price**2) * 10000, price**2)
        out['estimate'] = quote
    return out


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    source = p.add_mutually_exclusive_group(required=True)
    source.add_argument('--snapshot', help='workspace observation JSON; no network')
    source.add_argument('--live', action='store_true', help='read Ethereum via RPC')
    p.add_argument('--rpc', default=PUBLIC_RPC)
    p.add_argument('--block', default='finalized', help='finalized (default), safe, latest, or decimal number')
    p.add_argument('--save', help='save raw observation to a workspace JSON file (live only)')
    p.add_argument('--input', choices=('ZTO', 'IMD'), default='ZTO')
    p.add_argument('--amount', help='human token units; omit to estimate the interval input cap')
    args = p.parse_args(argv)
    try:
        if args.snapshot:
            require(args.save is None, '--save requires --live')
            with workspace_file(args.snapshot).open('rb') as handle:
                data = handle.read(100_001)
            require(len(data) <= 100_000, 'snapshot exceeds 100 KB')
            observation = json.loads(data)
        else:
            tag = args.block if args.block in ('finalized', 'safe', 'latest') else hex(int(args.block))
            observation = capture(args.rpc, tag)
        result = report(observation, args.input, args.amount)
        if args.save:
            encoded = json.dumps(observation, indent=2) + '\n'
            require(len(encoded.encode()) <= 100_000, 'snapshot exceeds 100 KB')
            workspace_file(args.save).write_text(encoded)
        print(json.dumps(result, indent=2))
        return 0 if result['status'] == 'estimated' else 2
    except (ValueError, KeyError, TypeError, AttributeError, OSError, OverflowError) as exc:
        print(json.dumps({'error': str(exc)}), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
