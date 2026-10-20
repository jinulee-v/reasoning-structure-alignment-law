import unittest

from bobcatlib import minimal


class MinimalSuiteTest(unittest.TestCase):
    def test_narrowing_swaps_a_broad_test_without_losing_coverage(self):
        # Greedy chooses 0 for its three bits, then 1 for the final bit.
        # Once row 1 is present, row 2 is a narrower replacement for row 0.
        masks = [0b1110, 0b0101, 0b1010]
        greedy, covered = minimal._greedy(masks)
        selected, swaps = minimal._narrow([i for i, _gain in greedy], masks)

        self.assertEqual(greedy, [(0, 3), (1, 1)])
        self.assertEqual(covered, 4)
        self.assertEqual(selected, [2, 1])
        self.assertEqual(swaps, [(0, 0, 2)])
        self.assertEqual(masks[selected[0]] | masks[selected[1]], 0b1111)
        self.assertLess(sum(masks[i].bit_count() for i in selected),
                        sum(masks[i].bit_count() for i, _gain in greedy))

    def test_narrowing_rejects_a_smaller_test_that_loses_coverage(self):
        masks = [0b1110, 0b0001, 0b0010]
        selected, swaps = minimal._narrow([0, 1], masks)

        self.assertEqual(selected, [0, 1])
        self.assertEqual(swaps, [])

    def test_narrowing_is_stable_and_deterministic(self):
        masks = [0b1110, 0b0101, 0b1010, 0b1010]
        once, _swaps = minimal._narrow([0, 1], masks)
        twice, second_swaps = minimal._narrow(once, masks)

        self.assertEqual(once, [2, 1])
        self.assertEqual(twice, once)
        self.assertEqual(second_swaps, [])


if __name__ == "__main__":
    unittest.main()
