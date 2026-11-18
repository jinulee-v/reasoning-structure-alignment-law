from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from rsa_formalizer.stages.utils.catala import toolchain_environment
from rsa_formalizer.stages.validation import verification


class NativeMoneyToleranceTest(unittest.TestCase):
    def test_other_assertions_are_unchanged(self) -> None:
        source = (
            "  assertion count = 3\n"
            "  assertion flag = true\n"
            "  assertion actual >= (money of 100)\n"
        )
        self.assertEqual(verification.money_assertions_with_tolerance(source), source)

    def test_policy_invalidates_exact_equality_cache(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fingerprint = verification.verification_fingerprint(root, root)
        self.assertNotEqual(fingerprint["runner"], "native-catala-v1")
        self.assertEqual(
            fingerprint["money_tolerance"], {"absolute": "1", "exclusive": True}
        )

    def test_catala_money_boundaries_and_integer_equality(self) -> None:
        environment = toolchain_environment({})
        clerk = shutil.which("clerk", path=environment["PATH"])
        if not clerk:
            self.skipTest("Catala toolchain is not installed")
        cases = {
            "Exact": ("money", "$100", True),
            "InsideAbove": ("money", "$100.99", True),
            "InsideBelow": ("money", "$99.01", True),
            "BoundaryAbove": ("money", "$101", False),
            "BoundaryBelow": ("money", "$99", False),
            "Outside": ("money", "$101.01", False),
            "IntegerMismatch": ("integer", "101", False),
        }
        blocks = []
        for name, (kind, value, _) in cases.items():
            expected = "(money of 100)" if kind == "money" else "100"
            blocks.append(
                "```catala\n#[test]\n"
                f"declaration scope {name}:\n  output actual content {kind}\n"
                f"scope {name}:\n  definition actual equals {value}\n"
                f"  assertion actual = {expected}\n```\n"
            )
        with tempfile.TemporaryDirectory(prefix="rsa-money-tolerance-") as directory:
            root = Path(directory)
            (root / "Case.catala_en").write_text(
                verification.money_assertions_with_tolerance("\n".join(blocks))
            )
            subprocess.run(
                [clerk, "start", "--color=never"], cwd=root, env=environment,
                capture_output=True, text=True, check=True, timeout=60,
            )
            result = subprocess.run(
                [clerk, "test", "Case.catala_en", "--json", "--color=never"],
                cwd=root, env=environment, capture_output=True, text=True, timeout=60,
            )
        report = verification._json_report(result.stdout)
        self.assertIsNotNone(report, result.stdout + result.stderr)
        observed = {
            test["scope_name"]: test["success"]
            for file in report["test-results"]
            for test in file["tests"]["scopes"]
        }
        self.assertEqual(observed, {name: case[2] for name, case in cases.items()})


if __name__ == "__main__":
    unittest.main()
