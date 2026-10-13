#!/usr/bin/env python3
"""Read-only ZTO/IMD exact-input quotes across a bounded v4 tick bitmap."""
import argparse
import json
from pathlib import Path
import sys

# Ordinary sibling source files, already included in this repository. No install.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'zto-band'))
import zto_band as z
from keccak import selector
from math_core import sqrt_at_tick, swap_step, amount0, amount1, total_fee

SCHEMA = 'zto-path-observation-v1'
QUOTER = '0x52f0e24d1c21c8a0cb1e5a5dd6198556bd9e1203'
MAX_TICKS = 128
MAX_STEPS = 256


def read_json(path):
    with z.workspace_file(path).open('rb') as handle:
        data = handle.read(100_001)
    z.require(len(data) <= 100_000, 'JSON exceeds 100 KB')
    return json.loads(data)


def save_json(path, value):
    data = json.dumps(value, indent=2) + '\n'
    z.require(len(data.encode()) < 100_000, 'JSON exceeds 100 KB')
    z.workspace_file(path).write_text(data)


def tick_keys(bitmap, spacing):
    return {(position * 256 + bit) * spacing
            for position, bits in bitmap.items() for bit in range(256) if bits & (1 << bit)}


def decode(observation):
    z.require(isinstance(observation, dict) and observation['schema'] == SCHEMA,
              'wrong path observation schema')
    state = z.decode(observation['base'])
    radius = observation['word_radius']
    z.require(type(radius) is int and 0 <= radius <= 4, 'word radius must be 0..4')
    center = state['tick'] // state['spacing'] // 256
    raw_bitmap = observation['bitmap']
    z.require(isinstance(raw_bitmap, dict) and set(raw_bitmap) ==
              {str(i) for i in range(center-radius, center+radius+1)},
              'bitmap coverage must be complete, contiguous and centered')
    bitmap = {int(k): z.words(v, 1)[0] for k, v in raw_bitmap.items()}
    expected = tick_keys(bitmap, state['spacing'])
    z.require(len(expected) <= MAX_TICKS, 'too many initialized ticks; narrow word radius')
    z.require(all(-887272 <= t <= 887272 for t in expected), 'initialized tick out of range')
    raw_ticks = observation['ticks']
    z.require(isinstance(raw_ticks, dict) and set(raw_ticks) == {str(t) for t in expected},
              'tick records must exactly match every initialized bitmap bit')
    ticks = {}
    for key, raw in raw_ticks.items():
        gross, net = z.words(raw, 2)
        z.uint(gross, 128, 'tick liquidity gross')
        net = z.signed(net, 128)
        z.require(gross > 0 and abs(net) <= gross and (gross + net) % 2 == 0,
                  'invalid initialized tick liquidity')
        ticks[int(key)] = net
    return state, bitmap, ticks


def capture(endpoint, block_tag='finalized', radius=1):
    z.require(type(radius) is int and 0 <= radius <= 4, 'word radius must be 0..4')
    base = z.capture(endpoint, block_tag)
    state = z.decode(base)
    rpc = z.RPC(endpoint)
    z.require(rpc.call('eth_chainId', []) == '0x1', 'expected Ethereum chain 1')
    pin = {'blockHash': base['block']['hash'], 'requireCanonical': True}
    def call(signature, argument):
        data = selector(signature) + z.POOL[2:] + z.word(argument).hex()
        return rpc.call('eth_call', [{'to': z.STATE_VIEW, 'data': data}, pin])
    center = state['tick'] // state['spacing'] // 256
    bitmap = {str(i): call('getTickBitmap(bytes32,int16)', i)
              for i in range(center-radius, center+radius+1)}
    keys = tick_keys({int(k): z.words(v, 1)[0] for k, v in bitmap.items()}, state['spacing'])
    z.require(len(keys) <= MAX_TICKS, 'too many initialized ticks; narrow word radius')
    ticks = {str(t): call('getTickLiquidity(bytes32,int24)', t) for t in sorted(keys)}
    end = rpc.call('eth_getBlockByNumber', [base['block']['number'], False])
    z.require(end and end['hash'] == base['block']['hash'], 'block changed during tick capture')
    observation = {'schema': SCHEMA, 'base': base, 'word_radius': radius,
                   'bitmap': bitmap, 'ticks': ticks}
    decode(observation)
    return observation


