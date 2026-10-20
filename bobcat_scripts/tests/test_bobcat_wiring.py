from pathlib import Path
import unittest

from bobcatlib import paths, run, targets


class BobcatWiringTests(unittest.TestCase):
    def test_default_target_budget_is_thirty_minutes(self):
        self.assertEqual(run.DEFAULT_TARGET_TIMEOUT, 1800)
        self.assertEqual(self.target().timeout, 1800)

    def target(self, max_list_length=None, solver_timeout_ms=None,
               solver_timeout_max_ms=None, objective_timeout_ms=None):
        return run.Target(
            name="fixture", port="sara", harness=Path("Fixture.catala_en"),
            scope="Fixture", max_list_length=max_list_length,
            solver_timeout_ms=solver_timeout_ms,
            solver_timeout_max_ms=solver_timeout_max_ms,
            objective_timeout_ms=objective_timeout_ms)

    def test_uses_independent_source_binary_and_output_tree(self):
        self.assertIn("catala-bobcat", str(paths.CATALA))
        self.assertTrue(str(paths.out("sara")).endswith("sara_bobcat"))
        self.assertNotEqual(paths.out("sara"),
                            paths.ROOT / ".port/sara_cutecat")

    def test_command_uses_only_goal_directed_subcommand(self):
        command = run.bobcat_cmd(self.target(5), Path("project"))
        self.assertEqual(command[0], "/usr/bin/prlimit")
        self.assertIn("--stack=268435456:unlimited", command)
        self.assertEqual(command[command.index(str(paths.CATALA)) + 1], "bobcat")
        self.assertNotIn("concolic", command)
        self.assertIn("--bobcat-max-list-length=5", command)
        self.assertIn("--bobcat-max-representation-capacity=64", command)
        self.assertFalse(any("intermediate-list-bound" in arg for arg in command))
        self.assertFalse(any(arg.startswith("--conc-") for arg in command))

    def test_default_list_bound_is_left_to_engine(self):
        command = run.bobcat_cmd(self.target(), Path("project"))
        self.assertFalse(any(arg.startswith("--bobcat-max-list-length=")
                             for arg in command))

    def test_named_output_is_forwarded_to_symbolic_slicing(self):
        target = self.target()
        target.output = "answer"
        command = run.bobcat_cmd(target, Path("project"))
        self.assertIn("--bobcat-output=answer", command)

    def test_positive_hundred_money_constraint_is_opt_in(self):
        target = self.target()
        self.assertNotIn("--bobcat-positive-hundred-money-inputs",
                         run.bobcat_cmd(target, Path("project")))
        target.positive_hundred_money_inputs = True
        self.assertIn("--bobcat-positive-hundred-money-inputs",
                      run.bobcat_cmd(target, Path("project")))

    def test_progressive_solver_timeouts_are_configurable(self):
        command = run.bobcat_cmd(
            self.target(solver_timeout_ms=25, solver_timeout_max_ms=500),
            Path("project"))
        self.assertIn("--bobcat-solver-timeout-ms=25", command)
        self.assertIn("--bobcat-solver-timeout-max-ms=500", command)

    def test_total_objective_timeout_is_configurable(self):
        command = run.bobcat_cmd(
            self.target(objective_timeout_ms=20000), Path("project"))
        self.assertIn("--bobcat-objective-timeout-ms=20000", command)

    def test_command_has_no_coverage_optimizer(self):
        command = run.bobcat_cmd(self.target(), Path("project"))
        self.assertFalse(any("maxsat" in arg.lower() for arg in command))

    def test_only_unique_requirement_scopes_are_targets(self):
        actual = targets.enumerated_targets()
        self.assertEqual(len(actual), 15)
        self.assertTrue(actual)
        self.assertEqual(sum(target.port == "sara" for target in actual), 1)
        sara_names = {target.name for target in actual if target.port == "sara"}
        self.assertEqual(sara_names, {"sara_scope_Section1_Total"})
        self.assertTrue(all("_fn_" not in target.name for target in actual))

    def test_requirement_mapping_groups_outputs_of_one_scope(self):
        sara = [target for target in targets.enumerated_targets()
                if target.name == "sara_scope_Section1_Total"]
        self.assertEqual(len(sara), 1)
        self.assertIn("SARA-TOTAL-TAX", sara[0].note)
        self.assertIn("outputs total", sara[0].note)


if __name__ == "__main__":
    unittest.main()
