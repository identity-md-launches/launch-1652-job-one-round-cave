#!/usr/bin/env python3
"""Offline reviewed-code gate over Ethereum state proofs and optional ancestry."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'code-ancestry'))
import code_ancestry as ancestry

proof, lens = ancestry.proof, ancestry.lens
require, keys = lens.require, ancestry.keys
SCHEMA = 'code-review-v1'
KINDS = {'no-supported-proxy-signal', 'eip1167-exact',
         'eip1967-implementation-candidate', 'eip1967-beacon-candidate'}


def uint64(value, label):
    require(type(value) is int and 0 <= value < 2**64, label + ' must be a uint64 integer')
    return value


def normalize_path(path):
    """Exact ordered identities, including both measured slots; no wildcards."""
    require(isinstance(path, list) and 1 <= len(path) <= lens.MAX_DEPTH + 1,
            'review path must contain 1 to 5 nodes')
    result, seen = [], set()
    for node in path:
        keys(node, ('address', 'code_hash', 'kind', 'next_address', 'storage'), 'review node')
        target = lens.address(node['address'])
        require(target not in seen, 'duplicate review address')
        seen.add(target)
        require(node['kind'] in KINDS, 'unknown review node kind')
        keys(node['storage'], lens.SLOTS, 'review storage')
        result.append({'address': target, 'code_hash': lens.fixed_hex(node['code_hash'], 32),
                       'kind': node['kind'],
                       'next_address': None if node['next_address'] is None else lens.address(node['next_address']),
                       'storage': {name: lens.fixed_hex(node['storage'][name], 32) for name in lens.SLOTS}})
    for index, node in enumerate(result):
        following = result[index + 1]['address'] if index + 1 < len(result) else None
        require(node['next_address'] == following, 'review path is disconnected')
        require((node['kind'] == 'no-supported-proxy-signal') == (following is None),
                'review kind and path ending disagree')
    return result


def validate_review(review):
    keys(review, ('schema', 'chain_id', 'target', 'path', 'max_age_blocks'), 'review')
    require(review['schema'] == SCHEMA and type(review['chain_id']) is int
            and review['chain_id'] == 1, 'wrong review schema or chain')
    target = lens.address(review['target'])
    path = normalize_path(review['path'])
    require(path[0]['address'] == target, 'review target and path differ')
    return {'schema': SCHEMA, 'chain_id': 1, 'target': target, 'path': path,
            'max_age_blocks': uint64(review['max_age_blocks'], 'max_age_blocks')}


def observed_path(observation):
    return normalize_path([{key: node[key] for key in
                           ('address', 'code_hash', 'kind', 'next_address', 'storage')}
                           for node in observation['nodes']])


def evaluate(bundle, review, as_of_block, anchor_hash=None, chain=None):
    """Accept identity only; caller remains responsible for review and anchor trust."""
    review = validate_review(review)
    as_of_block = uint64(as_of_block, 'as_of_block')
    # Never consume saved result summaries: reconstruct proofs and headers each run.
    checked = (ancestry.verify(bundle, chain, anchor_hash) if chain is not None
               else proof.verify(bundle, anchor_hash))
    observation = bundle['observation']
    actual = observed_path(observation)
    code_block = ancestry.block_identity(observation['block'])
    checkpoint = ancestry.block_identity(chain['checkpoint']) if chain is not None else code_block
    height = lens.quantity(code_block['number'])
    checkpoint_height = lens.quantity(checkpoint['number'])
    require(as_of_block >= checkpoint_height, 'as_of_block precedes evidence checkpoint')
    age = as_of_block - height  # Crucially not as_of_block minus checkpoint height.
    differences = []
    if lens.address(observation['target']) != review['target']:
        differences.append({'field': 'target', 'expected': review['target'],
                            'observed': lens.address(observation['target'])})
    for index in range(max(len(actual), len(review['path']))):
        expected = review['path'][index] if index < len(review['path']) else None
        observed = actual[index] if index < len(actual) else None
        if expected != observed:
            differences.append({'field': 'path', 'index': index,
                                'expected': expected, 'observed': observed})
    reasons = []
    if differences:
        reasons.append('reviewed-identity-mismatch')
    if age > review['max_age_blocks']:
        reasons.append('code-evidence-too-old')
    if checked['unproven_beacon_call_results']:
        reasons.append('unproven-beacon-routing')
    if anchor_hash is None:
        reasons.append('missing-caller-anchor')
    serialized = json.dumps(review, sort_keys=True, separators=(',', ':')).encode('ascii')
    return {
        'schema': 'code-review-result-v1', 'chain_id': 1,
        'decision': 'accept-identity' if not reasons else 'refuse',
        'reasons': reasons, 'identity_matches': not differences,
        'review_digest': lens.digest(serialized), 'target': observation['target'],
        'code_block': code_block, 'checkpoint': checkpoint,
        'as_of_block': as_of_block, 'code_age_blocks': age,
        'max_age_blocks': review['max_age_blocks'],
        'age_reference': 'caller-supplied-height; not current-time verification',
        'differences': differences, 'state_inclusion_verified': True,
        'anchor_hash_matched': anchor_hash is not None,
        'anchor_authenticity_verified': False, 'consensus_verified': False,
        'parent_links_verified': checked.get('parent_links_verified', 0),
        'proof_provenance': lens.provenance(observation),
        'scope': 'Exact reviewed runtime/path/slot identity at code_block only. '
                 'The caller must independently trust the anchor and review. '
                 'A match does not establish semantic safety, routing behavior, unchanged code '
                 'between blocks, code at checkpoint/today, finality, or permission to transact.',
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', required=True, help='workspace Code Proof bundle')
    parser.add_argument('--review', required=True, help='separately reviewed exact code/path identity')
    parser.add_argument('--as-of-block', required=True, type=int, help='explicit decimal reference height')
    parser.add_argument('--anchor-hash', help='independently trusted execution hash; never read from evidence')
    parser.add_argument('--ancestry', help='optional Code Ancestry file ending at anchor hash')
    args = parser.parse_args()
    try:
        result = evaluate(ancestry.read_json(args.bundle), ancestry.read_json(args.review),
                          args.as_of_block, args.anchor_hash,
                          ancestry.read_json(args.ancestry) if args.ancestry else None)
        print(json.dumps(result, indent=2))
        return 0 if result['decision'] == 'accept-identity' else 3
    except (ValueError, KeyError, TypeError, OSError, OverflowError, AttributeError,
            IndexError, RecursionError) as error:
        print('Code Review: ' + str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