def next_boundary(bitmap, tick, spacing, down):
    """One bitmap word at a time, including empty-word rounding boundaries."""
    compressed = tick // spacing + (0 if down else 1)
    position, bit = divmod(compressed, 256)
    if position not in bitmap:
        return None
    bits = bitmap[position]
    if down:
        masked = bits & ((1 << (bit+1)) - 1)
        index = masked.bit_length()-1 if masked else 0
    else:
        masked = bits & (((1 << 256)-1) ^ ((1 << bit)-1))
        index = (masked & -masked).bit_length()-1 if masked else 255
    boundary = (position * 256 + index) * spacing
    return max(-887272, min(887272, boundary)), bool(masked)


def tick_at_price(price):
    lo, hi = -887272, 887272
    while lo < hi:
        mid = (lo+hi+1)//2
        if sqrt_at_tick(mid) <= price:
            lo = mid
        else:
            hi = mid-1
    return lo


def quote(observation, token='ZTO', amount='100000000', max_steps=MAX_STEPS):
    state, bitmap, ticks = decode(observation)
    z.require(token in ('ZTO', 'IMD'), 'input must be ZTO or IMD')
    z.require(type(max_steps) is int and 1 <= max_steps <= MAX_STEPS, 'max steps must be 1..256')
    down = token == 'IMD'
    din, dout = state['decimals'] if down else state['decimals'][::-1]
    gross = z.parse_amount(amount, din)
    z.require(gross < 1 << 127, 'input must fit positive int128 pool delta')
    fee = total_fee(state['protocol'], state['lp'], down)
    price, tick, liquidity = state['price'], state['tick'], state['liquidity']
    remaining, output, fees = gross, 0, 0
    trace = []
    status = 'step_limit'
    price_limit = sqrt_at_tick(-887272)+1 if down else sqrt_at_tick(887272)-1
    for _ in range(max_steps):
        boundary = next_boundary(bitmap, tick, state['spacing'], down)
        if boundary is None:
            status = 'outside_coverage'
            break
        edge, initialized = boundary
        edge_price = sqrt_at_tick(edge)
        target = max(edge_price, price_limit) if down else min(edge_price, price_limit)
        z.require(target <= price if down else target >= price, 'inconsistent tick direction')
        before = liquidity
        if price == target or liquidity == 0:
            # Crossing an exact boundary or a known empty range consumes nothing.
            nxt, consumed, received, charged = target, 0, 0, 0
        else:
            step = swap_step(price, target, liquidity, fee, remaining, down)
            nxt = int(step['sqrt_price_after_x96'])
            consumed = int(step['input_consumed_raw'])
            received = int(step['output_raw'])
            # Sqrt-price rounding can make actual net input smaller than available.
            net = (amount0 if down else amount1)(price, nxt, liquidity, True)
            charged = consumed - net
            z.require(charged >= 0, 'negative rounded fee')
        remaining -= consumed
        output += received
        fees += charged
        crossed = initialized and nxt == edge_price
        if crossed:
            liquidity += -ticks[edge] if down else ticks[edge]
            z.uint(liquidity, 128, 'liquidity after crossing')
        if nxt == edge_price:
            tick = edge-1 if down else edge
        elif nxt != price:
            tick = tick_at_price(nxt)
        price = nxt
        trace.append({'boundary_tick': edge, 'initialized': initialized, 'crossed': crossed,
                      'liquidity_before_raw': str(before), 'liquidity_after_raw': str(liquidity),
                      'input_consumed_raw': str(consumed), 'output_raw': str(received),
                      'fee_raw': str(charged), 'sqrt_price_after_x96': str(price)})
        if remaining == 0:
            status = 'estimated'
            break
        if price == price_limit:
            status = 'price_limit'
            break
    z.require(output < 1 << 127, 'output exceeds int128 pool delta')
    totals = {'input_consumed_raw': str(gross-remaining), 'input_unspent_raw': str(remaining),
              'output_raw': str(output), 'output': z.units(output, dout),
              'fee_raw': str(fees), 'fee': z.units(fees, din),
              'sqrt_price_after_x96': str(price), 'tick_after': tick,
              'liquidity_after_raw': str(liquidity)}
    return {'schema': 'zto-path-report-v1', 'status': status, 'pool_id': z.POOL,
            'chain_id': 1, 'block': observation['base']['block'],
            'source': observation['base']['source'], 'input_token': token,
            'output_token': 'ZTO' if down else 'IMD', 'requested_input_raw': str(gross),
            'fee_pips': fee, 'bitmap_words': sorted(bitmap),
            'initialized_ticks_crossed': sum(s['crossed'] for s in trace),
            'scope': 'Exact-input core pool estimate within recorded tick coverage; not an executable quote.',
            'limitations': ['Historical RPC data, not a proof or freshness guarantee.',
                            'No router settlement, token transfer behavior, gas, slippage or MEV simulation.',
                            'Incomplete fills have partial diagnostics only, never a full-fill estimate.'],
            'estimate' if status == 'estimated' else 'partial': totals, 'steps': trace}


