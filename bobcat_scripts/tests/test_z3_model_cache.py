"""Model eligibility must be recomputed when a solver's model changes."""
import ctypes
import unittest

from bobcatlib import paths

LIBRARY = paths.ROOT / '.toolchain/bobcat-z3/lib/libz3.so'


@unittest.skipUnless(LIBRARY.exists(), 'BOBCat Z3 library is not built')
class ModelCacheTests(unittest.TestCase):
    def test_accessor_interpretation_changes_across_push_and_pop(self):
        z3 = ctypes.CDLL(str(LIBRARY))
        ptr = ctypes.c_void_p
        z3.Z3_mk_config.restype = ptr
        z3.Z3_mk_context.argtypes = [ptr]
        z3.Z3_mk_context.restype = ptr
        z3.Z3_del_config.argtypes = [ptr]
        z3.Z3_del_context.argtypes = [ptr]
        z3.Z3_eval_smtlib2_string.argtypes = [ptr, ctypes.c_char_p]
        z3.Z3_eval_smtlib2_string.restype = ctypes.c_char_p
        config = z3.Z3_mk_config()
        context = z3.Z3_mk_context(config)
        z3.Z3_del_config(config)
        try:
            result = z3.Z3_eval_smtlib2_string(context, b'''
                (declare-datatype D ((Mk (field Int)) Empty))
                (declare-const x D)
                (assert (= x (Mk 3)))
                (check-sat) (get-value ((field x)))
                (push) (assert (= (field Empty) 42))
                (check-sat) (get-value ((field Empty))) (pop)
                (push) (assert (= (field Empty) 43))
                (check-sat) (get-value ((field Empty))) (pop)
                (check-sat) (get-value ((field x)))
            ''').decode()
            self.assertEqual(result.count('sat\n'), 4)
            self.assertEqual(result.count('(((field x) 3))'), 2)
            self.assertIn('(((field Empty) 42))', result)
            self.assertIn('(((field Empty) 43))', result)
        finally:
            z3.Z3_del_context(context)
