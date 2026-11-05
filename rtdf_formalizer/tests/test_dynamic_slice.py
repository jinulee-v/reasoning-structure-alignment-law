"""Dependency closure invariants and real compiler/bridge branch checks."""

import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from rtdf_formalizer.stages import utils as experiment
from rtdf_formalizer.bobcat import trace as pipeline
from rtdf_formalizer.bobcat import compiled_json


class DynamicSliceTest(unittest.TestCase):
    def test_minimal_closure_keeps_occurrences_and_controls(self):
        def var(i, name, reads):
            return dict(
                kind="variable",
                name=name,
                definition_id=i,
                reads=[dict(definition_id=r) for r in reads],
                children=[],
            )

        tree = [
            dict(
                kind="call",
                name="Answer",
                children=[
                    var(0, "Answer.condition", []),
                    dict(
                        kind="call",
                        name="Helper",
                        children=[var(1, "Helper.value", [])],
                    ),
                    dict(
                        kind="call",
                        name="Helper",
                        children=[var(2, "Helper.value", [])],
                    ),
                    var(3, "Answer.total", [0, 2]),
                ],
            )
        ]
        sliced = pipeline.slice_execution_tree(tree, "Answer", "total", {})

        def ids(nodes):
            return [n["definition_id"] for n in nodes if n["kind"] == "variable"] + [
                i for n in nodes for i in ids(n.get("children", []))
            ]

        self.assertEqual(set(ids(sliced)), {0, 2, 3})
        self.assertEqual(len(sliced[0]["children"]), 4)
        # Every retained non-root occurrence is required by another live one.
        self.assertEqual(
            pipeline.slice_execution_tree(sliced, "Answer", "total", {}), sliced
        )

    def test_rejects_missing_or_dangling_provenance(self):
        tree = [dict(kind="variable", name="Answer.total", children=[])]
        with self.assertRaisesRegex(ValueError, "metadata missing"):
            pipeline.slice_execution_tree(tree, "Answer", "total", {})
        tree[0].update(definition_id=1, reads=[dict(definition_id=0)])
        with self.assertRaisesRegex(ValueError, "invalid reaching"):
            pipeline.slice_execution_tree(tree, "Answer", "total", {})

    def test_rejects_merged_duplicate_and_forward_occurrences(self):
        root = dict(
            kind="variable", name="Answer.total", definition_id=1, reads=[], children=[]
        )
        for tree, message in [
            ([{**root, "occurrences": 2}], "merged runtime"),
            ([root, dict(root)], "duplicate runtime"),
            ([{**root, "reads": [dict(definition_id=1)]}], "invalid reaching"),
            ([{**root, "reads": [dict(definition_id="0")]}], "invalid runtime read"),
            ([{**root, "reads": [None]}], "invalid runtime read"),
            ([], "expected one entry output"),
        ]:
            with (
                self.subTest(message=message),
                self.assertRaisesRegex(ValueError, message),
            ):
                pipeline.slice_execution_tree(tree, "Answer", "total")

    def test_preserves_only_live_definition_decisions(self):
        def definition(i, name, reads):
            return dict(
                kind="variable",
                name=name,
                definition_id=i,
                reads=[dict(definition_id=r) for r in reads],
                children=[],
            )

        tree = [
            dict(
                kind="call",
                name="Answer",
                children=[
                    dict(kind="decision", pos=dict(start_line=1), children=[]),
                    definition(0, "Answer.unused", []),
                    dict(kind="decision", pos=dict(start_line=2), children=[]),
                    definition(1, "Answer.total", []),
                ],
            )
        ]
        sliced = pipeline.slice_execution_tree(tree, "Answer", "total")
        self.assertEqual(sliced[0]["children"], tree[0]["children"][2:])
        # The caller's decision must stay before the contributing nested call.
        tree[0]["children"].insert(
            3,
            dict(
                kind="call", name="Helper", children=[definition(1, "Helper.value", [])]
            ),
        )
        tree[0]["children"][-1].update(definition_id=2, reads=[dict(definition_id=1)])
        sliced = pipeline.slice_execution_tree(tree, "Answer", "total")
        self.assertEqual(sliced[0]["children"], tree[0]["children"][2:])

    def test_compiled_branch_controls_and_selected_data(self):
        environment = experiment.toolchain_environment({"runtime": {}})
        if any(
            shutil.which(t, path=environment["PATH"]) is None
            for t in ("catala", "clerk", "ocamlfind", "ocamlobjinfo")
        ):
            self.skipTest("Catala toolchain unavailable")
        source = """```catala
declaration scope Choice:
  input choose content boolean
  input amount content integer
  internal predicate content boolean
  internal left content integer
  internal right content integer
  output result content integer

scope Choice:
  definition predicate equals choose
  definition left equals amount + 10
  definition right equals amount + 20
  definition result equals if predicate then left else right
```
"""
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            (project / "choice.catala_en").write_text(source)
            formats = experiment.extract_input_formats(
                project, environment=environment, timeout=60
            )
            errors = compiled_json.build_bridges(
                project, formats, environment=environment, timeout=60
            )
            self.assertEqual(errors, {})
            executable = compiled_json.compiled_path(
                project, "choice.catala_en", "Choice"
            )
            for choose, kept, discarded, expected in [
                (True, "left", "right", 11),
                (False, "right", "left", 21),
            ]:
                result = subprocess.run(
                    [str(executable), "Choice", "--trace"],
                    input=json.dumps(dict(choose=choose, amount=1)) + "\n",
                    text=True,
                    capture_output=True,
                    cwd=project,
                    env=environment,
                    timeout=30,
                    check=True,
                )
                observed = json.loads(result.stdout)
                self.assertEqual(
                    observed["dependency_semantics"],
                    pipeline.DYNAMIC_SLICE_DEPENDENCY_SEMANTICS,
                )
                self.assertEqual(int(observed["result"]["result"]), expected)
                tree = pipeline.execution_tree(observed["events"], deduplicate=False)
                sliced = pipeline.slice_execution_tree(tree, "Choice", "result", {})
                rendered = json.dumps(sliced)
                self.assertIn("Choice.predicate", rendered)
                self.assertIn("Choice." + kept, rendered)
                self.assertNotIn("Choice." + discarded, rendered)

    def test_compiled_optional_and_repeated_calls(self):
        environment = experiment.toolchain_environment({"runtime": {}})
        if any(
            shutil.which(t, path=environment["PATH"]) is None
            for t in ("catala", "clerk", "ocamlfind", "ocamlobjinfo")
        ):
            self.skipTest("Catala toolchain unavailable")
        source = """```catala
declaration scope Helper:
  input amount content integer
  output doubled content integer
scope Helper:
  definition doubled equals amount * 2

declaration scope Forwarded:
  input amount content integer
  internal incremented content integer
  internal helper content Helper
  output result content integer
scope Forwarded:
  definition incremented equals amount + 1
  definition helper equals output of Helper with { -- amount: incremented }
  definition result equals helper.doubled

declaration scope Repeated:
  input choose content boolean
  internal first content Helper
  internal second content Helper
  output result content integer
scope Repeated:
  definition first equals output of Helper with { -- amount: 3 }
  definition second equals output of Helper with { -- amount: 7 }
  definition result equals if choose then first.doubled else second.doubled

declaration structure Facts:
  data value content optional of integer
declaration scope OptionalChoice:
  input facts content Facts
  internal maybe content optional of integer
  internal increment content integer
  internal fallback content integer
  output result content integer
scope OptionalChoice:
  definition maybe equals facts.value
  definition increment equals 10
  definition fallback equals 20
  definition result equals
    match maybe with pattern
    -- Present content x: x + increment
    -- Absent: fallback

declaration scope ShortCircuit:
  input choose content boolean
  internal first_guard content boolean
  internal second_guard content boolean
  internal left content integer
  internal right content integer
  output result content integer
scope ShortCircuit:
  definition first_guard equals choose
  definition second_guard equals not choose
  definition left equals 1
  definition right equals 2
  definition result equals if first_guard or second_guard then left else right
```
"""

        def variables(nodes):
            return [n for n in nodes if n["kind"] == "variable"] + [
                v for n in nodes for v in variables(n.get("children", []))
            ]

        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            (project / "examples.catala_en").write_text(source)
            formats = experiment.extract_input_formats(
                project, environment=environment, timeout=60
            )
            errors = compiled_json.build_bridges(
                project, formats, environment=environment, timeout=60
            )
            self.assertEqual(errors, {})
            cases = [
                ("Forwarded", dict(amount=5), 12, "incremented", None),
                ("Repeated", dict(choose=True), 6, "first", "second"),
                ("Repeated", dict(choose=False), 14, "second", "first"),
                ("OptionalChoice", dict(facts={}), 20, "fallback", "increment"),
                (
                    "OptionalChoice",
                    dict(facts=dict(value=None)),
                    20,
                    "fallback",
                    "increment",
                ),
                (
                    "OptionalChoice",
                    dict(facts=dict(value=5)),
                    15,
                    "increment",
                    "fallback",
                ),
                ("ShortCircuit", dict(choose=True), 1, "first_guard", "second_guard"),
                ("ShortCircuit", dict(choose=False), 1, "second_guard", "right"),
            ]
            for scope, inputs, expected, kept, discarded in cases:
                with self.subTest(scope=scope, inputs=inputs):
                    executable = compiled_json.compiled_path(
                        project, "examples.catala_en", scope
                    )
                    process = subprocess.run(
                        [str(executable), scope, "--trace"],
                        input=json.dumps(inputs) + "\n",
                        text=True,
                        capture_output=True,
                        cwd=project,
                        env=environment,
                        timeout=30,
                        check=True,
                    )
                    observed = json.loads(process.stdout)
                    self.assertEqual(int(observed["result"]["result"]), expected)
                    tree = pipeline.execution_tree(
                        observed["events"], deduplicate=False
                    )
                    sliced = pipeline.slice_execution_tree(tree, scope, "result")
                    rendered = json.dumps(sliced)
                    self.assertIn(scope + "." + kept, rendered)
                    if discarded is not None:
                        self.assertNotIn(scope + "." + discarded, rendered)
                    if scope == "OptionalChoice":
                        self.assertIn("OptionalChoice.maybe", rendered)
                    elif scope in {"Repeated", "Forwarded"}:
                        original = [
                            v for v in variables(tree) if v["name"] == "Helper.doubled"
                        ]
                        retained = [
                            v
                            for v in variables(sliced)
                            if v["name"] == "Helper.doubled"
                        ]
                        self.assertEqual(len(original), 2 if scope == "Repeated" else 1)
                        self.assertEqual(len(retained), 1)
                        self.assertEqual(int(retained[0]["value"]), expected)
                        if scope == "Forwarded":
                            self.assertTrue(retained[0]["reads"])
                    else:
                        self.assertIn("ShortCircuit.first_guard", rendered)
                        self.assertIn("ShortCircuit.left", rendered)
                        self.assertNotIn("ShortCircuit.right", rendered)


if __name__ == "__main__":
    unittest.main()
