#!/usr/bin/env python3
"""Refresh and quoter-check a ZTO/IMD path through an explicit read-only route."""
import argparse
import contextlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sys
import threading

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'zto-path'))
import zto_path as path

HERE = Path(__file__).resolve().parent
SNAPSHOT = HERE.parent / 'zto-path' / 'observation.json'
EVIDENCE = HERE.parent / 'zto-path' / 'quoter-check.json'
MANAGER_EVIDENCE = HERE / 'demo-manager.json'


def replay_table(observation, evidence, manager_evidence=None):
    """Raw archived replies for exact requests; saved verdicts are never used."""
    state, _, _ = path.decode(observation)
    base = observation['base']
    path.z.require(evidence['block'] == base['block'] and evidence['quoter'] == path.QUOTER,
                   'quoter evidence must match the snapshot block and contract')
    pin = {'blockHash': base['block']['hash'], 'requireCanonical': True}
    table = {}

    def put(method, params, result):
        key = json.dumps([method, params], sort_keys=True)
        path.z.require(key not in table or table[key] == result, 'conflicting archived response')
        table[key] = result

    def call(to, signature, argument, result):
        put('eth_call', [{'to': to, 'data': path.selector(signature) + argument}, pin], result)

    put('eth_chainId', [], base['chain_id'])
    put('eth_getBlockByNumber', [base['block']['number'], False], base['block'])
    put('eth_getBlockByNumber', [hex(path.z.INIT_BLOCK), False],
        {'hash': base['initialize']['blockHash']})
    put('eth_getLogs', [{'address': path.z.MANAGER, 'blockHash': base['initialize']['blockHash'],
                        'topics': [path.z.INIT_TOPIC, path.z.POOL]}], [base['initialize']])
    for to, sig, arg, key in (
        (path.z.STATE_VIEW, 'poolManager()', '', 'state_view_manager'),
        (path.z.STATE_VIEW, 'getSlot0(bytes32)', path.z.POOL[2:], 'slot0'),
        (path.z.STATE_VIEW, 'getLiquidity(bytes32)', path.z.POOL[2:], 'liquidity'),
        (path.z.IMD, 'decimals()', '', 'imd_decimals'),
        (path.z.ZTO, 'decimals()', '', 'zto_decimals')):
        call(to, sig, arg, base['raw'][key])
    for key, raw in observation['bitmap'].items():
        call(path.z.STATE_VIEW, 'getTickBitmap(bytes32,int16)',
             path.z.POOL[2:] + path.z.word(int(key)).hex(), raw)
    for key, raw in observation['ticks'].items():
        call(path.z.STATE_VIEW, 'getTickLiquidity(bytes32,int24)',
             path.z.POOL[2:] + path.z.word(int(key)).hex(), raw)
    manager = manager_evidence if manager_evidence is not None else path.read_json(str(MANAGER_EVIDENCE))
    path.z.require(manager['block'] == base['block'] and manager['request'] == {
        'to': path.QUOTER, 'data': path.selector('poolManager()')}, 'manager evidence context mismatch')
    path.z.require(path.z.address_word(manager['raw_result']) == path.z.MANAGER,
                   'recorded Quoter manager mismatch')
    call(path.QUOTER, 'poolManager()', '', manager['raw_result'])
    for case in evidence['results']:
        values = [int(path.z.IMD, 16), int(path.z.ZTO, 16), 12500, 60, int(state['hook'], 16),
                  int(case['input_token'] == 'IMD'),
                  int(path.quote(observation, case['input_token'], case['amount'])['requested_input_raw']), 256]
        expected = path.selector('quoteExactInputSingle(((address,address,uint24,int24,address),bool,uint128,bytes))')
        expected += (path.z.word(32) + b''.join(path.z.word(v) for v in values) + path.z.word(0)).hex()
        path.z.require(case['request'] == {'to': path.QUOTER, 'data': expected},
                       'recorded quote calldata does not match the stated input')
        path.z.words(case['raw_result'], 2)
        put('eth_call', [case['request'], pin], case['raw_result'])
    return table


