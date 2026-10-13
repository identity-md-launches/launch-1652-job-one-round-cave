#!/usr/bin/env python3
"""Choose one complete, block-pinned ZTO/IMD path snapshot; never mix RPCs."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'zto-path'))
import zto_path as path

SCHEMA = 'zto-archive-report-v1'
DEFAULT_SNAPSHOT = Path(__file__).resolve().parent.parent / 'zto-path' / 'observation.json'
DEFAULT_RPCS = ('https://ethereum-rpc.publicnode.com', 'https://eth.drpc.org')


def inside_workspace(name):
    return path.z.workspace_file(name)


def validate_snapshot(observation):
    """Validate a complete Path observation and expose the one pin it represents."""
    state, bitmap, ticks = path.decode(observation)
    base = observation['base']
    block = base['block']
    path.z.validate_endpoint(base.get('source'))
    path.z.require(isinstance(block.get('number'), str) and isinstance(block.get('hash'), str),
                   'snapshot must carry a block number and hash')
    return {'block': block, 'source': base['source'], 'tick': state['tick'],
            'liquidity_raw': str(state['liquidity']), 'bitmap_word_count': len(bitmap),
            'initialized_tick_count': len(ticks)}


def report_snapshot(observation, mode='offline_validation', attempts=()):
    selected = validate_snapshot(observation)
    return {'schema': SCHEMA, 'chain_id': 1, 'pool_id': path.z.POOL, 'mode': mode,
            'selected': selected, 'attempts': list(attempts),
            'invariant': 'One selected endpoint supplied initialization, state, bitmap and ticks at one block hash.',
            'scope': 'Archive-source selection for a ZTO/IMD Path observation; no transaction is prepared.',
            'limitations': ['A successful RPC response is provider evidence, not a state proof.',
                            'Failure of one archive endpoint does not establish a pool or math failure.',
                            'This does not compare providers or make a snapshot current.']}


def capture_one(rpcs, block, radius):
    """Try sources independently. A failed source contributes no data to the winner."""
    attempts = []
    for endpoint in rpcs:
        try:
            observation = path.capture(endpoint, block, radius)
            selected = validate_snapshot(observation)
            attempts.append({'source': endpoint, 'status': 'selected', 'block': selected['block']})
            return observation, attempts
        except (ValueError, KeyError, TypeError, AttributeError, OSError, OverflowError) as exc:
            attempts.append({'source': endpoint, 'status': 'unavailable', 'error': str(exc)[:300]})
    raise ValueError('no endpoint produced one complete pinned observation: ' + json.dumps(attempts))


def save_json(name, value):
    encoded = json.dumps(value, indent=2) + '\n'
    path.z.require(len(encoded.encode()) <= 100_000, 'JSON exceeds 100 KB')
    inside_workspace(name).write_text(encoded)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--snapshot', help='validate an existing Path snapshot inside this workspace')
    group.add_argument('--live', action='store_true', help='read one complete snapshot from one archive endpoint')
    parser.add_argument('--rpc', action='append', help='HTTPS endpoint; repeat to specify fallback order')
    parser.add_argument('--block', default='finalized')
    parser.add_argument('--word-radius', type=int, default=1)
    parser.add_argument('--save-observation', help='write selected raw observation inside workspace (live only)')
    parser.add_argument('--save-report', help='write report inside workspace')
    args = parser.parse_args(argv)
    try:
        path.z.require(args.save_observation is None or args.live, '--save-observation requires --live')
        path.z.require(0 <= args.word_radius <= 4, 'word radius must be 0..4')
        if args.snapshot:
            observation = path.read_json(args.snapshot)
            result = report_snapshot(observation)
        else:
            sources = tuple(args.rpc) if args.rpc else DEFAULT_RPCS
            path.z.require(len(sources) <= 8, 'at most eight endpoints')
            tag = args.block if args.block in ('finalized', 'safe', 'latest') else hex(int(args.block))
            observation, attempts = capture_one(sources, tag, args.word_radius)
            if args.save_observation:
                path.save_json(args.save_observation, observation)
            result = report_snapshot(observation, 'live_single_source', attempts)
        if args.save_report:
            save_json(args.save_report, result)
        print(json.dumps(result, indent=2))
        return 0
    except (ValueError, KeyError, TypeError, AttributeError, OSError, OverflowError) as exc:
        print(json.dumps({'error': str(exc)}), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
