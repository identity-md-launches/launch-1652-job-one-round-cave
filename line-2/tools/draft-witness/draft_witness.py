#!/usr/bin/env python3
"""Check that an unsigned ERC-20 revoke draft exactly matches reviewed evidence.

This is intentionally an offline witness.  It does not connect to an RPC,
open a wallet, sign, simulate, broadcast, or write a transaction.
"""

import argparse
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'approval-draft'))
import approval_draft as drafts

DEFAULT_OBSERVATION = HERE.parent / 'permission-gate' / 'live-observation.json'
DEFAULT_POLICY = HERE.parent / 'permission-gate' / 'demo-policy.json'
MAX_DRAFT_BYTES = 16_384


def load_draft(path):
    """Load one bounded JSON draft, rejecting duplicate keys and outside paths."""
    candidate = drafts.gate.lens.workspace_path(path)
    with candidate.open('rb') as stream:
        payload = stream.read(MAX_DRAFT_BYTES + 1)
    drafts.gate.lens.require(len(payload) <= MAX_DRAFT_BYTES,
                             'draft exceeds 16 KiB')
    return json.loads(payload, object_pairs_hook=drafts.gate.unique_object)


def witness(candidate, observation, policy):
    """Return a deterministic match/no-match report for one proposed draft."""
    expected = drafts.build(observation, policy)
    gate_decision = expected['permission_gate_decision']
    matched = []
    if gate_decision == 'deny':
        # Exact object equality deliberately refuses added transaction fields such
        # as nonce, gas, fees, or a changed calldata destination.
        matched = [row for row in expected['drafts'] if row == candidate]
    status = 'exact_match' if matched else (
        'no_candidate_from_insufficient_evidence'
        if gate_decision == 'insufficient_evidence' else 'not_a_reviewed_candidate')
    return {
        'schema': 'allowance-draft-witness-v1',
        'status': status,
        'matches_reviewed_draft': bool(matched),
        'permission_gate_decision': gate_decision,
        'chain_id': expected['chain_id'],
        'token': expected['token'],
        'token_address': expected['token_address'],
        'block_number': expected['block_number'],
        'block_hash': expected['block_hash'],
        'candidate_count': expected['draft_count'],
        'complete_wallet_audit': False,
        'limitations': [
            'A match only binds this unsigned object to supplied historical evidence and policy.',
            'A match is not an instruction, authorization, signature, simulation, broadcast, or receipt.',
            'Refresh canonical evidence and let the owner independently verify before any wallet action.',
            'Unknown spenders, Permit2, signatures, custom permissions, other tokens and chains are outside coverage.',
            'The proposed object must be byte-for-structure identical; nonce, gas and fee fields are intentionally absent.',
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--draft', help='one JSON draft object to compare')
    parser.add_argument('--observation', help='reviewed raw observation or inventory')
    parser.add_argument('--policy', help='reviewed Permission Gate policy')
    args = parser.parse_args(argv)
    try:
        provided = (args.draft, args.observation, args.policy)
        drafts.gate.lens.require(all(provided) or not any(provided),
                                 'provide --draft, --observation and --policy together, or none for the demonstration')
        demonstration = not any(provided)
        observation = drafts.gate.load(args.observation or DEFAULT_OBSERVATION)
        policy = drafts.gate.load(args.policy or DEFAULT_POLICY)
        # The no-argument demo uses the first independently generated candidate;
        # it neither stores a draft nor asks a user for an address.
        candidate = (drafts.build(observation, policy)['drafts'][0]
                     if demonstration else load_draft(args.draft))
        result = witness(candidate, observation, policy)
        result['demonstration'] = demonstration
        print(json.dumps(result, indent=2))
        return 0 if result['matches_reviewed_draft'] else 3
    except (ValueError, KeyError, TypeError, OSError, OverflowError, IndexError,
            json.JSONDecodeError) as exc:
        print(json.dumps({'error': str(exc)}), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
