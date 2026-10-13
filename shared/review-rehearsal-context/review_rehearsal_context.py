#!/usr/bin/env python3
"""Keep a reviewed code identity and a rehearsed call in their exact context."""
import argparse
import json
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
LIMIT = 98_000
SCHEMA = 'review-rehearsal-context-v1'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def object_no_duplicates(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate JSON key: ' + key)
        result[key] = value
    return result


def workspace_path(value):
    path = Path(value).resolve()
    require(path.is_relative_to(Path.cwd().resolve()), 'path escapes workspace')
    return path


def load(value):
    path = workspace_path(value)
    raw = path.read_bytes()
    require(len(raw) <= LIMIT, 'input exceeds 98000 bytes')
    return json.loads(raw, object_pairs_hook=object_no_duplicates)


def block(value, label):
    require(isinstance(value, dict) and set(value) >= {'number', 'hash'}, label + ' is malformed')
    number, digest = value['number'], value['hash']
    require(isinstance(number, str) and number.startswith('0x') and int(number[2:], 16) >= 0,
            label + ' number is malformed')
    require(isinstance(digest, str) and len(digest) == 66 and digest.startswith('0x')
            and all(c in '0123456789abcdef' for c in digest[2:].lower()), label + ' hash is malformed')
    return {'number': hex(int(number, 16)), 'hash': digest.lower()}


def address(value, label):
    require(isinstance(value, str) and len(value) == 42 and value.startswith('0x')
            and all(c in '0123456789abcdef' for c in value[2:].lower()), label + ' is malformed')
    return value.lower()


def assess(review, rehearsal):
    require(isinstance(review, dict) and review.get('schema') == 'code-review-result-v1',
            'unsupported code review result')
    require(review.get('chain_id') == 1 and review.get('decision') in ('accept-identity', 'refuse'),
            'invalid code review result')
    require(isinstance(rehearsal, dict) and rehearsal.get('schema') == 'call-rehearsal-v1'
            and rehearsal.get('chain_id') == 1, 'unsupported rehearsal result')
    code_target = address(review.get('target'), 'review target')
    call = rehearsal.get('call')
    require(isinstance(call, dict), 'rehearsal call is malformed')
    call_target = address(call.get('to'), 'rehearsal target')
    code_block = block(review.get('code_block'), 'review code block')
    call_block = block(rehearsal.get('block'), 'rehearsal block')
    target_matches, block_matches = code_target == call_target, code_block == call_block
    accepted = review['decision'] == 'accept-identity'
    coherent = accepted and target_matches and block_matches
    if coherent:
        verdict = 'coherent_reviewed_rehearsal'
    elif not target_matches or not block_matches:
        verdict = 'context_mismatch'
    else:
        verdict = 'review_refused'
    return {'schema': SCHEMA, 'verdict': verdict, 'coherent': coherent,
            'reviewed_identity_accepted': accepted, 'same_target': target_matches,
            'same_block': block_matches, 'review_target': code_target, 'rehearsal_target': call_target,
            'review_code_block': code_block, 'rehearsal_block': call_block,
            'limits': ['A coherent result joins supplied historical evidence only.',
                       'It does not authenticate the caller anchor, RPC, consensus or code review.',
                       'It does not prove a state effect, safety, gas need or future transaction outcome.',
                       'No wallet, key, signature, transaction, payment or network request is used.']}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_subparsers(dest='mode', required=True)
    modes.add_parser('demo', help='compare saved real ZTO review and relay rehearsal')
    check = modes.add_parser('check', help='compare a code review result and rehearsal JSON')
    check.add_argument('--review', required=True)
    check.add_argument('--rehearsal', required=True)
    args = parser.parse_args(argv)
    try:
        if args.mode == 'demo':
            review = load('line-3/tools/code-review/zto-result.json')
            rehearsal = load('line-4/tools/relay-rehearsal/zto-relay-observation.json')
        else:
            review, rehearsal = load(args.review), load(args.rehearsal)
        result = assess(review, rehearsal)
        print(json.dumps(result, indent=2, allow_nan=False))
        return 0 if result['coherent'] else 2
    except (ValueError, TypeError, KeyError, OSError, OverflowError, json.JSONDecodeError) as error:
        print(json.dumps({'error': str(error)}), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
