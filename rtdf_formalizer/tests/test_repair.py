from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from rtdf_formalizer.stages import utils as exp
from rtdf_formalizer.stages.reasoning_trace_diff_fuzzing import repair
from rtdf_formalizer.bobcat import compiled_json
from rtdf_formalizer.main import argument_parser
from rtdf_formalizer.stages.reasoning_trace_diff_fuzzing.repair import (
    bundle_report,
    replay,
)
from rtdf_formalizer.stages.reasoning_trace_diff_fuzzing.repair import (
    recursive as recursive_repair,
)


SCHEMA = {
    "type": "object",
    "properties": {
        "tax": {"$ref": "#/definitions/money"},
        "unrelated": {"type": "integer"},
    },
    "required": ["tax", "unrelated"],
    "definitions": {"money": {"type": "number", "title": "Catala Money"}},
}


class RepairTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.run = Path(self.temporary.name)
        (self.run / "workspace").mkdir()

    def state(self, stage="agent"):
        return {
            "recursive_phase": "initial",
            "next_stage": stage,
            "status": "running",
            "completed_stages": [],
        }

    def test_cli_exposes_only_recursive_workflow(self):
        parser = argument_parser()
        start = parser._subparsers._group_actions[0].choices["start"]
        self.assertFalse(any(item.dest == "repair_mode" for item in start._actions))
        self.assertEqual(start.get_default("max_scope_revisions"), 2)
        self.assertEqual(start.get_default("repair_scope_selection"), "all")
        self.assertEqual(start.get_default("reasoning_jobs"), 8)
        with self.assertRaisesRegex(exp.RunnerError, "must be"):
            repair.max_revisions_per_scope(
                {"repair": {"max_revisions_per_scope": -1}}
            )

    def test_entry_scope_selection_keeps_only_graph_roots(self):
        leaf = {"id": "law::Leaf", "dependencies": []}
        top = {"id": "Api::Top", "dependencies": ["law::Leaf"]}
        other = {"id": "Api::Other", "dependencies": []}

        selected = repair.selected_repair_plan(
            [leaf, top, other], {"repair": {"scope_selection": "entry"}}
        )

        self.assertEqual(
            [record["id"] for record in selected], [top["id"], other["id"]]
        )
        self.assertEqual(selected[0]["dependencies"], ["law::Leaf"])

        selected = repair.selected_repair_plan(
            [leaf, top, other],
            {"repair": {"scope_selection": "entry"}},
            {top["id"]},
        )
        self.assertEqual([record["id"] for record in selected], [top["id"]])

    def test_scope_discovery_resolves_compiler_filename_case(self):
        project = self.run / "project"
        project.mkdir()
        (project / "airlinepolicy.catala_en").write_text("", encoding="utf-8")
        scopes = [
            {
                "file": "AirlinePolicy.catala_en",
                "compiler_file": "AirlinePolicy.catala_en",
                "scope": "Policy",
            }
        ]
        completed = mock.Mock(stdout="{}")
        with mock.patch.object(shutil, "which", return_value="catala"), mock.patch.object(
            exp, "run_checked", return_value=completed
        ) as run_checked:
            plan = repair.discover_scope_order(project, scopes, {})

        self.assertEqual(run_checked.call_args.args[0][2], "airlinepolicy.catala_en")
        self.assertEqual(plan[0]["source"], "airlinepolicy.catala_en")

    def test_full_plan_can_back_entry_only_queue(self):
        leaf = {"id": "law::Leaf", "dependencies": []}
        top = {"id": "Api::Top", "dependencies": [leaf["id"]]}
        state = {}
        repair.install_plan(state, [leaf, top])
        selected = repair.selected_repair_plan(
            [leaf, top], {"repair": {"scope_selection": "entry"}}, {top["id"]}
        )
        state["recursive_selected_scope_ids"] = [row["id"] for row in selected]
        state["recursive_repair_queue"] = list(state["recursive_selected_scope_ids"])

        self.assertEqual([row["id"] for row in state["recursive_repair_plan"]], [leaf["id"], top["id"]])
        self.assertEqual(state["recursive_repair_queue"], [top["id"]])

    def test_recursive_prompt_localizes_changes(self):
        prompt = repair.prompt(
            "initial",
            {"scope": "Leaf", "source": "law.catala_en"},
        )
        self.assertIn("Keep changes minimal and localized to the target scope", prompt)
        self.assertIn("smallest necessary external change", prompt)
        self.assertIn("at most twice in this revision", prompt)
        self.assertIn("do not make another semantic or interface edit", prompt)
        self.assertIn("llm_oracle_complete true", prompt)
        self.assertIn("must not improve its evidence score", prompt)

    def test_agent_regeneration_is_limited_to_two_calls_per_revision(self):
        record = {"id": "law::Top", "source": "law.catala_en", "scope": "Top"}
        state = {
            "recursive_step": "session",
            "recursive_active_scope": record["id"],
            "recursive_revision": 0,
            "recursive_repair_plan": [record],
        }
        parent = repair.scope_revision_root(self.run, state) / "agent_regeneration"
        (parent / "000").mkdir(parents=True)
        (parent / "001").mkdir()

        with self.assertRaisesRegex(exp.RunnerError, "limited to two"):
            repair.regenerate_active_scope(self.run, {}, state)

    def test_copy_cache_excludes_build_directories(self):
        source = self.run / "source"
        destination = self.run / "destination"
        tests = source / "tests_bobcat"
        natural = source / "tests_bobcat_natural_language_results"
        (tests / "build").mkdir(parents=True)
        (tests / "nested" / "_build").mkdir(parents=True)
        natural.mkdir(parents=True)
        (tests / "cases.json").write_text("{}", encoding="utf-8")
        (tests / "build" / "readonly.cmi").write_text("compiled", encoding="utf-8")
        (tests / "nested" / "_build" / "generated").write_text(
            "generated", encoding="utf-8"
        )
        (natural / "case.txt").write_text("reasoning", encoding="utf-8")
        destination.mkdir()

        repair._copy_cache(source, destination)

        self.assertTrue((destination / "tests_bobcat/cases.json").is_file())
        self.assertFalse((destination / "tests_bobcat/build").exists())
        self.assertFalse((destination / "tests_bobcat/nested/_build").exists())
        self.assertTrue(
            (
                destination / "tests_bobcat_natural_language_results/case.txt"
            ).is_file()
        )
        self.assertEqual(list(destination.glob(".tests_bobcat.*")), [])

    def test_copy_cache_does_not_publish_failed_copy(self):
        source = self.run / "source"
        destination = self.run / "destination"
        (source / "tests_bobcat").mkdir(parents=True)
        destination.mkdir()

        with mock.patch.object(shutil, "copytree", side_effect=OSError("failed")):
            with self.assertRaisesRegex(OSError, "failed"):
                repair._copy_cache(source, destination)

        self.assertFalse((destination / "tests_bobcat").exists())
        self.assertEqual(list(destination.glob(".tests_bobcat.*")), [])

    def test_result_uses_latest_regenerated_analysis(self):
        identifier = "law::Leaf"
        record = {"id": identifier, "source": "law", "scope": "Leaf"}
        state = {
            "recursive_step": "result",
            "recursive_active_scope": identifier,
            "recursive_revision": 1,
            "recursive_repair_plan": [record],
            "recursive_before_schema_fingerprint": "schema",
        }
        root = self.run / "result"
        snapshot = root / "snapshot"
        snapshot.mkdir(parents=True)
        (snapshot / "law.catala_en").write_text("fixed", encoding="utf-8")
        analysis = recursive_repair.scope_revision_root(self.run, state) / "analysis"
        (analysis / "snapshot").mkdir(parents=True)
        (analysis / "snapshot/law.catala_en").write_text(
            "before", encoding="utf-8"
        )
        regenerated = self.run / "regenerated"
        regenerated.mkdir()
        state["recursive_latest_regeneration"] = {
            "scope": identifier,
            "revision": 1,
            "schema_fingerprint": "schema",
            "workspace_fingerprint": exp.tree_hash(snapshot),
            "analysis_path": "regenerated",
        }

        cached, schema = repair._analysis_cache(
            self.run, state, root, "schema"
        )

        self.assertEqual(cached, regenerated)
        self.assertEqual(schema, "schema")

    def test_result_reuses_latest_evidence_after_semantic_edit(self):
        identifier = "law::Leaf"
        record = {"id": identifier, "source": "law", "scope": "Leaf"}
        state = {
            "recursive_step": "result",
            "recursive_active_scope": identifier,
            "recursive_revision": 1,
            "recursive_repair_plan": [record],
            "recursive_before_schema_fingerprint": "schema",
        }
        root = self.run / "result"
        snapshot = root / "snapshot"
        snapshot.mkdir(parents=True)
        (snapshot / "law.catala_en").write_text("newer edit", encoding="utf-8")
        analysis = recursive_repair.scope_revision_root(self.run, state) / "analysis"
        (analysis / "snapshot").mkdir(parents=True)
        (analysis / "snapshot/law.catala_en").write_text(
            "before", encoding="utf-8"
        )
        regenerated = self.run / "regenerated"
        regenerated.mkdir()
        prior = self.run / "prior"
        prior.mkdir()
        (prior / "law.catala_en").write_text("fixed", encoding="utf-8")
        state["recursive_latest_regeneration"] = {
            "scope": identifier,
            "revision": 1,
            "schema_fingerprint": "schema",
            "workspace_fingerprint": exp.tree_hash(prior),
            "analysis_path": "regenerated",
        }

        cached, schema = repair._analysis_cache(
            self.run, state, root, "schema"
        )

        self.assertEqual(cached, regenerated)
        self.assertEqual(schema, "schema")

    def test_result_regenerates_after_interface_change(self):
        identifier = "law::Leaf"
        record = {"id": identifier, "source": "law", "scope": "Leaf"}
        state = {
            "recursive_step": "result",
            "recursive_active_scope": identifier,
            "recursive_revision": 0,
            "recursive_repair_plan": [record],
            "recursive_before_schema_fingerprint": "old-schema",
        }
        analysis = recursive_repair.scope_revision_root(self.run, state) / "analysis"
        (analysis / "snapshot").mkdir(parents=True)
        root = self.run / "result"
        (root / "snapshot").mkdir(parents=True)

        cached, schema = repair._analysis_cache(
            self.run, state, root, "new-schema"
        )

        self.assertIsNone(cached)
        self.assertIsNone(schema)

    def test_result_reuses_original_analysis_without_edits(self):
        identifier = "law::Leaf"
        record = {"id": identifier, "source": "law", "scope": "Leaf"}
        state = {
            "recursive_step": "result",
            "recursive_active_scope": identifier,
            "recursive_revision": 0,
            "recursive_repair_plan": [record],
            "recursive_before_schema_fingerprint": "schema",
        }
        analysis = recursive_repair.scope_revision_root(self.run, state) / "analysis"
        (analysis / "snapshot").mkdir(parents=True)
        (analysis / "snapshot/law.catala_en").write_text(
            "unchanged", encoding="utf-8"
        )
        root = self.run / "result"
        exp.publish_copy(analysis / "snapshot", root / "snapshot")

        cached, schema = repair._analysis_cache(
            self.run, state, root, "schema"
        )

        self.assertEqual(cached, analysis)
        self.assertEqual(schema, "schema")

    def test_recursive_scope_order_is_dependency_first(self):
        scopes = [
            {"compiler_file": "api", "scope": "Top"},
            {"compiler_file": "law", "scope": "LeafB"},
            {"compiler_file": "law", "scope": "LeafA"},
            {"compiler_file": "law", "scope": "Middle"},
        ]
        sid = recursive_repair.scope_id
        dependencies = {
            sid("api", "Top"): {sid("law", "Middle")},
            sid("law", "Middle"): {sid("law", "LeafA"), sid("law", "LeafB")},
        }
        plan = recursive_repair.topological_scope_order(scopes, dependencies)
        self.assertEqual(
            [item["scope"] for item in plan], ["LeafA", "LeafB", "Middle", "Top"]
        )

    def test_recursive_scope_order_follows_entry_execution_order(self):
        scopes = [
            {"compiler_file": "api", "scope": "Top"},
            {"compiler_file": "law", "scope": "LateLeaf"},
            {"compiler_file": "law", "scope": "EarlyParent"},
            {"compiler_file": "law", "scope": "EarlyLeaf"},
        ]
        sid = recursive_repair.scope_id
        top = sid("api", "Top")
        early_parent = sid("law", "EarlyParent")
        early_leaf = sid("law", "EarlyLeaf")
        late_leaf = sid("law", "LateLeaf")
        dependencies = {
            top: {late_leaf, early_parent},
            early_parent: {early_leaf},
        }
        plan = recursive_repair.topological_scope_order(
            scopes,
            dependencies,
            {top: [early_parent, late_leaf], early_parent: [early_leaf]},
        )
        self.assertEqual(
            [item["scope"] for item in plan],
            ["EarlyLeaf", "EarlyParent", "LateLeaf", "Top"],
        )

    def test_declared_scope_calls_define_execution_order(self):
        (self.run / "Api.catala_en").write_text(
            """```catala-metadata
declaration scope Top:
  first scope Law.Early
  second scope Law.Late
```
""",
            encoding="utf-8",
        )
        scopes = [
            {"file": "Api.catala_en", "compiler_file": "Api.catala_en", "scope": "Top"},
            {"file": "law.catala_en", "compiler_file": "law.catala_en", "scope": "Late"},
            {"file": "law.catala_en", "compiler_file": "law.catala_en", "scope": "Early"},
        ]
        sid = recursive_repair.scope_id
        top = sid("Api.catala_en", "Top")
        early = sid("law.catala_en", "Early")
        late = sid("law.catala_en", "Late")
        order = recursive_repair._declared_dependency_order(
            self.run, scopes, {top: {late, early}}
        )
        self.assertEqual(order[top], [early, late])

    def test_old_recursive_plan_is_requeued_in_execution_order(self):
        initial = self.run / "initial"
        (initial / "validation").mkdir(parents=True)
        (initial / "snapshot").mkdir()
        (initial / "snapshot/Api.catala_en").write_text(
            """```catala-metadata
declaration scope Top:
  early scope Law.Early
  late scope Law.Late
```
""",
            encoding="utf-8",
        )
        scopes = [
            {"file": "Api.catala_en", "compiler_file": "Api.catala_en", "scope": "Top"},
            {"file": "law.catala_en", "compiler_file": "law.catala_en", "scope": "Late"},
            {"file": "law.catala_en", "compiler_file": "law.catala_en", "scope": "Early"},
        ]
        (initial / "validation/input_formats.json").write_text(
            json.dumps({"candidate": {"scopes": scopes}}), encoding="utf-8"
        )
        sid = recursive_repair.scope_id
        top = sid("Api.catala_en", "Top")
        early = sid("law.catala_en", "Early")
        late = sid("law.catala_en", "Late")
        state = {
            "recursive_phase": "scope",
            "recursive_repair_plan": [
                {"id": late, "source": "law.catala_en", "scope": "Late", "dependencies": []},
                {"id": early, "source": "law.catala_en", "scope": "Early", "dependencies": []},
                {"id": top, "source": "Api.catala_en", "scope": "Top", "dependencies": [late, early]},
            ],
            "recursive_processed": {late: {"fingerprint": "old"}},
            "recursive_revisions": {late: 1},
            "recursive_active_scope": early,
        }
        self.assertTrue(recursive_repair.migrate_scope_order(self.run, state))
        self.assertEqual(
            [record["id"] for record in state["recursive_repair_plan"]],
            [early, late, top],
        )
        self.assertEqual(state["recursive_active_scope"], early)
        self.assertEqual(state["recursive_repair_queue"], [late, top])
        self.assertEqual(state["recursive_processed"], {})

    def test_completed_scope_does_not_requeue_or_invalidate_others(self):
        plan = [
            {"id": "law::Leaf", "source": "law", "scope": "Leaf", "dependencies": []},
            {
                "id": "law::Top",
                "source": "law",
                "scope": "Top",
                "dependencies": ["law::Leaf"],
            },
        ]
        state = {
            "recursive_repair_plan": plan,
            "recursive_repair_queue": [],
            "recursive_active_scope": "law::Top",
            "recursive_revision": 0,
            "recursive_processed": {"law::Leaf": {"fingerprint": "old"}},
        }
        recursive_repair.record_processed(
            state, {"law::Leaf": "unchanged", "law::Top": "new"}
        )
        self.assertEqual(state["recursive_repair_queue"], [])
        self.assertEqual(state["recursive_processed"]["law::Leaf"]["fingerprint"], "old")
        self.assertEqual(state["recursive_processed"]["law::Top"]["fingerprint"], "new")

    def test_failed_bobcat_result_is_not_an_empty_scope(self):
        analysis = self.run / "analysis/tests_bobcat"
        analysis.mkdir(parents=True)
        (analysis / "scope.json").write_text(
            json.dumps(
                {
                    "returncode": 123,
                    "finished": False,
                    "timed_out": False,
                    "cases": [],
                }
            ),
            encoding="utf-8",
        )
        self.assertTrue(recursive_repair._failed_bobcat_analysis(self.run / "analysis"))

    def test_recursive_resume_requeues_failed_scopes_in_plan_order(self):
        low = "law::Low"
        active = "law::Active"
        top = "law::Top"
        failed = self.run / "failed/tests_bobcat"
        failed.mkdir(parents=True)
        (failed / "low.json").write_text(
            json.dumps({"returncode": 123, "finished": False, "cases": []}),
            encoding="utf-8",
        )
        state = {
            "recursive_phase": "scope",
            "next_stage": "scope_analysis",
            "recursive_step": "analysis",
            "recursive_active_scope": active,
            "recursive_revision": 0,
            "recursive_revisions": {active: 1},
            "recursive_repair_plan": [
                {"id": low, "source": "law", "scope": "Low"},
                {"id": active, "source": "law", "scope": "Active"},
                {"id": top, "source": "law", "scope": "Top"},
            ],
            "recursive_repair_queue": [top],
            "recursive_processed": {low: {"analysis_path": "failed"}},
        }
        self.assertTrue(recursive_repair.recover_recursive_resume(self.run, state))
        self.assertEqual(state["recursive_active_scope"], low)
        self.assertEqual(state["recursive_repair_queue"], [active, top])
        self.assertNotIn(low, state["recursive_processed"])

    def test_recursive_resume_restores_interrupted_session(self):
        identifier = "law::Leaf"
        state = {
            "recursive_phase": "scope",
            "next_stage": "agent",
            "recursive_step": "session",
            "recursive_active_scope": identifier,
            "recursive_revision": 0,
            "recursive_repair_plan": [
                {"id": identifier, "source": "law", "scope": "Leaf"}
            ],
            "recursive_repair_queue": [],
            "recursive_processed": {},
        }
        root = recursive_repair.scope_revision_root(self.run, state)
        snapshot = root / "analysis/snapshot"
        snapshot.mkdir(parents=True)
        (snapshot / "law.catala_en").write_text("before", encoding="utf-8")
        agent = root / "session/agent"
        agent.mkdir(parents=True)
        (agent / "invocation.json").write_text("{}", encoding="utf-8")
        (self.run / "workspace/law.catala_en").write_text("partial", encoding="utf-8")
        self.assertTrue(recursive_repair.recover_recursive_resume(self.run, state))
        self.assertEqual(
            (self.run / "workspace/law.catala_en").read_text(encoding="utf-8"),
            "before",
        )
        self.assertTrue(
            (root / "session/recovery/interrupted_workspace/law.catala_en").is_file()
        )
        self.assertEqual(state["next_stage"], "agent")

    def test_restart_from_scope_restores_checkpoint_and_order(self):
        low = "law.catala_en::Low"
        target = "law.catala_en::Target"
        top = "law.catala_en::Top"
        plan = [
            {"id": low, "source": "law.catala_en", "file": "law.catala_en", "scope": "Low"},
            {"id": target, "source": "law.catala_en", "file": "law.catala_en", "scope": "Target"},
            {"id": top, "source": "law.catala_en", "file": "law.catala_en", "scope": "Top"},
        ]
        state = {
            "recursive_phase": "scope",
            "recursive_repair_plan": plan,
            "recursive_processed": {low: {}, target: {}},
            "recursive_revisions": {low: 1, target: 1},
            "recursive_active_scope": top,
            "recursive_repair_queue": [],
        }
        record = plan[1]
        snapshot = (
            self.run
            / "refinement"
            / recursive_repair.scope_slug(record)
            / "revisions/000/analysis/snapshot"
        )
        snapshot.mkdir(parents=True)
        (snapshot / "law.catala_en").write_text("checkpoint", encoding="utf-8")
        (self.run / "workspace/law.catala_en").write_text("current", encoding="utf-8")
        archive = recursive_repair.restart_from_scope(self.run, state, target)
        self.assertEqual(
            (self.run / "workspace/law.catala_en").read_text(encoding="utf-8"),
            "checkpoint",
        )
        self.assertEqual(
            (archive / "workspace/law.catala_en").read_text(encoding="utf-8"),
            "current",
        )
        self.assertEqual(state["recursive_active_scope"], target)
        self.assertEqual(state["recursive_repair_queue"], [top])
        self.assertEqual(set(state["recursive_processed"]), {low})

    def test_processed_scope_tree_is_collapsed_without_inputs(self):
        state = {
            "recursive_active_scope": "law::Top",
            "recursive_processed": {"law::Leaf": {}},
            "recursive_repair_plan": [
                {"id": "law::Leaf", "scope": "Leaf"},
                {"id": "law::Top", "scope": "Top"},
            ],
        }
        tree = {
            "kind": "scope_call",
            "name": "Leaf",
            "inputs": {"large": [1, 2]},
            "output": {"answer": 3},
            "children": [{"kind": "variable"}],
        }
        collapsed = recursive_repair.prune_execution_tree(tree, state)
        self.assertEqual(collapsed["kind"], "processed_scope")
        self.assertNotIn("inputs", collapsed)
        self.assertNotIn("children", collapsed)

    def test_recursive_artifact_directories(self):
        initial = {"recursive_phase": "initial"}
        self.assertEqual(exp.stage_directory(self.run, initial), self.run / "initial")
        state = {
            "recursive_phase": "scope",
            "recursive_step": "analysis",
            "recursive_active_scope": "law::Leaf",
            "recursive_revision": 1,
            "recursive_repair_plan": [{"id": "law::Leaf", "scope": "Leaf"}],
        }
        self.assertEqual(
            exp.stage_directory(self.run, state),
            self.run
            / "refinement"
            / recursive_repair.scope_slug(state["recursive_repair_plan"][0])
            / "revisions/001/analysis",
        )

    def test_scope_bundle_contains_only_raw_case_evidence(self):
        state = {
            "recursive_active_scope": "law::Leaf",
            "recursive_processed": {},
            "recursive_repair_plan": [
                {"id": "law::Leaf", "source": "law.catala_en", "scope": "Leaf"}
            ],
        }
        cases = [{"id": "case:1", "inputs": {"income": 2}, "branches": ["private"]}]
        symbolic = [
            {"id": "case:1", "output": {"tax": 1}, "error": None, "execution_tree": []}
        ]
        natural = [
            {
                "id": "case:1",
                "output_text": '<answer>{"tax": 1}</answer>',
                "execution_tree": {"steps": []},
            }
        ]
        bundle = recursive_repair.write_scope_bundle(
            self.run, state, cases, symbolic, natural
        )
        record = json.loads((bundle / "cases/case_1/case.json").read_text())
        self.assertEqual(record["llm_answer"], {"tax": 1})
        self.assertTrue(record["llm_oracle_complete"])
        self.assertEqual(
            set(record),
            {
                "case_id",
                "input",
                "catala_output",
                "catala_error",
                "llm_answer",
                "llm_oracle_complete",
                "llm_error",
            },
        )
        self.assertNotIn("branches", record)
        self.assertEqual(bundle_report(bundle)[0]["input"], {"income": 2})

    def test_summary_requires_every_remaining_case_exactly_once(self):
        value = {
            "scope": "Leaf",
            "change_summary": ["No code change."],
            "remaining_disagreements": [
                {"case_id": "a", "rationale": "The LLM omitted the threshold."}
            ],
        }
        self.assertIs(recursive_repair.validate_summary(value, "Leaf", {"a"}), value)
        with self.assertRaisesRegex(ValueError, "case IDs"):
            recursive_repair.validate_summary(value, "Leaf", {"a", "b"})

    def test_replay_rebuilds_current_workspace(self):
        report = self.run / "report.json"
        exp.atomic_json(report, [{"requirement_id": "TAX", "input": {"income": 20}}])
        mappings = {
            "requirements": [
                {
                    "requirement_id": "TAX",
                    "file": "tax.catala_en",
                    "scope": "Tax",
                    "output": "tax",
                }
            ]
        }
        formats = {
            "scopes": [
                {
                    "file": "tax.catala_en",
                    "compiler_file": "tax.catala_en",
                    "scope": "Tax",
                    "output_schema": SCHEMA,
                }
            ]
        }

        def build(project, formats, **kwargs):
            binary = compiled_json.compiled_path(project, "tax.catala_en", "Tax")
            binary.parent.mkdir(parents=True)
            binary.touch()
            return {}

        with (
            mock.patch.object(exp, "load_requirement_outputs", return_value=mappings),
            mock.patch.object(exp, "extract_input_formats", return_value=formats),
            mock.patch.object(compiled_json, "build_bridges", side_effect=build),
            mock.patch(
                "rtdf_formalizer.stages.reasoning_trace_diff_fuzzing.repair.subprocess.run",
                return_value=mock.Mock(
                    returncode=0, stdout='{"tax":42,"unrelated":99}', stderr=""
                ),
            ),
        ):
            rows = replay(report, self.run / "workspace")
        self.assertEqual(rows[0]["code_execution_output"], {"tax": 42})


if __name__ == "__main__":
    unittest.main()
