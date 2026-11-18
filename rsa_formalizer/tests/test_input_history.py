import unittest

from rsa_formalizer.stages.utils.input_history import compact, expand


class InputHistoryTest(unittest.TestCase):
    def test_roundtrip_preserves_missing_null_reserved_keys_and_order(self):
        inputs = [{"attempt": 0, "inputs": {"items": [{"code": "a"}, {"code": "b", "extra": None}]}},
                  {"attempt": 1, "inputs": {"$table": {"$object": [None, True, 4]}}}]
        self.assertEqual(expand(compact(inputs)), inputs)
        self.assertNotEqual(compact([{"x": None}]), compact([{}]))

    def test_roundtrip_handles_unrelated_input_shapes(self):
        for inputs in ([{"ready": True, "steps": 4}, {"ready": False}],
                       [{"relationships": [{"from": "a", "to": "b"}], "date": "2026-01-01"}],
                       [], [None, False, "value", 1], {"$object": []}):
            with self.subTest(inputs=inputs):
                self.assertEqual(expand(compact(inputs)), inputs)


if __name__ == "__main__":
    unittest.main()
