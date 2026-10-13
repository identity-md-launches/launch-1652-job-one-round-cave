#!/usr/bin/env python3
"""Replay real saved proofs and show fail-closed decisions without inventing trust."""
import json
from pathlib import Path
import code_review as tool


def main():
    here = Path(__file__).resolve().parent
    checks = []
    for token in ('zto', 'imd'):
        bundle = tool.ancestry.read_json(here.parent / 'code-proof' / (token + '-proof.json'))
        review = tool.ancestry.read_json(here / (token + '-review.json'))
        height = int(bundle['observation']['block']['number'], 16)
        result = tool.evaluate(bundle, review, height + 8)
        assert result['identity_matches'] and result['decision'] == 'refuse'
        assert result['reasons'] == ['missing-caller-anchor']
        checks.append({'case': token.upper() + ' historical identity; no independent anchor',
                       'result': result})
    stale = tool.evaluate(bundle, review, height + 9)
    assert stale['reasons'] == ['code-evidence-too-old', 'missing-caller-anchor']
    checks.append({'case': 'IMD one block beyond example age limit', 'result': stale})
    print(json.dumps({'demonstration_passed': True,
                      'example_reviews_are_not_safety_endorsements': True,
                      'reference_heights_are_historical_examples': True,
                      'checks': checks}, indent=2))


if __name__ == '__main__':
    main()