@contextlib.contextmanager
def replay_relay(table):
    """Ephemeral local HTTP replay, no forwarding or external network access."""
    calls = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            try:
                length = int(self.headers.get('Content-Length', '0'))
                path.z.require(0 < length <= 100_000, 'invalid request size')
                request = json.loads(self.rfile.read(length))
                path.z.require(request['method'] in path.z.RPC.METHODS, 'not a read method')
                key = json.dumps([request['method'], request['params']], sort_keys=True)
                path.z.require(key in table, 'request absent from historical replay')
                calls.append({'method': request['method'], 'params': request['params']})
                reply = {'jsonrpc': '2.0', 'id': request['id'], 'result': table[key]}
            except (ValueError, KeyError, TypeError) as exc:
                reply = {'jsonrpc': '2.0', 'id': None, 'error': {'code': -32602, 'message': str(exc)}}
            encoded = json.dumps(reply).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield 'http://127.0.0.1:%d/rpc/1' % server.server_port, calls
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def refresh(endpoint, block, radius, cases):
    observation = path.capture(endpoint, block, radius)
    comparison = path.compare(observation, endpoint, cases)
    path.z.require(comparison['all_match'], 'local swap output disagrees with the quoter')
    return observation, comparison


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', action='store_true', help='otherwise replay real saved state over local HTTP')
    parser.add_argument('--rpc', default=path.z.PUBLIC_RPC, help='HTTPS or explicit literal loopback relay')
    parser.add_argument('--block', default='finalized')
    parser.add_argument('--word-radius', type=int, default=1)
    parser.add_argument('--input', choices=('ZTO', 'IMD'), default='ZTO')
    parser.add_argument('--amount', default='1')
    parser.add_argument('--save-observation')
    parser.add_argument('--save-check')
    parser.add_argument('--save-report')
    args = parser.parse_args(argv)
    try:
        if args.live:
            tag = args.block if args.block in ('finalized', 'safe', 'latest') else hex(int(args.block))
            observation, comparison = refresh(args.rpc, tag, args.word_radius, [(args.input, args.amount)])
            mode, calls = 'live_read_only', None
            archival_source = None
        else:
            path.z.require(not args.save_observation and not args.save_check,
                           'demo may save only its report; it is historical replay, not a new capture')
            saved = path.read_json(str(SNAPSHOT))
            evidence = path.read_json(str(EVIDENCE))
            cases = [(r['input_token'], r['amount']) for r in evidence['results']]
            with replay_relay(replay_table(saved, evidence)) as (endpoint, calls):
                observation, comparison = refresh(endpoint, saved['base']['block']['number'],
                                                  saved['word_radius'], cases)
            mode, archival_source = 'historical_local_http_replay', saved['base']['source']
        result = {'schema': 'zto-refresh-report-v1', 'mode': mode,
                  'pool_id': path.z.POOL, 'block': observation['base']['block'],
                  'transport_endpoint': observation['base']['source'],
                  'archival_source': archival_source,
                  'comparison_count': len(comparison['results']), 'all_match': comparison['all_match'],
                  'requested_quote_compared': any(r['input_token'] == args.input and
                                                 r['amount'] == args.amount for r in comparison['results']),
                  'quote': path.quote(observation, args.input, args.amount),
                  'read_request_count': len(calls) if calls is not None else None,
                  'limitations': ['Transport labels do not establish an upstream provider or independent agreement.',
                                  'Pool arithmetic does not simulate settlement, token behavior, gas or future inclusion.']}
        if not args.live:
            result['manager_evidence_source'] = path.read_json(str(MANAGER_EVIDENCE))['source']
            result['limitations'].append('Demo replays historical raw replies over local HTTP; it is not a fresh collection or independent provider agreement.')
        if args.save_observation:
            path.save_json(args.save_observation, observation)
        if args.save_check:
            path.save_json(args.save_check, comparison)
        if args.save_report:
            path.save_json(args.save_report, result)
        print(json.dumps(result, indent=2))
        return 0 if result['quote']['status'] == 'estimated' else 2
    except (ValueError, KeyError, TypeError, AttributeError, OSError, OverflowError) as exc:
        print(json.dumps({'error': str(exc)}), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
