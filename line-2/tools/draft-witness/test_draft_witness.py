import copy
import unittest

import draft_witness as witness

drafts = witness.drafts


class DraftWitnessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.observation = drafts.gate.load(witness.DEFAULT_OBSERVATION)
        cls.policy = drafts.gate.load(witness.DEFAULT_POLICY)
        cls.real = drafts.build(cls.observation, cls.policy)['drafts'][0]

    def test_real_candidate_matches_exactly(self):
        report = witness.witness(self.real, self.observation, self.policy)
        self.assertTrue(report['matches_reviewed_draft'])
        self.assertEqual(report['status'], 'exact_match')
        self.assertEqual(report['candidate_count'], 3)

    def test_changed_calldata_cannot_match(self):
        changed = copy.deepcopy(self.real)
        changed['transaction']['data'] = changed['transaction']['data'][:-1] + '1'
        report = witness.witness(changed, self.observation, self.policy)
        self.assertFalse(report['matches_reviewed_draft'])
        self.assertEqual(report['status'], 'not_a_reviewed_candidate')

    def test_added_fee_field_cannot_match(self):
        changed = copy.deepcopy(self.real)
        changed['transaction']['gas'] = '0x1'
        report = witness.witness(changed, self.observation, self.policy)
        self.assertFalse(report['matches_reviewed_draft'])

    def test_old_evidence_cannot_produce_a_witness(self):
        policy = copy.deepcopy(self.policy)
        policy['minimum_block'] += 1
        policy['maximum_block'] += 1
        report = witness.witness(self.real, self.observation, policy)
        self.assertFalse(report['matches_reviewed_draft'])
        self.assertEqual(report['status'], 'no_candidate_from_insufficient_evidence')


if __name__ == '__main__':
    unittest.main()
