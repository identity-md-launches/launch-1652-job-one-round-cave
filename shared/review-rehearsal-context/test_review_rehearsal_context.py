import copy
import unittest

import review_rehearsal_context as tool


class ReviewRehearsalContextTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.review = tool.load('line-3/tools/code-review/zto-result.json')
        cls.rehearsal = tool.load('line-4/tools/relay-rehearsal/zto-relay-observation.json')

    def test_real_zto_evidence_is_not_silently_combined(self):
        result = tool.assess(self.review, self.rehearsal)
        self.assertEqual(result['verdict'], 'context_mismatch')
        self.assertTrue(result['same_target'])
        self.assertFalse(result['same_block'])
        self.assertFalse(result['coherent'])

    def test_exact_reviewed_context_can_be_coherent(self):
        review, rehearsal = copy.deepcopy(self.review), copy.deepcopy(self.rehearsal)
        review['decision'] = 'accept-identity'
        review['code_block'] = copy.deepcopy(rehearsal['block'])
        result = tool.assess(review, rehearsal)
        self.assertEqual(result['verdict'], 'coherent_reviewed_rehearsal')
        self.assertTrue(result['coherent'])

    def test_target_change_refuses_context(self):
        rehearsal = copy.deepcopy(self.rehearsal)
        rehearsal['call']['to'] = '0xd34a99bc0f67ae1bbd63c660e6d0b0dd03e263b7'
        self.assertEqual(tool.assess(self.review, rehearsal)['verdict'], 'context_mismatch')

    def test_duplicate_json_keys_are_refused(self):
        with self.assertRaisesRegex(ValueError, 'duplicate JSON key'):
            tool.object_no_duplicates([('a', 1), ('a', 2)])


if __name__ == '__main__':
    unittest.main()
