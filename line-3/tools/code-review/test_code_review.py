"""Real ZTO/IMD replay, adversarial review boundaries, and CLI exit contracts."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import code_review as tool

HERE = Path(__file__).resolve().parent


def bundle(token='zto'):
    return tool.ancestry.read_json(HERE.parent / 'code-proof' / (token + '-proof.json'))


def review(token='zto'):
    return tool.ancestry.read_json(HERE / (token + '-review.json'))


def chain():
    return tool.ancestry.read_json(HERE.parent / 'code-ancestry' / 'zto-ancestry.json')


class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.bundle = bundle()
        self.review = review()
        self.height = int(self.bundle['observation']['block']['number'], 16)
        # This is observed, NOT independently trusted. Exercises equality only.
        self.anchor = self.bundle['observation']['block']['hash']

    def evaluate(self, **kwargs):
        args = dict(bundle=self.bundle, review=self.review,
                    as_of_block=self.height, anchor_hash=self.anchor)
        args.update(kwargs)
        return tool.evaluate(**args)

    def test_real_tokens_match_but_without_anchor_refuse(self):
        for token in ('zto', 'imd'):
            result = tool.evaluate(bundle(token), review(token), self.height)
            self.assertTrue(result['identity_matches'])
            self.assertEqual(result['decision'], 'refuse')
            self.assertEqual(result['reasons'], ['missing-caller-anchor'])
            self.assertFalse(result['anchor_hash_matched'])

    def test_explicit_hash_matches_not_authentication(self):
        result = self.evaluate()
        self.assertEqual(result['decision'], 'accept-identity')
        self.assertTrue(result['anchor_hash_matched'])
        self.assertFalse(result['anchor_authenticity_verified'])
        self.assertFalse(result['consensus_verified'])

    def test_wrong_anchor_fails_before_verdict(self):
        with self.assertRaisesRegex(ValueError, 'independent block hash'):
            self.evaluate(anchor_hash=tool.lens.digest(b'wrong checkpoint'))

    def test_same_hash_at_wrong_target_refused(self):
        self.review['target'] = tool.lens.IMD
        self.review['path'][0]['address'] = tool.lens.IMD
        result = self.evaluate()
        self.assertFalse(result['identity_matches'])
        self.assertIn('reviewed-identity-mismatch', result['reasons'])
        self.assertEqual(len(result['differences']), 2)

    def test_wrong_reviewed_hash_refused(self):
        self.review['path'][0]['code_hash'] = tool.lens.digest(b'different reviewed runtime')
        self.assertIn('reviewed-identity-mismatch', self.evaluate()['reasons'])

    def test_slots_are_part_of_review(self):
        self.review['path'][0]['storage']['implementation'] = '0x' + tool.lens.IMD[2:].rjust(64, '0')
        self.assertFalse(self.evaluate()['identity_matches'])

    def test_age_boundary_and_zero_limit(self):
        self.assertEqual(self.evaluate(as_of_block=self.height + 8)['decision'], 'accept-identity')
        self.assertIn('code-evidence-too-old', self.evaluate(as_of_block=self.height + 9)['reasons'])
        self.review['max_age_blocks'] = 0
        self.assertEqual(self.evaluate()['decision'], 'accept-identity')
        self.assertEqual(self.evaluate(as_of_block=self.height + 1)['reasons'], ['code-evidence-too-old'])

    def test_future_evidence_and_invalid_age_types(self):
        for reference in (self.height - 1, True, -1, 1.0, '26185280', 2**64):
            with self.subTest(reference=reference), self.assertRaises(ValueError):
                self.evaluate(as_of_block=reference)
        for limit in (True, -1, 1.0, '8', 2**64):
            self.review['max_age_blocks'] = limit
            with self.subTest(limit=limit), self.assertRaises(ValueError):
                self.evaluate()

    def test_ancestry_does_not_refresh_old_code(self):
        result = self.evaluate(chain=chain(), anchor_hash=chain()['checkpoint']['hash'],
                               as_of_block=self.height + 8)
        self.assertEqual(result['decision'], 'accept-identity')
        self.assertEqual(result['parent_links_verified'], 8)
        self.assertEqual(result['code_age_blocks'], 8)
        self.review['max_age_blocks'] = 7
        self.assertEqual(self.evaluate(chain=chain(), anchor_hash=chain()['checkpoint']['hash'],
                         as_of_block=self.height + 8)['reasons'], ['code-evidence-too-old'])

    def test_reference_cannot_precede_checkpoint(self):
        with self.assertRaisesRegex(ValueError, 'precedes evidence checkpoint'):
            self.evaluate(chain=chain(), anchor_hash=chain()['checkpoint']['hash'])

    def test_missing_or_tampered_proof_never_matches(self):
        self.bundle['proofs'][0]['accountProof'].pop()
        with self.assertRaises(ValueError):
            self.evaluate()

    def test_forged_runtime_with_consistent_report_is_not_a_proof(self):
        node = self.bundle['observation']['nodes'][0]
        node.update(code='0x6000', code_bytes=2, code_hash=tool.lens.digest(b'\x60\x00'))
        self.bundle['observation']['effective_code_hash'] = node['code_hash']
        self.bundle['proofs'][0]['codeHash'] = node['code_hash']
        self.review['path'][0]['code_hash'] = node['code_hash']
        with self.assertRaisesRegex(ValueError, 'proven code hash'):
            self.evaluate()

    def test_unknown_review_fields_cannot_weaken_checks(self):
        for key in ('allow_unanchored', 'trusted', 'ignore_age', 'anchor_hash'):
            r = copy.deepcopy(self.review)
            r[key] = True
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'extra review'):
                self.evaluate(review=r)
        self.review['path'][0]['ignore_slots'] = True
        with self.assertRaisesRegex(ValueError, 'extra review node'):
            self.evaluate()

    def test_wrong_chain_and_missing_fields(self):
        for chain_id in (True, 8453, '1'):
            r = copy.deepcopy(self.review)
            r['chain_id'] = chain_id
            with self.assertRaisesRegex(ValueError, 'chain'):
                self.evaluate(review=r)
        for key in self.review:
            r = copy.deepcopy(self.review)
            del r[key]
            with self.assertRaises(ValueError):
                self.evaluate(review=r)

    def test_path_cannot_omit_middle_or_repeat_address(self):
        # Shape tests use the real addresses but do not claim observed proxy routing.
        first = copy.deepcopy(self.review['path'][0])
        first.update(kind='eip1967-implementation-candidate', next_address=tool.lens.IMD)
        second = copy.deepcopy(first)
        second.update(address=tool.lens.IMD, kind='no-supported-proxy-signal', next_address=None)
        self.review['path'] = [first, second]
        self.assertFalse(self.evaluate()['identity_matches'])
        for path in ([], [first], [first, first], [second, first]):
            self.review['path'] = path
            with self.assertRaises(ValueError):
                self.evaluate()

    def test_beacon_even_with_exact_review_and_anchor_is_refused(self):
        sys.path.insert(0, str(HERE.parent / 'code-proof'))
        from test_code_proof import synthetic_beacon_bundle
        b = synthetic_beacon_bundle()
        r = copy.deepcopy(self.review)
        r['path'] = tool.observed_path(b['observation'])
        result = self.evaluate(bundle=b, review=r, anchor_hash=b['observation']['block']['hash'])
        self.assertTrue(result['identity_matches'])
        self.assertEqual(result['reasons'], ['unproven-beacon-routing'])

    def test_case_normalization_and_review_fingerprint(self):
        original = self.evaluate()
        node = self.review['path'][0]
        for key in ('address', 'code_hash'):
            node[key] = '0x' + node[key][2:].upper()
        result = self.evaluate()
        self.assertEqual(result['decision'], 'accept-identity')
        self.assertEqual(result['review_digest'], original['review_digest'])
        self.review['max_age_blocks'] += 1
        self.assertNotEqual(self.evaluate()['review_digest'], original['review_digest'])

    def test_cli_exit_codes_and_no_partial_error_json(self):
        args = [sys.executable, '-B', str(HERE / 'code_review.py'),
                '--bundle', str(HERE.parent / 'code-proof' / 'zto-proof.json'),
                '--review', str(HERE / 'zto-review.json'), '--as-of-block', str(self.height)]
        for extra, code in (([], 3), (['--anchor-hash', self.anchor], 0),
                            (['--anchor-hash', tool.lens.digest(b'wrong')], 1)):
            run = subprocess.run(args + extra, capture_output=True, text=True, timeout=20)
            self.assertEqual(run.returncode, code, run.stderr)
            if code == 1:
                self.assertEqual(run.stdout, '')
            else:
                self.assertEqual(json.loads(run.stdout)['decision'], 'accept-identity' if code == 0 else 'refuse')

    def test_duplicate_keys_and_workspace_escape_refused(self):
        scratch = Path.cwd() / 'test' / 'scratch'
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as directory:
            path = Path(directory) / 'review.json'
            path.write_text('{"chain_id": 1, "chain_id": 2}')
            with self.assertRaisesRegex(ValueError, 'duplicate JSON'):
                tool.ancestry.read_json(path)
            path.unlink()
            path.symlink_to(Path.cwd().parent / 'never-read')
            with self.assertRaisesRegex(ValueError, 'inside workspace'):
                tool.ancestry.read_json(path)


if __name__ == '__main__':
    unittest.main()
