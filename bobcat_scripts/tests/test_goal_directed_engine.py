import json
from pathlib import Path
import re
import subprocess
import unittest

from bobcatlib import parse, paths


RESULT = re.compile(r"^\[RESULT\] BOBCAT_OBJECTIVE (?P<json>\{.*\})$")


@unittest.skipUnless(paths.CATALA.exists(), "BOBCat compiler is not built")
class GoalDirectedEngineTests(unittest.TestCase):
    def parse_completed(self, completed):
        results = [json.loads(match["json"])
                   for line in completed.stdout.splitlines()
                   if (match := RESULT.match(line))]
        parsed = parse.parse_run(completed.stdout)
        self.assertTrue(parsed.finished)
        self.assertEqual(len(parsed.objectives), len(results))
        manifest = set(parsed.branch_manifest or [])
        self.assertTrue(all(set(path.branches) <= manifest
                            for path in parsed.paths),
                        "concrete replay emitted an outcome absent from the "
                        "stable branch manifest")
        return results, parsed

    def solve(self, fixture: str, scope: str, extra_args=(), return_run=False):
        source = paths.SCRIPTS / "tests/fixtures" / fixture
        command = [str(paths.CATALA), "bobcat", str(source), "-s", scope,
                   "--no-stdlib", "--color=never", "--message-format=gnu",
                   *extra_args]
        completed = subprocess.run(command, cwd=paths.ROOT,
                                   env=paths.bobcat_env(), text=True,
                                   capture_output=True, check=True)
        results, parsed = self.parse_completed(completed)
        return (results, parsed) if return_run else results

    def test_queries_outcomes_directly_and_proves_infeasible_goal(self):
        results = self.solve("goal_directed_unsat.catala_en", "GoalDirected")
        statuses = [result["status"] for result in results]
        self.assertEqual(len(results), 4)
        self.assertEqual(statuses.count("unsat"), 1)
        self.assertEqual(statuses.count("sat"), 3)
        self.assertNotIn("unknown", statuses)

    def test_named_output_excludes_unrelated_symbolic_branches(self):
        all_results, all_run = self.solve(
            "goal_directed_output_slice.catala_en", "OutputSlice",
            return_run=True)
        left_results, left_run = self.solve(
            "goal_directed_output_slice.catala_en", "OutputSlice",
            ("--bobcat-output=left",), return_run=True)
        self.assertEqual(len(all_results), 4)
        self.assertEqual(len(left_results), 2)
        self.assertEqual(len(all_run.branch_manifest), 4)
        self.assertEqual(len(left_run.branch_manifest), 2)
        self.assertTrue(all(set(path.branches) <= set(left_run.branch_manifest)
                            for path in left_run.paths))

    def test_solver_numbers_are_json_numbers_not_rational_strings(self):
        _, run = self.solve(
            "goal_directed_numeric_json.catala_en", "NumericJson",
            return_run=True)
        self.assertTrue(run.paths)
        for path in run.paths:
            self.assertIsInstance(path.inputs["amount"].py, (int, float))
            self.assertIsInstance(path.inputs["ratio"].py, (int, float))
            self.assertIsInstance(path.inputs["count"].py, int)

    def test_branchless_scope_gets_cutecat_default_without_fabricating_a_branch(self):
        results, run = self.solve(
            "coverage_single_arm.catala_en", "SingleArm", return_run=True)
        self.assertEqual(results, [])
        self.assertEqual(run.branch_manifest, [])
        self.assertTrue(run.finished)
        self.assertEqual(len(run.paths), 1)
        self.assertEqual(run.paths[0].kind, "branchless_default")
        self.assertEqual(run.paths[0].branches, [])
        self.assertEqual(run.paths[0].inputs["choice"].py, "Only")
        self.assertEqual(run.paths[0].outputs["result"].py, 1)

    def test_fixed_input_scope_uses_its_only_execution_without_solver_search(self):
        results, run = self.solve(
            "goal_directed_fixed_input.catala_en", "FixedInput", return_run=True)
        self.assertEqual(sorted(result["status"] for result in results),
                         ["sat", "unsat"])
        self.assertEqual(len(run.paths), 1)
        self.assertEqual(run.paths[0].kind, "fixed_input")
        self.assertEqual(run.paths[0].inputs, {})
        self.assertEqual(run.paths[0].outputs["result"].py, 1)

    def test_callee_slice_preserves_entry_guard_and_later_failure(self):
        results, run = self.solve("goal_directed_entry_guard.catala_en",
                                  "EntryGuard", return_run=True)
        self.assertEqual(sorted(r["status"] for r in results),
                         ["sat", "unsat", "unsat", "unsat"])
        self.assertTrue(run.paths)
        self.assertTrue(all(not path.inputs["enter"].py for path in run.paths))

    def test_list_equality_ignores_inactive_storage(self):
        results, run = self.solve("goal_directed_list_equality.catala_en",
                                  "ListEquality", return_run=True)
        self.assertEqual(sorted(r["status"] for r in results), ["sat", "sat"])
        self.assertTrue(any(list(map(int, path.inputs["xs"].py)) == [1] for path in run.paths))
        self.assertTrue(any(list(map(int, path.inputs["xs"].py)) != [1] for path in run.paths))

    def test_unused_date_decodes_without_symbolic_calendar_constraints(self):
        results = self.solve("goal_directed_unused_date.catala_en", "UnusedDate")
        self.assertEqual([r["status"] for r in results], ["sat", "sat"])
        self.assertTrue(all(r.get("validated") for r in results))

    def test_failure_outside_branch_slice_is_refined(self):
        results, run = self.solve("goal_directed_unrelated_empty.catala_en",
                                  "UnrelatedEmpty", return_run=True)
        self.assertTrue(results)
        self.assertTrue(all(r["status"] == "sat" for r in results))
        self.assertTrue(run.paths)
        self.assertTrue(all(path.inputs["values"].py for path in run.paths))

    def test_same_source_decision_is_not_reenumerated_per_call_site(self):
        results = self.solve("coverage_scheduler.catala_en", "SchedulerTest")
        self.assertEqual(len(results), 4)
        self.assertTrue(all(result["status"] == "sat" for result in results))

    def test_helper_definition_and_nested_goal_share_exact_semantics(self):
        results = self.solve("goal_directed_helper_unsat.catala_en",
                             "HelperGoal")
        statuses = [result["status"] for result in results]
        self.assertEqual(len(results), 4)
        self.assertEqual(statuses.count("unsat"), 1)
        self.assertEqual(statuses.count("sat"), 3)
        self.assertNotIn("unknown", statuses)

    def test_bounded_list_elements_drive_lambda_branches(self):
        results = self.solve("goal_directed_list.catala_en", "ListGoal")
        self.assertEqual(len(results), 2)
        self.assertTrue(all(result["status"] == "sat" for result in results))
        self.assertTrue(all(result.get("validated") for result in results))

    def test_input_bound_admits_a_goal_requiring_two_elements(self):
        results, run = self.solve(
            "goal_directed_progressive_list.catala_en",
            "ProgressiveListGoal",
            ("--bobcat-max-list-length=2", "--bobcat-timings"),
            return_run=True,
        )
        self.assertEqual(len(results), 2)
        self.assertTrue(all(result["status"] == "sat" for result in results))
        self.assertTrue(all(result.get("validated") for result in results))
        checks = [timing for timing in run.timings
                  if timing["phase"] == "z3_check_and_decode"]
        self.assertIn(2, {timing.get("list_bound") for timing in checks})
        self.assertTrue(all(timing["list_bound"] <= 2 for timing in checks))
        self.assertTrue(any(timing["phase"] in ("shared_compilation", "slice_compilation")
                            for timing in run.timings))

    def test_completed_compilation_precedes_solving(self):
        results, run = self.solve(
            "goal_directed_compilation_barrier.catala_en",
            "CompilationBarrierGoal",
            ("--bobcat-timings",),
            return_run=True,
        )
        self.assertEqual(
            sorted(result["status"] for result in results), ["sat", "unsat"]
        )
        phases = [timing["phase"] for timing in run.timings]
        self.assertIn("z3_check_and_decode", phases)
        self.assertTrue(any(phase in ("shared_compilation", "slice_compilation")
                            for phase in phases[:phases.index("z3_check_and_decode")]))

    def test_each_written_match_arm_is_a_validated_branch(self):
        results = self.solve("goal_directed_match.catala_en", "MatchGoal")
        self.assertEqual(len(results), 3)
        self.assertTrue(all(result["status"] == "sat" for result in results))
        self.assertTrue(all(result.get("validated") for result in results))

    def test_reduce_reaches_nonempty_and_empty_outcomes(self):
        results = self.solve("goal_directed_reduce.catala_en", "ReduceGoal")
        self.assertEqual(len(results), 2)
        self.assertTrue(all(result["status"] == "sat" for result in results))
        self.assertTrue(all(result.get("validated") for result in results))

    def test_year_duration_is_calendar_aware_and_replay_validated(self):
        results = self.solve("goal_directed_calendar.catala_en", "CalendarGoal")
        self.assertEqual(len(results), 2)
        self.assertTrue(all(result["status"] == "sat" for result in results))
        self.assertTrue(all(result.get("validated") for result in results))

    def test_recursive_bounds_cover_nested_list_elements(self):
        results = self.solve("goal_directed_nested_list.catala_en",
                             "NestedListGoal")
        self.assertEqual(len(results), 2)
        self.assertTrue(all(result["status"] == "sat" for result in results))
        self.assertTrue(all(result.get("validated") for result in results))

    def test_nested_scope_map2_preserves_defaults_and_assertions(self):
        results, run = self.solve(
            "goal_directed_nested_scope_map.catala_en", "NestedScopeMap",
            return_run=True)
        self.assertEqual(len(results), 2)
        self.assertTrue(all(result["status"] == "sat" for result in results))
        self.assertTrue(all(result.get("validated") for result in results))
        validated_inputs = [result["input"] for result in results]
        self.assertTrue(all(value["journey"]["valid"] == 42
                            for value in validated_inputs))
        self.assertTrue(all(value["journey"]["values"]
                            for value in validated_inputs))
        self.assertTrue(run.paths)

    def test_filter_map_reduce_composition_is_symbolic(self):
        results = self.solve("goal_directed_composed_list.catala_en",
                             "ComposedListGoal")
        self.assertGreaterEqual(len(results), 4)
        self.assertTrue(all(result["status"] != "unknown" for result in results))
        self.assertTrue(all(result.get("validated")
                            for result in results
                            if result["status"] == "sat"))

    def test_duration_division_is_replay_validated(self):
        results = self.solve("goal_directed_duration_division.catala_en",
                             "DurationDivisionGoal")
        self.assertEqual(len(results), 2)
        self.assertTrue(all(result["status"] == "sat" for result in results))
        self.assertTrue(all(result.get("validated") for result in results))

    def test_error_on_empty_is_a_normal_termination_constraint(self):
        results = self.solve("goal_directed_error_on_empty.catala_en",
                             "ErrorOnEmptyGoal")
        self.assertEqual(len(results), 2)
        self.assertTrue(all(result["status"] == "sat" for result in results))
        self.assertTrue(all(result.get("validated") for result in results))

    def test_named_scalar_and_list_values_are_not_unconstrained(self):
        results, run = self.solve(
            "goal_directed_defined_values.catala_en",
            "DefinedValuesGoal",
            return_run=True,
        )
        self.assertEqual(len(results), 2)
        self.assertTrue(all(result["status"] == "sat" for result in results))
        self.assertTrue(all(result.get("validated") for result in results))
        self.assertEqual(run.refinements, [])

    def test_input_bounds_change_the_representable_witnesses(self):
        for bound in (0, 1, 2):
            with self.subTest(bound=bound):
                results, run = self.solve(
                    "goal_directed_progressive_list.catala_en", "ProgressiveListGoal",
                    (f"--bobcat-max-list-length={bound}", "--bobcat-timings"),
                    return_run=True)
                self.assertEqual(sum(r["status"] == "sat" for r in results),
                                 2 if bound == 2 else 1)
                compiled = [t["list_bound"] for t in run.timings
                            if t["phase"] in ("shared_compilation", "slice_compilation")]
                self.assertEqual(max(compiled), bound)


    def test_intermediate_lists_can_exceed_input_bound(self):
        results = self.solve("goal_directed_list_growth.catala_en", "ListGrowth",
                             ("--bobcat-max-list-length=1",))
        self.assertEqual([r["status"] for r in results].count("sat"), 2)

    def test_representation_cap_preserves_witnesses_without_false_unsat(self):
        results = self.solve(
            "goal_directed_list_growth.catala_en", "ListGrowth",
            ("--bobcat-max-list-length=1",
             "--bobcat-max-representation-capacity=1"))
        self.assertEqual([r["status"] for r in results].count("sat"), 1)
        self.assertEqual([r["status"] for r in results].count("unknown"), 1)
        self.assertNotIn("unsat", [r["status"] for r in results])
        self.assertTrue(all(r.get("validated") for r in results
                            if r["status"] == "sat"))

    def test_summary_instances_preserve_different_arguments(self):
        results = self.solve("goal_directed_summary_arguments.catala_en",
                             "SummaryArguments")
        self.assertEqual([r["status"] for r in results].count("unsat"), 1)
        self.assertNotIn("unknown", [r["status"] for r in results])

    def test_failure_refinement_preserves_inactive_calls(self):
        results, run = self.solve("goal_directed_semantic_refinement.catala_en",
                                  "SemanticRefinement", return_run=True)
        self.assertTrue(all(r["status"] == "sat" for r in results))
        self.assertTrue(run.paths)
        for path in run.paths:
            data = {k: v.py for k, v in path.inputs.items()}
            if data["enabled"]:
                self.assertTrue(data["permitted"])
        self.assertTrue(any(not path.inputs["enabled"].py
                            and not path.inputs["permitted"].py
                            for path in run.paths))
        self.assertTrue(any(r.get("learned_obligations", 0) > 0
                            for r in run.refinements))

    def test_branches_used_only_in_assertion_remain_objectives(self):
        results = self.solve("goal_directed_assertion_only.catala_en", "AssertionOnly")
        self.assertEqual(len(results), 2)
        self.assertTrue(all(r["status"] == "sat" for r in results))

    def test_function_valued_record_keeps_captured_arguments(self):
        results = self.solve("goal_directed_function_record.catala_en", "FunctionRecord")
        self.assertEqual(len(results), 2)
        self.assertTrue(all(r["status"] == "sat" for r in results))

    def test_lazy_refinement_specializes_each_call(self):
        results, run = self.solve("goal_directed_refined_instances.catala_en",
                                  "RefinedInstances", return_run=True)
        self.assertTrue(results)
        self.assertTrue(all(r["status"] in ("sat", "unsat") for r in results))
        self.assertTrue(any(r["status"] == "unsat" for r in results))
        self.assertTrue(run.paths)
        self.assertTrue(all(path.inputs["x"].py not in (0, -1) for path in run.paths))
        self.assertTrue(any(r.get("learned_obligations", 0) > 0 for r in run.refinements))

    def test_computed_function_preserves_conditional_closures(self):
        results, run = self.solve("goal_directed_computed_function.catala_en",
                                  "ComputedFunction", return_run=True)
        self.assertTrue(results)
        self.assertTrue(all(r["status"] == "sat" for r in results))
        self.assertTrue(run.paths)

    def test_mapped_nested_list_growth_preserves_element_bound(self):
        results = self.solve("goal_directed_nested_growth.catala_en", "NestedGrowth",
                             ("--bobcat-max-list-length=1",))
        self.assertTrue(all(r["status"] == "sat" for r in results))
        self.assertTrue(results)

    def test_polymorphic_summaries_keep_argument_sorts_separate(self):
        results = self.solve("goal_directed_polymorphic_summaries.catala_en",
                             "PolymorphicSummaries",
                             ("--bobcat-max-list-length=1",))
        self.assertTrue(results)
        self.assertTrue(all(r["status"] == "sat" for r in results))


if __name__ == "__main__":
    unittest.main()
