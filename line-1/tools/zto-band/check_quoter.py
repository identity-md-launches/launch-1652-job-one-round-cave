#!/usr/bin/env python3
"""Optional read-only comparison with the deployed V4Quoter at a snapshot block.

Only eth_call is used. The node simulates the quoter and discards all changes.
No transaction, wallet, signing, or deployment is involved.
"""

import argparse
import json
import sys

import zto_band as z
from keccak import selector

QUOTER = '0x52f0e24d1c21c8a0cb1e5a5dd6198556bd9e1203'
CASES = [('ZTO', '0.000000000000000001'), ('ZTO', '1'), ('ZTO', '1000'),
         ('ZTO', '400000'), ('IMD', '0.000000000000000001'), ('IMD', '0.001'),
         ('IMD', '0.1'), ('IMD', '1')]


def check(observation, endpoint):
    state = z.decode(observation)
    rpc = z.RPC(endpoint)
    z.require(rpc.call('eth_chainId', []) == '0x1', 'expected Ethereum chain 1')
    pin = {'blockHash': observation['block']['hash'], 'requireCanonical': True}
    manager = rpc.call('eth_call', [{'to': QUOTER, 'data': selector('poolManager()')}, pin])
    z.require(z.address_word(manager) == z.MANAGER, 'Quoter manager mismatch')
    results = []
    for token, amount in CASES:
        local = z.report(observation, token, amount)
        if local['status'] != 'estimated':
            results.append({'input_token': token, 'input': amount, 'status': 'outside_interval'})
            continue
        values = [int(z.IMD, 16), int(z.ZTO, 16), 12500, 60, int(state['hook'], 16),
                  int(token == 'IMD'), int(local['requested_input_raw']), 256]
        payload = z.word(32) + b''.join(z.word(v) for v in values) + z.word(0)
        data = selector('quoteExactInputSingle(((address,address,uint24,int24,address),bool,uint128,bytes))') + payload.hex()
        call = {'to': QUOTER, 'data': data}
        raw = rpc.call('eth_call', [call, pin])
        actual, _gas = z.words(raw, 2)
        expected = int(local['estimate']['output_raw'])
        results.append({'input_token': token, 'input': amount, 'request': call, 'raw_result': raw,
                        'local_output_raw': str(expected), 'quoter_output_raw': str(actual),
                        'matches': actual == expected})
    z.require(all(r.get('matches', True) for r in results), 'local result disagrees with V4Quoter')
    z.require(any('matches' in r for r in results), 'no comparison fit the interval')
    return {'schema': 'zto-band-quoter-check-v1', 'source': endpoint,
            'block': observation['block'], 'quoter': QUOTER, 'results': results}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--snapshot', required=True)
    p.add_argument('--rpc', default=z.PUBLIC_RPC)
    p.add_argument('--save', help='optional workspace output JSON')
    args = p.parse_args()
    try:
        with z.workspace_file(args.snapshot).open('rb') as handle:
            raw = handle.read(100_001)
        z.require(len(raw) <= 100_000, 'snapshot exceeds 100 KB')
        result = check(json.loads(raw), args.rpc)
        encoded = json.dumps(result, indent=2) + '\n'
        z.require(len(encoded.encode()) <= 100_000, 'check report exceeds 100 KB')
        if args.save:
            z.workspace_file(args.save).write_text(encoded)
        print(json.dumps({'comparisons': len([r for r in result['results'] if 'matches' in r]),
                          'all_match': True, 'block': result['block']}, indent=2))
        return 0
    except (ValueError, KeyError, TypeError, AttributeError, OSError, OverflowError) as exc:
        print(json.dumps({'error': str(exc)}), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
