import sys
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cutecatlib import entrypoints, identifiers, values


class UnicodeIdentifierTests(unittest.TestCase):
    def test_printed_cjk_value(self):
        value = values.parse("{ 資料 欄位 = 選項; 人數 = 2; }")
        self.assertEqual(value.as_json(), {
            "struct": "資料",
            "fields": {"欄位": {"cons": "選項"}, "人數": 2},
        })

    def test_all_unicode_xid_scripts_and_combining_marks(self):
        # The accent in the second name is a separate combining code point.
        names = ["Éligibilité", "E\u0301ligibilite\u0301", "расчёт", "資料", "l'enfant"]
        for name in names:
            with self.subTest(name=name):
                self.assertTrue(identifiers.is_identifier(name))
                value = values.parse(f"{{ {name} résultat = true; }}")
                self.assertEqual(value.as_json()["struct"], name)
        self.assertTrue(identifiers.is_qualified_identifier("Модуль.資料"))
        self.assertFalse(identifiers.is_identifier("1資料"))
        self.assertFalse(identifiers.is_identifier("_資料"))

    def test_entrypoint_scan_and_wrapper_qualification(self):
        source = """> Module Example

declaration structure É資料:
  data 人數 content integer

declaration scope 範圍:
  input 輸入 content É資料
  output 結果 content É資料

declaration расчёт content É資料
  depends on 輸入 content É資料
  equals 輸入
"""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "Example.catala_en"
            path.write_text(source)
            port = entrypoints.scan(Path(tmp))

        self.assertEqual(
            [(s.kind, s.name, s.params) for s in port.entries],
            [("scope", "範圍", [("輸入", "É資料")]),
             ("function", "расчёт", [("輸入", "É資料")])],
        )
        wrapper = entrypoints.harness_for(
            port, "Example.catala_en",
            [s for s in port.entries if s.kind == "function"])
        self.assertIn("declaration scope FnРасчёт:", wrapper)
        self.assertIn("input 輸入 content Src.É資料", wrapper)
        self.assertIn("output result content Src.É資料", wrapper)


if __name__ == "__main__":
    unittest.main()