def compare(observation, endpoint, cases):
    state, _, _ = decode(observation)
    rpc = z.RPC(endpoint)
    z.require(rpc.call('eth_chainId', []) == '0x1', 'expected Ethereum chain 1')
    pin = {'blockHash': observation['base']['block']['hash'], 'requireCanonical': True}
    manager = rpc.call('eth_call', [{'to': QUOTER, 'data': selector('poolManager()')}, pin])
    z.require(z.address_word(manager) == z.MANAGER, 'quoter manager mismatch')
    results = []
    for token, amount in cases:
        local = quote(observation, token, amount)
        z.require(local['status'] == 'estimated', 'comparison requires a complete local fill')
        values = [int(z.IMD,16), int(z.ZTO,16), 12500, 60, int(state['hook'],16),
                  int(token == 'IMD'), int(local['requested_input_raw']), 256]
        data = selector('quoteExactInputSingle(((address,address,uint24,int24,address),bool,uint128,bytes))')
        data += (z.word(32) + b''.join(z.word(v) for v in values) + z.word(0)).hex()
        request = {'to': QUOTER, 'data': data}
        raw = rpc.call('eth_call', [request, pin])
        actual, _ = z.words(raw, 2)
        results.append({'input_token': token, 'amount': amount, 'request': request, 'raw_result': raw,
                        'local_output_raw': local['estimate']['output_raw'],
                        'initialized_ticks_crossed': local['initialized_ticks_crossed'],
                        'matches': actual == int(local['estimate']['output_raw'])})
    end = rpc.call('eth_getBlockByNumber', [observation['base']['block']['number'], False])
    z.require(end and end['hash'] == pin['blockHash'], 'block changed during comparison')
    return {'schema': 'zto-path-quoter-check-v1', 'block': observation['base']['block'],
            'source': endpoint,
            'quoter': QUOTER, 'all_match': all(r['matches'] for r in results), 'results': results}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    source = p.add_mutually_exclusive_group(required=True)
    source.add_argument('--snapshot')
    source.add_argument('--live', action='store_true')
    p.add_argument('--rpc', default=z.PUBLIC_RPC)
    p.add_argument('--block', default='finalized')
    p.add_argument('--word-radius', type=int, default=1)
    p.add_argument('--save', help='save a live observation inside the workspace')
    p.add_argument('--input', choices=('ZTO','IMD'), default='ZTO')
    p.add_argument('--amount', default='100000000')
    p.add_argument('--max-steps', type=int, default=MAX_STEPS)
    p.add_argument('--check-quoter', action='store_true', help='network eth_call at the snapshot block')
    p.add_argument('--save-check', help='save quoter evidence inside the workspace')
    args = p.parse_args(argv)
    try:
        z.require(args.save is None or args.live, '--save requires --live')
        z.require(args.save_check is None or args.check_quoter, '--save-check requires --check-quoter')
        if args.snapshot:
            observation = read_json(args.snapshot)
        else:
            tag = args.block if args.block in ('finalized','safe','latest') else hex(int(args.block))
            observation = capture(args.rpc, tag, args.word_radius)
        result = quote(observation, args.input, args.amount, args.max_steps)
        if args.save:
            save_json(args.save, observation)
        if args.check_quoter:
            check = compare(observation, args.rpc, [(args.input, args.amount)])
            if args.save_check:
                save_json(args.save_check, check)
            result['quoter_check'] = check
            z.require(check['all_match'], 'quoter output disagrees with local math')
        print(json.dumps(result, indent=2))
        return 0 if result['status'] == 'estimated' else 2
    except (ValueError, KeyError, TypeError, AttributeError, OSError, OverflowError) as exc:
        print(json.dumps({'error': str(exc)}), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
