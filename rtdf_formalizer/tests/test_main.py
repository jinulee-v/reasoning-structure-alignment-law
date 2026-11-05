from __future__ import annotations

import argparse
import json
import os
import re
import socket
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from rtdf_formalizer import runner
from rtdf_formalizer.stages import validation as apply_nl_test
from rtdf_formalizer.stages.validation import verification as validation_verification
from rtdf_formalizer import agents
from rtdf_formalizer.stages import utils as main
from rtdf_formalizer.stages.utils import run_state
from rtdf_formalizer.stages.utils import workspace_validation
from rtdf_formalizer.stages.validation import information_extraction
from rtdf_formalizer.agents import (
    apptainer,
    claude_code,
    codex,
)
from rtdf_formalizer.agents.base import (
    DOCUMENTATION_MOUNT,
    INPUT_REQUIREMENTS_HELPER_MOUNT,
    SUBMISSION_CHECK_HELPER_MOUNT,
    formalization_prompt,
)
from rtdf_formalizer.stages.utils.guidance import (
    endpoint_test_files,
    public_endpoint_scopes,
    public_endpoint_test_targets,
    semantic_guidance,
)


DOCUMENT = """<!-- rtdf-document-id: example/doc -->

<!-- rtdf-block-id: example/doc:b0001; role: preamble-definitions -->
```catala
```

The statute prose must remain unchanged.

<!-- rtdf-block-id: example/doc:b0002; role: provision -->
```catala
```
"""


def endpoint_contracts(
    text: str, *, markdown: bool
) -> dict[str, tuple[tuple[str, str, str], ...]]:
    if markdown:
        heading = re.compile(r"(?m)^scope ([^:]+):")
    else:
        heading = re.compile(
            r"(?m)^(?:declaration scope|déclaration champ d'application) ([^:]+):"
        )
    result = {}
    for match in heading.finditer(text):
        body = text[match.end() :]
        boundary = re.search(
            r"(?m)^(?:scope |declaration scope|déclaration champ d'application|"
            r"champ d'application |```)",
            body,
        )
        if boundary:
            body = body[: boundary.start()]
        fields = []
        for kind, name, value_type in re.findall(
            r"(?m)^\s*(input|output|entrée|résultat)\s+(\S+)\s+"
            r"(?:content|contenu)\s+([^\n]+)",
            body,
        ):
            normalized_type = re.sub(r"\b(?:W|A)\.", "", value_type.strip())
            for french, english in (
                ("liste de ", "list of "),
                ("argent", "money"),
                ("entier", "integer"),
                ("booléen", "boolean"),
                ("durée", "duration"),
                ("décimal", "decimal"),
            ):
                normalized_type = normalized_type.replace(french, english)
            fields.append(
                (
                    {"entrée": "input", "résultat": "output"}.get(kind, kind),
                    name,
                    normalized_type,
                )
            )
        result[match.group(1)] = tuple(fields)
    return result


def structure_contracts(text: str) -> dict[str, tuple[tuple[str, str], ...]]:
    result = {}
    heading = re.compile(r"(?m)^(?:declaration|déclaration) structure ([^:]+):")
    for match in heading.finditer(text):
        fields = []
        for line in text[match.end() :].splitlines():
            field = re.match(
                r"\s*(?:data|donnée)\s+(\S+)\s+(?:content|contenu)\s+(.+)",
                line,
            )
            if field:
                value_type = re.sub(r"\b(?:W|A)\.", "", field.group(2).strip())
                for french, english in (
                    ("liste de ", "list of "),
                    ("argent", "money"),
                    ("entier", "integer"),
                    ("booléen", "boolean"),
                    ("décimal", "decimal"),
                ):
                    value_type = value_type.replace(french, english)
                fields.append((field.group(1), value_type))
            elif fields:
                break
        result[match.group(1)] = tuple(fields)
    return result


class AgentStageTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.dataset = self.root / "dataset"
        self.dataset.mkdir()
        (self.dataset / "RTDF_MANIFEST.json").write_text(
            '{"version": 1}\n', encoding="utf-8"
        )
        (self.dataset / "statute.catala_en").write_text(DOCUMENT, encoding="utf-8")
        self.fake_apptainer = self.root / "fake-apptainer"
        self.fake_apptainer.write_text(
            """#!/usr/bin/env python3
import json
import pathlib
import sys

workspace = None
for index, value in enumerate(sys.argv):
    if value == "--bind":
        source, destination, *_ = sys.argv[index + 1].split(":")
        if destination == "/workspace":
            workspace = pathlib.Path(source)
if workspace is None:
    raise SystemExit("workspace was not mounted")
document = workspace / "statute.catala_en"
text = document.read_text()
text = text.replace(
    "```catala\\n```",
    "```catala\\ndeclaration Answer content integer\\ndeclaration Other content integer\\n````"[:-1],
    1,
)
text = text.replace(
    "```catala\\n```",
    "```catala\\ndeclaration Answer content integer\\ndeclaration Other content integer\\n````"[:-1],
    1,
)
document.write_text(text)
print(json.dumps({"type": "thread.started", "thread_id": "thread-test"}))
print(json.dumps({"type": "turn.completed", "usage": {"input_tokens": 120, "output_tokens": 30, "cached_input_tokens": 20, "output_tokens_details": {"reasoning_tokens": 7}}}))
""",
            encoding="utf-8",
        )
        self.fake_apptainer.chmod(0o755)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def arguments(self) -> argparse.Namespace:
        return argparse.Namespace(
            dataset=str(self.dataset),
            run_id="test-run",
            agent="opencode",
            image="example/agent:test",
            agent_provider="openai",
            agent_model="test-model",
            reasoning_trace_provider="openai",
            reasoning_trace_model="reasoning-model",
            agent_command='["fake-agent"]',
            mount=[],
            apptainer_binary=str(self.fake_apptainer),
            agent_binary=None,
            use_host_agent=False,
            agent_home_seed=None,
            host_toolchain=None,
            network_policy="host",
            cpus=None,
            memory=None,
            pids_limit=None,
            timeout=30,
            progress_interval=0,
        )

    def test_agent_stage_is_durable_and_idempotent(self) -> None:
        runs = self.root / "runs"
        with mock.patch.object(run_state, "RUNS", runs):
            run_directory = runner.create_run(self.arguments())
            # Exercise the historical stage-at-a-time resume contract here; the repair-iteration controller has its own repair tests.
            config = main.load_json(run_directory / "config.json")
            config.pop("repair")
            main.atomic_json(run_directory / "config.json", config)
            state = runner.resume_run(run_directory)
            self.assertEqual(state["next_stage"], "validation")
            self.assertEqual(state["status"], "agent_completed")
            self.assertIn("agent", state["completed_stages"])
            self.assertIn("snapshot", state["completed_stages"])
            snapshot = run_directory / "iterations/000/snapshot"
            self.assertTrue(snapshot.is_dir())
            self.assertEqual(
                main.tree_hash(snapshot), main.tree_hash(run_directory / "workspace")
            )
            manifest = main.load_json(run_directory / "iterations/000/snapshot.json")
            self.assertEqual(manifest["tree_sha256"], main.tree_hash(snapshot))

            result = main.load_json(run_directory / "iterations/000/agent/result.json")
            self.assertEqual(result["integrity"]["changed_blocks"], 2)
            config = main.load_json(run_directory / "config.json")
            self.assertEqual(config["agent"]["provider"], "openai")
            self.assertEqual(
                config["reasoning_trace"],
                {"provider": "openai", "model": "reasoning-model"},
            )
            attempts_before = list(
                (run_directory / "iterations/000/agent").glob("attempt-*")
            )

            resumed = runner.resume_run(run_directory)
            attempts_after = list(
                (run_directory / "iterations/000/agent").glob("attempt-*")
            )
            self.assertEqual(resumed["next_stage"], "validation")
            self.assertEqual(attempts_before, attempts_after)

            usage = json.loads((run_directory / "usage.jsonl").read_text().strip())
            self.assertEqual(usage["total_tokens"], 150)
            self.assertEqual(usage["uncached_input_tokens"], 100)
            self.assertEqual(usage["reasoning_tokens"], 7)
            self.assertEqual(usage["count_source"], "provider-reported")
            self.assertEqual(usage["request_id"], "thread-test")
            self.assertEqual(usage["request_metadata"]["thread_id"], "thread-test")

            frozen = (snapshot / "statute.catala_en").read_bytes()
            (run_directory / "workspace/statute.catala_en").write_text(
                DOCUMENT.replace(
                    "```catala\n```",
                    "```catala\ndeclaration Other content integer\n```",
                ),
                encoding="utf-8",
            )
            self.assertEqual(
                main.publish_iteration_snapshot(run_directory, 0), snapshot
            )
            self.assertEqual((snapshot / "statute.catala_en").read_bytes(), frozen)

    def test_agent_stage_persists_rejected_insubstantial_submission(self) -> None:
        script = self.fake_apptainer.read_text(encoding="utf-8")
        script = script.replace(
            "declaration Answer content integer\\ndeclaration Other content integer\\n",
            "# comment-only marker\\n",
        )
        self.fake_apptainer.write_text(script, encoding="utf-8")
        runs = self.root / "rejected-runs"

        with mock.patch.object(run_state, "RUNS", runs):
            run_directory = runner.create_run(self.arguments())
            with self.assertRaisesRegex(
                main.RunnerError, "translation not happening for all provisions"
            ):
                runner.resume_run(run_directory)

        state = main.load_json(run_directory / "state.json")
        self.assertNotIn("agent", state["completed_stages"])
        self.assertFalse((run_directory / "iterations/000/snapshot").exists())
        result = main.load_json(
            run_directory / "iterations/000/agent/attempt-000/result.json"
        )
        self.assertEqual(result["status"], "failed")
        self.assertIsNone(result["integrity"])
        self.assertEqual(
            result["error"], "translation not happening for all provisions"
        )

    def test_opencode_usage_aggregates_provider_reported_steps(self) -> None:
        stdout = self.root / "opencode.jsonl"
        events = [
            {
                "type": "step_finish",
                "part": {
                    "tokens": {
                        "total": 120,
                        "input": 70,
                        "output": 10,
                        "reasoning": 2,
                        "cache": {"read": 40, "write": 0},
                    }
                },
            },
            {
                "type": "step_finish",
                "part": {
                    "tokens": {
                        "total": 93,
                        "input": 55,
                        "output": 5,
                        "reasoning": 0,
                        "cache": {"read": 30, "write": 3},
                    }
                },
            },
        ]
        stdout.write_text(
            "".join(json.dumps(event) + "\n" for event in events),
            encoding="utf-8",
        )

        usage = main.extract_usage(stdout, "ignored fallback prompt")

        self.assertEqual(usage["input_tokens"], 198)
        self.assertEqual(usage["uncached_input_tokens"], 128)
        self.assertEqual(usage["cached_input_tokens"], 70)
        self.assertEqual(usage["cache_write_tokens"], 3)
        self.assertEqual(usage["output_tokens"], 15)
        self.assertEqual(usage["reasoning_tokens"], 2)
        self.assertEqual(usage["total_tokens"], 213)
        self.assertEqual(usage["count_source"], "provider-reported")

    def test_live_progress_aggregates_tokens_tools_and_fences(self) -> None:
        stdout = self.root / "live.jsonl"
        events = [
            {
                "type": "tool_use",
                "part": {"callID": "call-1", "type": "tool"},
            },
            {
                "type": "step_finish",
                "part": {
                    "tokens": {
                        "total": 120,
                        "input": 70,
                        "output": 10,
                        "cache": {"read": 40, "write": 0},
                    }
                },
            },
        ]
        stdout.write_text(
            "".join(json.dumps(event) + "\n" for event in events), encoding="utf-8"
        )
        workspace = self.root / "progress-workspace"
        workspace.mkdir()
        (workspace / "RTDF_MANIFEST.json").write_text('{"version": 1}\n')
        (workspace / "statute.catala_en").write_text(
            DOCUMENT.replace(
                "```catala\n```",
                "```catala\ndeclaration Answer content integer\n```",
                1,
            )
        )

        progress = main.AgentProgress(stdout, self.dataset, workspace)
        progress.refresh()

        self.assertEqual(progress.tokens(), (110, 40, 10, 120))
        self.assertEqual(len(progress.tool_ids), 1)
        self.assertEqual(
            main.workspace_fence_progress(self.dataset, workspace),
            {"total": 2, "filled": 1, "valid": 0, "changed": 1},
        )

    def test_live_progress_deduplicates_claude_message_fragments(self) -> None:
        stdout = self.root / "claude-live.jsonl"
        base_message = {
            "model": "claude-test",
            "id": "message-1",
            "usage": {
                "input_tokens": 2,
                "cache_creation_input_tokens": 8,
                "cache_read_input_tokens": 90,
                "output_tokens": 3,
            },
        }
        events = [
            {"type": "assistant", "message": {**base_message, "content": []}},
            {
                "type": "assistant",
                "message": {
                    **base_message,
                    "usage": {**base_message["usage"], "output_tokens": 9},
                    "content": [{"type": "tool_use", "id": "tool-1"}],
                },
            },
        ]
        stdout.write_text(
            "".join(json.dumps(event) + "\n" for event in events), encoding="utf-8"
        )

        progress = main.AgentProgress(stdout, self.dataset, self.dataset)
        progress.refresh()

        self.assertEqual(progress.tokens(), (100, 90, 9, 109))
        self.assertEqual(len(progress.tool_ids), 1)

    def test_generated_run_id_records_experiment_axes(self) -> None:
        run_id = main.new_run_id(
            self.dataset, "codex", "openai/gpt-5", "deepinfra/model-x"
        )
        self.assertRegex(
            run_id,
            r"^\d{8}-\d{4}-codex-openai-gpt-5-deepinfra-model-x-dataset-[0-9a-f]{8}$",
        )

    def test_prompt_documents_the_offline_catala_workflow(self) -> None:
        prompt = formalization_prompt("example", False)
        self.assertIn(f"{DOCUMENTATION_MOUNT}/README.md", prompt)
        self.assertIn("clerk start", prompt)
        self.assertIn("clerk typecheck .", prompt)
        self.assertIn("clerk test .", prompt)
        self.assertIn("clerk run path/to/document.catala_* --scope=ScopeName", prompt)
        self.assertIn("Treat absence as data", prompt)
        self.assertIn("JSON interface an absent optional value is `null`", prompt)
        self.assertIn("complete `match` covering both", prompt)
        self.assertIn("`Absent` and `Present content value`", prompt)
        self.assertIn("absence must not automatically", prompt)
        self.assertIn("Test whether a rule is", prompt)
        self.assertIn("applicable before inspecting optionals", prompt)
        self.assertIn("required evaluator-facing output non-optional", prompt)

    def test_known_dataset_prompt_includes_semantic_guidance(self) -> None:
        prompt = formalization_prompt("NSW_community_gaming", False)
        self.assertIn("`/workspace/nsw_community_gaming.md`", prompt)
        self.assertIn("`/workspace/REQUIREMENT_OUTPUTS.json`", prompt)
        self.assertIn("Catala source file", prompt)
        self.assertIn("`file`, `scope`, and `output`", prompt)
        self.assertIn("top-level output variable", prompt)
        self.assertIn(
            "`/rtdf/check_submission.sh /workspace "
            "/workspace/INPUT_VARIABLE_DESCRIPTION.json --check`",
            prompt,
        )
        self.assertIn("`/rtdf/extract_input_requirements.sh`", prompt)
        self.assertIn("until it prints `submission accepted`", prompt)
        self.assertIn("calls `clerk json-schema`", prompt)
        self.assertIn("`/workspace/INPUT_VARIABLE_DESCRIPTION.json`", prompt)
        self.assertIn("unique field path, enum, and struct", prompt)
        self.assertIn("exact `FILE::SCOPE` identifiers", prompt)
        self.assertIn("Do not leave descriptions blank", prompt)
        self.assertIn("deliberately does not specify an interface", prompt)
        self.assertIn("do not collect them in one block", prompt)
        self.assertIn(
            "For each provision-local fence, formalize the immediately preceding statutory",
            prompt,
        )
        self.assertIn("verify that all fences are correctly filled", prompt)
        self.assertIn(
            "A single Catala scope definition can be distributed across multiple fences",
            prompt,
        )
        self.assertIn("keeping the rule connected to a machine-callable output", prompt)
        self.assertNotIn("50%", prompt)
        self.assertNotIn("non-comment lines", prompt)
        self.assertIn("whether each covered form is", prompt)
        self.assertIn("`NSW-ART-UNION`", prompt)
        self.assertNotIn("scope ArtUnionAuthorized", prompt)
        self.assertNotIn("declaration enumeration BenefitingOrganisationType", prompt)
        self.assertNotIn("content enum", prompt)
        self.assertNotIn("favorite_color", prompt)

    def test_sara_prompt_uses_the_predeclared_api_contract(self) -> None:
        prompt = formalization_prompt("sara", False)
        self.assertIn("`Api.catala_en` as the evaluator-facing contract", prompt)
        self.assertIn("`Definitions.catala_en` is exclusively", prompt)
        self.assertIn("Do not rename or remove those scopes or outputs", prompt)
        self.assertIn("implement only cross-section composition", prompt)
        self.assertNotIn("`/workspace/REQUIREMENT_OUTPUTS.json`", prompt)
        self.assertNotIn("fill every ID", prompt)

    def test_all_benchmark_datasets_have_guidance(self) -> None:
        for dataset in (
            "airline",
            "sara",
            "NSW_community_gaming",
            "aides_logement",
            "allocations_familiales",
        ):
            with self.subTest(dataset=dataset):
                value = semantic_guidance(dataset)
                self.assertIsNotNone(value)
                directory = main.ROOT / "data/raw" / dataset
                mapping = main.load_requirement_outputs(
                    directory, require_resolved=False
                )
                self.assertEqual(
                    [item["requirement_id"] for item in mapping["requirements"]],
                    main.required_functionality_ids(directory),
                )
                self.assertTrue(
                    "machine-callable" in value or "appelables par machine" in value
                )

    def test_guidance_does_not_expose_gold_signatures(self) -> None:
        for dataset in ("airline", "sara", "NSW_community_gaming"):
            with self.subTest(dataset=dataset):
                guidance = semantic_guidance(dataset)
                self.assertEqual(endpoint_contracts(guidance, markdown=True), {})
                self.assertEqual(structure_contracts(guidance), {})

    def test_public_endpoint_targets_are_derived_from_wrappers(self) -> None:
        self.assertEqual(public_endpoint_scopes("airline"), ("BaggageFee",))
        self.assertIn("TotalTax", public_endpoint_scopes("sara"))
        self.assertEqual(
            public_endpoint_test_targets("allocations_familiales"),
            (
                "allocations_familiales_scope_allocations_familiales_wrapper_"
                "FamilyAllowance",
                "allocations_familiales_scope_allocations_familiales_wrapper_"
                "FamilyBenefitEligibility",
            ),
        )

    def test_only_public_wrapper_targets_are_staged(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary)
            for filename, target in (
                ("public.jsonl", "airline_scope_airline_wrapper_BaggageFee"),
                ("internal.jsonl", "airline_scope_Airline_FnPositionFee"),
            ):
                (source / filename).write_text(
                    json.dumps({"target": target}) + "\n", encoding="utf-8"
                )
            self.assertEqual(endpoint_test_files("airline", source), ("public.jsonl",))

    def test_original_corpus_keeps_non_wrapper_targets(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary)
            for filename in ("upstream_a.jsonl", "upstream_b.jsonl"):
                (source / filename).write_text("{}\n", encoding="utf-8")
            self.assertEqual(
                main.corpus_test_files("airline", source, corpus="original"),
                ("upstream_a.jsonl", "upstream_b.jsonl"),
            )

    def test_primary_test_suite_is_discovered_only_by_directory_convention(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            gold = Path(temporary)
            nl = gold / "tests_nl"
            nl.mkdir()
            (nl / "case.json").write_text(
                json.dumps(
                    {
                        "id": "case",
                        "domain": "example",
                        "text": "Facts.",
                        "question": "Question?",
                        "label": "Answer",
                    }
                ),
                encoding="utf-8",
            )
            self.assertEqual(main.verification_test_directories(gold)["original"], nl)
            rows = list(information_extraction._rows(nl))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0][2]["label"], "Answer")

            (gold / "tests_catala").mkdir()
            with self.assertRaisesRegex(
                main.RunnerError, "multiple primary test suites"
            ):
                main.verification_test_directories(gold)

    def test_legacy_translator_prompt_no_longer_receives_gold_signature(self) -> None:
        prompt = apply_nl_test.translator_prompt("airline")
        self.assertNotIn("scope BaggageFee", prompt)
        self.assertIn("calculate the total", prompt)
        self.assertIn("`reference_to_candidate`", prompt)
        self.assertIn("payload-bearing constructor as a one-key object", prompt)
        self.assertIn("`year`/`month`/`day` object", prompt)
        self.assertIn("map the active", prompt)
        self.assertIn("ignore the inactive one", prompt)
        self.assertNotIn("--candidate-test", prompt)
        self.assertNotIn("round trip", prompt.casefold())

    def test_invocation_mounts_bundled_documentation_read_only(self) -> None:
        config = {
            "runtime": {
                "binary": "apptainer",
                "host_toolchain": None,
                "network_policy": "host",
                "cpus": None,
                "memory": None,
                "pids_limit": None,
            },
            "agent": {
                "image": "example/agent:test",
                "command": ["fake-agent"],
                "mounts": [],
                "host_binary": None,
            },
        }
        command = apptainer.invocation(
            config,
            self.root,
            self.root / "prompt.txt",
            self.root / "runtime",
            self.root / "agent-home",
            None,
            self.root / "submission-check",
        )
        self.assertIn(
            f"{apptainer.DOCUMENTATION_SOURCE}:{DOCUMENTATION_MOUNT}:ro", command
        )
        self.assertIn(
            f"{apptainer.SUBMISSION_CHECK_HELPER_SOURCE}:"
            f"{INPUT_REQUIREMENTS_HELPER_MOUNT}:ro",
            command,
        )
        self.assertIn(
            f"{apptainer.SUBMISSION_CHECK_HELPER_SOURCE}:"
            f"{SUBMISSION_CHECK_HELPER_MOUNT}:ro",
            command,
        )
        self.assertIn(
            f"{self.root / 'submission-check'}:"
            f"{apptainer.SUBMISSION_CHECK_DIRECTORY_MOUNT}:rw",
            command,
        )
        self.assertNotIn("--home", command)
        self.assertIn("--bind", command)
        self.assertIn(f"{self.root / 'agent-home'}:/agent-home:rw", command)
        self.assertIn("/usr/bin/env", command)
        self.assertIn("HOME=/agent-home", command)

    def test_environment_leaves_home_to_the_agent_process_wrapper(self) -> None:
        config = {"runtime": {"host_toolchain": None}, "agent": {"environment": []}}
        process_environment = apptainer.environment(config)
        self.assertNotIn("APPTAINERENV_HOME", process_environment)
        self.assertEqual(
            process_environment["APPTAINERENV_XDG_CACHE_HOME"], "/agent-home/.cache"
        )

    def test_environment_exposes_submission_check_socket_only_when_enabled(
        self,
    ) -> None:
        config = {"runtime": {"host_toolchain": None}, "agent": {"environment": []}}
        self.assertNotIn(
            "APPTAINERENV_RTDF_SUBMISSION_CHECK_SOCKET",
            apptainer.environment(config),
        )
        self.assertEqual(
            apptainer.environment(config, submission_check=True)[
                "APPTAINERENV_RTDF_SUBMISSION_CHECK_SOCKET"
            ],
            apptainer.SUBMISSION_CHECK_SOCKET_MOUNT,
        )

    def test_submission_check_service_returns_only_callback_result(self) -> None:
        socket_path = self.root / "submission-service/validator.sock"
        with apptainer.submission_check_service(
            socket_path,
            lambda: (False, "translation not happening for all provisions"),
        ):
            client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            client.connect(str(socket_path))
            client.sendall(b"check\n")
            response = json.loads(client.recv(4096))
            client.close()

        self.assertEqual(
            response,
            {
                "accepted": False,
                "message": "translation not happening for all provisions",
            },
        )

    def test_environment_exposes_sandbox_python_and_ninja(self) -> None:
        config = {
            "runtime": {"host_toolchain": "/toolchain"},
            "agent": {"environment": []},
        }
        path = apptainer.environment(config)["APPTAINERENV_PATH"].split(":")
        self.assertIn("/toolchain/envs/cutecat/bin", path)
        self.assertIn("/toolchain/envs/catala/bin", path)

    def test_integrity_check_rejects_prose_changes(self) -> None:
        workspace = self.root / "workspace"
        workspace.mkdir()
        (workspace / "RTDF_MANIFEST.json").write_text(
            '{"version": 1}\n', encoding="utf-8"
        )
        (workspace / "statute.catala_en").write_text(
            DOCUMENT.replace("must remain", "was not"), encoding="utf-8"
        )
        with self.assertRaisesRegex(main.RunnerError, "statute prose"):
            main.validate_workspace(self.dataset, workspace)

    def test_integrity_check_tolerates_protected_whitespace_changes(self) -> None:
        workspace = self.root / "workspace"
        workspace.mkdir()
        (workspace / "RTDF_MANIFEST.json").write_text(
            '{"version": 1}\n', encoding="utf-8"
        )
        candidate = DOCUMENT.replace(
            "```catala\n```",
            "```catala\n"
            "declaration Answer content integer\n"
            "declaration Other content integer\n"
            "```",
            1,
        ).replace(
            "```catala\n```",
            "```catala\n"
            "declaration Third content integer\n"
            "declaration Fourth content integer\n"
            "```",
            1,
        )
        candidate = candidate.replace(
            "The statute prose must remain unchanged.",
            "  The statute  prose must remain unchanged.  ",
        ).rstrip()
        (workspace / "statute.catala_en").write_text(candidate, encoding="utf-8")

        integrity = main.validate_workspace(self.dataset, workspace)

        self.assertEqual(integrity["changed_blocks"], 2)
        self.assertEqual(integrity["total_blocks"], 2)
        self.assertEqual(integrity["valid_code_blocks"], 2)

    def test_integrity_rejects_when_fewer_than_ninety_percent_have_two_code_lines(
        self,
    ) -> None:
        workspace = self.root / "insubstantial-workspace"
        workspace.mkdir()
        (workspace / "RTDF_MANIFEST.json").write_text(
            '{"version": 1}\n', encoding="utf-8"
        )
        candidate = DOCUMENT.replace(
            "```catala\n```",
            "```catala\n# marker\ndeclaration Answer content integer\n```",
            1,
        ).replace(
            "```catala\n```",
            "```catala\n# first comment\n# second comment\n```",
            1,
        )
        (workspace / "statute.catala_en").write_text(candidate, encoding="utf-8")

        with self.assertRaisesRegex(
            main.RunnerError,
            "translation not happening for all provisions",
        ):
            main.validate_workspace(self.dataset, workspace)

    def test_valid_catala_block_accepts_exactly_two_code_lines(self) -> None:
        self.assertTrue(
            main.valid_catala_block(
                b"scope Calculate:\n  definition answer equals 42\n"
            )
        )
        self.assertFalse(
            main.valid_catala_block(b"# comments do not count\nscope Calculate:\n")
        )

    def test_integrity_rejects_exactly_half_valid_catala_and_metadata_fences(
        self,
    ) -> None:
        baseline = DOCUMENT.replace("```catala\n```", "```catala-metadata\n```", 1)
        (self.dataset / "statute.catala_en").write_text(baseline, encoding="utf-8")
        workspace = self.root / "half-valid-workspace"
        main.publish_copy(self.dataset, workspace)
        candidate = baseline.replace(
            "```catala-metadata\n```",
            "```catala-metadata\n"
            "# a comment does not count\n"
            "declaration First content integer\n"
            "declaration Second content integer\n"
            "```",
            1,
        ).replace(
            "```catala\n```",
            "```catala\n# comment only\n```",
            1,
        )
        (workspace / "statute.catala_en").write_text(candidate, encoding="utf-8")

        with self.assertRaisesRegex(
            main.RunnerError,
            "translation not happening for all provisions",
        ):
            main.validate_workspace(self.dataset, workspace)

    def test_dependency_gate_counts_only_symbols_reaching_an_output(self) -> None:
        graph = {
            "intra_scopes": {
                "Calculate": {
                    "nodes": {
                        "1": "input_value",
                        "2": "answer",
                        "3": "isolated_marker",
                    },
                    "edges": [
                        {"from": 1, "to": 2},
                        {"from": 1, "to": 3},
                    ],
                }
            },
            "inter_scopes": {
                "nodes": {"1": "Calculate"},
                "edges": [],
            },
        }
        intra, inter = main._dependency_graph_edges(graph)
        live = main._dependency_closure(intra, {"Calculate\0answer"})

        self.assertEqual(inter, {"Calculate": set()})
        self.assertIn("Calculate\0input_value", live)
        self.assertNotIn("Calculate\0isolated_marker", live)
        self.assertTrue(
            main.dependency_valid_catala_block(
                b"scope Calculate:\n  definition answer equals\n    input_value\n",
                {"Calculate"},
                {("Calculate", "answer"), ("Calculate", "input_value")},
            )
        )
        self.assertFalse(
            main.dependency_valid_catala_block(
                b"scope Calculate:\n  definition isolated_marker equals input_value\n",
                {"Calculate"},
                {("Calculate", "answer"), ("Calculate", "input_value")},
            )
        )

    def test_dependency_gate_follows_called_scopes(self) -> None:
        _, inter = main._dependency_graph_edges(
            {
                "intra_scopes": {},
                "inter_scopes": {
                    "nodes": {"1": "Helper", "2": "Calculate", "3": "Unused"},
                    "edges": [{"from": 1, "to": 2}],
                },
            }
        )

        self.assertEqual(
            main._dependency_closure(inter, {"Calculate"}),
            {"Calculate", "Helper"},
        )

    def test_unreachable_blocks_are_reported_by_rtdf_id(self) -> None:
        workspace = self.root / "reachability-workspace"
        workspace.mkdir()
        source = workspace / "statute.catala_en"
        source.write_text(
            DOCUMENT.replace(
                "```catala\n```",
                "```catala\n"
                "declaration scope Calculate:\n"
                "  output answer content integer\n"
                "```",
                1,
            ).replace(
                "```catala\n```",
                "```catala\n"
                "scope Calculate:\n"
                "  definition isolated_marker equals 0\n"
                "```",
                1,
            ),
            encoding="utf-8",
        )
        live = {
            "statute.catala_en": (
                {"Calculate"},
                {("Calculate", "answer")},
            )
        }

        with mock.patch.object(
            workspace_validation, "dependency_live_definitions", return_value=live
        ):
            unreachable = main.unreachable_catala_blocks(
                workspace, {"schema_version": 1, "requirements": []}
            )

        self.assertEqual(
            main.catala_block_ids(source), ("example/doc:b0001", "example/doc:b0002")
        )
        self.assertEqual(unreachable, ["example/doc:b0002"])

    def test_integrity_manifest_comparison_accepts_pre_gate_results(self) -> None:
        current = {
            "documents": 1,
            "changed_blocks": 2,
            "nonempty_blocks": 2,
            "total_blocks": 2,
            "valid_code_blocks": 1,
            "files": {"statute.catala_en": "abc"},
        }
        legacy = {
            key: value
            for key, value in current.items()
            if key not in {"total_blocks", "valid_code_blocks"}
        }

        self.assertTrue(main.integrity_manifest_matches(legacy, current))
        self.assertTrue(main.integrity_manifest_matches(current, current))
        self.assertFalse(
            main.integrity_manifest_matches({**legacy, "changed_blocks": 1}, current)
        )

    def test_integrity_requires_mapping_but_not_output_reachability(self) -> None:
        task = "# Required tasks\n\n- `EXAMPLE-ANSWER`: calculate the answer.\n"
        template = {
            "schema_version": 1,
            "requirements": [
                {
                    "requirement_id": "EXAMPLE-ANSWER",
                    "file": "",
                    "scope": "",
                    "output": "",
                }
            ],
        }
        (self.dataset / "example.md").write_text(task, encoding="utf-8")
        (self.dataset / main.REQUIREMENT_OUTPUTS_FILE).write_text(
            json.dumps(template), encoding="utf-8"
        )
        workspace = self.root / "mapped-workspace"
        main.publish_copy(self.dataset, workspace)
        (workspace / "statute.catala_en").write_text(
            DOCUMENT.replace(
                "```catala\n```",
                "```catala\n"
                "declaration scope Calculate:\n"
                "  input source content integer\n"
                "  output answer content integer\n"
                "```",
                1,
            ).replace(
                "```catala\n```",
                "```catala\n"
                "scope Calculate:\n"
                "  definition source equals 0\n"
                "  definition answer equals 42\n"
                "```",
                1,
            ),
            encoding="utf-8",
        )
        with self.assertRaisesRegex(main.RunnerError, "unresolved requirement"):
            main.validate_workspace(self.dataset, workspace)
        template["requirements"][0].update(
            file="statute.catala_en", scope="Calculate", output="answer"
        )
        (workspace / main.REQUIREMENT_OUTPUTS_FILE).write_text(
            json.dumps(template), encoding="utf-8"
        )
        with mock.patch.object(
            main,
            "dependency_live_definitions",
            side_effect=AssertionError(
                "the integrity gate must not inspect reachability"
            ),
        ):
            integrity = main.validate_workspace(self.dataset, workspace)
        self.assertEqual(integrity["changed_blocks"], 2)
        self.assertEqual(integrity["valid_code_blocks"], 2)

    def test_cleanup_removes_only_clerk_artifacts(self) -> None:
        workspace = self.root / "workspace"
        (workspace / "_build").mkdir(parents=True)
        (workspace / "_build/generated").write_text("generated", encoding="utf-8")
        (workspace / "_targets").mkdir()
        source = workspace / "statute.catala_en"
        source.write_text(DOCUMENT, encoding="utf-8")

        main.cleanup_clerk_artifacts(workspace)

        self.assertFalse((workspace / "_build").exists())
        self.assertFalse((workspace / "_targets").exists())
        self.assertEqual(source.read_text(encoding="utf-8"), DOCUMENT)


class VerificationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_declared_scopes_and_json_with_build_prefix(self) -> None:
        source = self.root / "example.catala_en"
        source.write_text(
            "```catala-metadata\n"
            "declaration scope First:\n  input n content integer\n"
            "declaration scope Éligibilité:\n  output ok content boolean\n"
            "```\n",
            encoding="utf-8",
        )
        self.assertEqual(main.declared_scopes(source), ["First", "Éligibilité"])
        self.assertEqual(
            main.extract_json_value('[1/2] build progress\n[{"type": "object"}, {}]\n'),
            [{"type": "object"}, {}],
        )

    def test_verification_result_contract(self) -> None:
        path = self.root / "result.json"
        value = {
            "schema_version": main.VERIFICATION_SCHEMA_VERSION,
            "cases": [
                {
                    "id": "a",
                    "source": "bobcat",
                    "status": "pass",
                    "reference_output": {"x": 1},
                    "candidate_output": {"x": 1},
                    "detail": None,
                },
                {
                    "id": "b",
                    "source": "original",
                    "status": "fail",
                    "reference_output": True,
                    "candidate_output": False,
                    "detail": "different",
                },
            ],
            "summary": {
                "total": 2,
                "passed": 1,
                "failed": 1,
                "errors": 0,
                "skipped": 0,
                "accuracy": 0.5,
            },
        }
        path.write_text(json.dumps(value), encoding="utf-8")
        self.assertEqual(apply_nl_test.validate_verification_result(path), value)
        value["summary"]["passed"] = 2
        path.write_text(json.dumps(value), encoding="utf-8")
        with self.assertRaisesRegex(main.RunnerError, "summary counts"):
            apply_nl_test.validate_verification_result(path)

    def test_requirement_outputs_resolve_against_static_schema(self) -> None:
        (self.root / "example.md").write_text(
            "- `EXAMPLE-ANSWER`: calculate the answer.\n", encoding="utf-8"
        )
        mapping = {
            "schema_version": 1,
            "requirements": [
                {
                    "requirement_id": "EXAMPLE-ANSWER",
                    "file": "example.catala_en",
                    "scope": "Calculate",
                    "output": "answer",
                }
            ],
        }
        (self.root / main.REQUIREMENT_OUTPUTS_FILE).write_text(
            json.dumps(mapping), encoding="utf-8"
        )
        candidate_format = {
            "scopes": [
                {
                    "file": "example.catala_en",
                    "scope": "Calculate",
                    "output_schema": {
                        "$ref": "#/definitions/Calculate_out",
                        "definitions": {
                            "Calculate_out": {
                                "type": "object",
                                "properties": {"answer": {"type": "integer"}},
                                "required": ["answer"],
                            }
                        },
                    },
                },
                {
                    "file": "other.catala_en",
                    "scope": "Calculate",
                    "output_schema": {
                        "type": "object",
                        "properties": {"answer": {"type": "string"}},
                    },
                },
            ]
        }
        resolved = main.validate_requirement_scope_outputs(self.root, candidate_format)
        self.assertEqual(resolved["requirements"][0]["file"], "example.catala_en")
        self.assertEqual(
            resolved["requirements"][0]["output_schema"], {"type": "integer"}
        )
        mapping["requirements"][0]["file"] = "missing.catala_en"
        (self.root / main.REQUIREMENT_OUTPUTS_FILE).write_text(
            json.dumps(mapping), encoding="utf-8"
        )
        with self.assertRaisesRegex(main.RunnerError, "missing scope"):
            main.validate_requirement_scope_outputs(self.root, candidate_format)
        mapping["requirements"][0]["file"] = "example.catala_en"
        mapping["requirements"][0]["output"] = "missing"
        (self.root / main.REQUIREMENT_OUTPUTS_FILE).write_text(
            json.dumps(mapping), encoding="utf-8"
        )
        with self.assertRaisesRegex(main.RunnerError, "missing output"):
            main.validate_requirement_scope_outputs(self.root, candidate_format)

    def test_requirement_outputs_can_come_from_protected_api_contract(self) -> None:
        (self.root / "sara.md").write_text(
            "- `SARA-TOTAL-TAX`: calculate total tax.\n", encoding="utf-8"
        )
        (self.root / "Api.catala_en").write_text(
            "# API\n\n"
            "- Requirement ID `SARA-TOTAL-TAX`: scope `TotalTax`, output "
            "`total_tax`.\n\n"
            "> Module Api\n\n"
            "```catala-metadata\n"
            "declaration scope TotalTax:\n"
            "  output total_tax content money\n"
            "```\n",
            encoding="utf-8",
        )
        mapping = main.load_requirement_outputs(self.root, require_resolved=True)
        self.assertEqual(
            mapping,
            {
                "schema_version": 1,
                "requirements": [
                    {
                        "requirement_id": "SARA-TOTAL-TAX",
                        "file": "Api.catala_en",
                        "scope": "TotalTax",
                        "output": "total_tax",
                    }
                ],
            },
        )

    def test_requirement_mapping_replaces_llm_scope_and_path_selection(self) -> None:
        schema = information_extraction._plan_schema(
            ["example.catala_en::Calculate"], ["EXAMPLE-ANSWER"]
        )
        self.assertIn("requirement_id", schema["properties"])
        self.assertNotIn("scope_id", schema["properties"])
        self.assertNotIn("output_path", schema["properties"])

    def test_input_descriptions_match_nested_schema_exactly(self) -> None:
        candidate_format = {
            "scopes": [
                {
                    "file": "example.catala_en",
                    "scope": "Calculate",
                    "input_schema": {
                        "$ref": "#/definitions/Calculate_in",
                        "definitions": {
                            "Calculate_in": {
                                "type": "object",
                                "properties": {
                                    "person": {"$ref": "#/definitions/Person"},
                                    "payments": {
                                        "type": "array",
                                        "items": {"$ref": "#/definitions/Payment"},
                                    },
                                    "status": {"$ref": "#/definitions/Status"},
                                },
                            },
                            "Person": {
                                "type": "object",
                                "properties": {"age": {"type": "integer"}},
                            },
                            "Payment": {
                                "type": "object",
                                "properties": {"amount": {"type": "number"}},
                            },
                            "Status": {
                                "type": "string",
                                "enum": ["Active", "Inactive"],
                            },
                        },
                    },
                }
            ]
        }
        descriptions = {
            "schema_version": 3,
            "fields": {
                "person": {
                    "scopes": ["example.catala_en::Calculate"],
                    "description": "The person whose eligibility is calculated.",
                },
                "person.age": {
                    "scopes": ["example.catala_en::Calculate"],
                    "description": "That person's age in completed years.",
                },
                "payments": {
                    "scopes": ["example.catala_en::Calculate"],
                    "description": "Payments received by that person.",
                },
                "payments[].amount": {
                    "scopes": ["example.catala_en::Calculate"],
                    "description": "Each payment amount in dollars.",
                },
                "status": {
                    "scopes": ["example.catala_en::Calculate"],
                    "description": "The person's status during the relevant period.",
                },
            },
            "enums": {"Status": "Whether the person was active during the period."},
            "structs": {
                "Person": "Facts about the eligibility subject.",
                "Payment": "One payment received in the relevant period.",
            },
        }
        path = self.root / main.INPUT_VARIABLE_DESCRIPTION_FILE
        path.write_text(json.dumps(descriptions), encoding="utf-8")

        self.assertEqual(
            main.validate_input_variable_descriptions(self.root, candidate_format),
            descriptions,
        )
        registry = {
            category: {
                **descriptions[category],
                f"unrelated_{category}": (
                    {
                        "scopes": ["other.catala_en::Other"],
                        "description": "Other scope.",
                    }
                    if category == "fields"
                    else "Other scope."
                ),
            }
            for category in ("fields", "enums", "structs")
        }
        relevant = information_extraction._relevant_input_descriptions(
            candidate_format["scopes"][0]["input_schema"], registry
        )
        self.assertEqual(
            relevant["fields"],
            {
                name: entry["description"]
                for name, entry in descriptions["fields"].items()
            },
        )
        self.assertEqual(relevant["enums"], descriptions["enums"])
        self.assertEqual(relevant["structs"], descriptions["structs"])
        descriptions["fields"].pop("person.age")
        path.write_text(json.dumps(descriptions), encoding="utf-8")
        with self.assertRaisesRegex(main.RunnerError, "missing=.*person.age"):
            main.validate_input_variable_descriptions(self.root, candidate_format)

    def test_input_prompt_receives_only_selected_scope_descriptions(self) -> None:
        source = self.root / "example.catala_en"
        source.write_text(
            "```catala\ndeclaration A content integer\n```\n", encoding="utf-8"
        )
        scope = {
            "file": source.name,
            "compiler_file": source.name,
            "scope": "Calculate",
            "input_schema": {
                "type": "object",
                "properties": {"amount": {"type": "number"}},
            },
        }
        selected = {
            "scope_id": "example.catala_en::Calculate",
            "fields": {"amount": "Amount paid by the claimant in dollars."},
            "enums": {},
            "structs": {},
        }
        prompt = information_extraction._input_prompt(
            {"facts": "A person paid $10.", "question": "Are they eligible?"},
            scope,
            self.root,
            selected,
        )
        self.assertIn("Amount paid by the claimant in dollars.", prompt)
        self.assertNotIn("descriptions for another scope", prompt)

    def test_strict_extraction_schema_uses_null_for_optional_fields(self) -> None:
        schema = {
            "$ref": "#/definitions/Input",
            "$schema": "http://json-schema.org/draft-04/schema#",
            "definitions": {
                "Input": {
                    "type": "object",
                    "properties": {
                        "count": {"type": "integer"},
                        "profile": {"$ref": "#/definitions/Profile"},
                        "items": {
                            "type": "array",
                            "items": {"$ref": "#/definitions/Item"},
                        },
                        "required_nullable": {"type": ["string", "null"]},
                    },
                    "required": ["count", "items", "required_nullable"],
                },
                "Profile": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "tags": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["name"],
                },
                "Item": {
                    "type": "object",
                    "properties": {
                        "value": {"type": "integer"},
                        "note": {"type": "string"},
                    },
                    "required": ["value"],
                },
            },
        }

        strict = information_extraction._strict_extraction_schema(schema)
        self.assertEqual(
            strict["required"],
            ["count", "profile", "items", "required_nullable"],
        )
        self.assertEqual(strict["properties"]["profile"]["anyOf"][-1], {"type": "null"})
        self.assertEqual(strict["definitions"]["Profile"]["required"], ["name", "tags"])
        self.assertEqual(strict["definitions"]["Item"]["required"], ["value", "note"])
        self.assertEqual(
            strict["properties"]["required_nullable"], {"type": ["string", "null"]}
        )

        extracted = {
            "count": 2,
            "profile": {"name": "Ada", "tags": None},
            "items": [{"value": 1, "note": None}],
            "required_nullable": None,
        }
        cleaned = information_extraction._strip_optional_nulls(extracted, schema)
        self.assertEqual(
            cleaned,
            {
                "count": 2,
                "profile": {"name": "Ada"},
                "items": [{"value": 1}],
                "required_nullable": None,
            },
        )
        information_extraction.Draft202012Validator(
            information_extraction._validation_schema(schema)
        ).validate(cleaned)

        omitted_profile = dict(extracted, profile=None)
        self.assertNotIn(
            "profile",
            information_extraction._strip_optional_nulls(omitted_profile, schema),
        )

    def test_output_path_projects_catala_optional_values(self) -> None:
        schema = {
            "$ref": "#/definitions/Output",
            "definitions": {
                "Output": {
                    "type": "object",
                    "properties": {
                        "required": {"type": "number"},
                        "optional": {"type": "number"},
                    },
                    "required": ["required"],
                }
            },
        }
        self.assertEqual(
            information_extraction._at_path(
                {"required": 1, "optional": 2}, ["optional"], schema
            ),
            2,
        )
        self.assertEqual(
            information_extraction._at_path({"required": 1}, ["optional"], schema), None
        )
        self.assertEqual(
            information_extraction._at_path(
                {"required": 1, "optional": None}, ["optional"], schema
            ),
            None,
        )
        with self.assertRaises(KeyError):
            information_extraction._at_path({}, ["required"], schema)

    def test_money_claim_comparison_tolerates_less_than_one_dollar(self) -> None:
        money = {"$ref": "#/definitions/money"}
        plan = {"comparison": "equals_claim", "claim": "$100"}
        self.assertTrue(information_extraction._observed_verdict("100.99", plan, money))
        self.assertFalse(
            information_extraction._observed_verdict("101.00", plan, money)
        )
        self.assertFalse(
            information_extraction._observed_verdict("101.01", plan, money)
        )
        self.assertFalse(
            information_extraction._observed_verdict(
                "100.01", plan, {"$ref": "#/definitions/decimal"}
            )
        )

    def test_sara_question_label_preserves_polarity(self) -> None:
        self.assertEqual(
            information_extraction._sara_question_label(
                "The exemption is $2,000. Contradiction"
            ),
            ("The exemption is $2,000.", False),
        )
        self.assertEqual(
            information_extraction._sara_question_label(
                "The exemption is $0. Entailment"
            ),
            ("The exemption is $0.", True),
        )

    def test_translator_trial_tool_runs_complete_staged_union(self) -> None:
        for index, source in enumerate(("original", "bobcat"), 1):
            directory = self.root / "test_cases" / source
            directory.mkdir(parents=True)
            row = {
                "target": "Reference",
                "path": index,
                "inputs": {},
                "outputs": {"result": index},
                "error": None,
                "exact": True,
            }
            (directory / "cases.jsonl").write_text(
                json.dumps(row) + "\n", encoding="utf-8"
            )
        for name in ("reference_program", "candidate_program"):
            (self.root / name).mkdir()
        (self.root / "candidate_program/program.catala_en").write_text(
            "", encoding="utf-8"
        )
        for name in ("reference_format.json", "candidate_format.json"):
            (self.root / name).write_text("{}\n", encoding="utf-8")
        translator = self.root / "translate_test_cases.py"
        translator.write_text(
            """import argparse, json
p = argparse.ArgumentParser()
p.add_argument('--reference-test')
a = p.parse_args()
row = json.loads(a.reference_test)
print(json.dumps({'target': 'Run', 'path': 'program.catala_en', 'inputs': {},
                  'outputs': row['outputs'], 'error': None, 'exact': True}))
""",
            encoding="utf-8",
        )
        binaries = self.root / "bin"
        binaries.mkdir()
        clerk = binaries / "clerk"
        clerk.write_text("#!/bin/sh\nprintf '{\"result\":1}\\n'\n", encoding="utf-8")
        clerk.chmod(0o755)
        tool = apply_nl_test.stage_translator_trial_tool(self.root)
        environment = os.environ.copy()
        environment["PATH"] = os.pathsep.join(
            (os.fspath(binaries), environment["PATH"])
        )
        completed = subprocess.run(
            [os.fspath(Path(os.sys.executable)), os.fspath(tool)],
            cwd=self.root,
            text=True,
            capture_output=True,
            check=True,
            env=environment,
        )
        feedback = json.loads(completed.stdout)
        self.assertEqual(feedback["expected_cases"], 2)
        self.assertEqual(feedback["summary"]["passed"], 1)
        self.assertEqual(feedback["summary"]["failed"], 1)
        receipt = main.load_json(tool.parent / "trial_receipt.json")
        self.assertEqual(receipt["translator_sha256"], main.sha256_file(translator))

    def test_missing_gold_leaves_ad_hoc_run_resumable(self) -> None:
        run = self.root / "run"
        run.mkdir()
        state = {"iteration": 0}
        with mock.patch.object(main, "ROOT", self.root):
            self.assertFalse(
                apply_nl_test.run_verification_stage(
                    run,
                    {"dataset": {"name": "not-a-benchmark"}},
                    state,
                )
            )

    def test_verification_stage_reuses_script_and_result_cache(self) -> None:
        gold = self.root / "gold"
        workspace = self.root / "run/workspace"
        gold.mkdir()
        workspace.mkdir(parents=True)
        for directory in (gold, workspace):
            (directory / "program.catala_en").write_text(
                "```catala-metadata\n"
                "declaration scope Run:\n"
                "  output answer content integer\n"
                "```\n",
                encoding="utf-8",
            )
            (directory / "clerk.toml").write_text("[project]\n", encoding="utf-8")
        run = workspace.parent
        input_directory = run / "input"
        input_directory.mkdir()
        (input_directory / "program.catala_en").write_text(
            "```catala-metadata\n\n```\n", encoding="utf-8"
        )
        (input_directory / "clerk.toml").write_text("[project]\n", encoding="utf-8")
        snapshot = run / "iterations/000/snapshot"
        snapshot.parent.mkdir(parents=True)
        main.publish_copy(workspace, snapshot)
        main.atomic_json(
            snapshot.parent / "snapshot.json", main.snapshot_manifest(snapshot, 0)
        )
        (workspace / "program.catala_en").write_text(
            "```catala-metadata\ndeclaration scope ChangedAfterSnapshot:\n```\n",
            encoding="utf-8",
        )
        state = {"iteration": 0, "completed_stages": ["agent"]}
        config = {
            "run_id": "run",
            "dataset": {"name": "example"},
            "runtime": {"host_toolchain": None, "timeout_seconds": 30},
        }
        script = """import argparse, json
p = argparse.ArgumentParser()
p.add_argument('--reference-test')
a = p.parse_args()
print(json.dumps(json.loads(a.reference_test)))
"""

        def generate(_temporary, destination, **_kwargs):
            destination.write_text(script, encoding="utf-8")
            return {
                "model": main.TRANSLATOR_MODEL,
                "elapsed_seconds": 1.0,
                "sha256": main.sha256_file(destination),
                "usage": {
                    "input_tokens": 1,
                    "output_tokens": 1,
                    "total_tokens": 2,
                    "count_source": "provider-reported",
                },
            }

        formats = {"schema_version": 1, "project_files": [], "scopes": []}
        with (
            mock.patch.object(
                validation_verification, "resolve_gold_dataset", return_value=gold
            ),
            mock.patch.object(
                validation_verification, "extract_input_formats", return_value=formats
            ),
            mock.patch.object(
                validation_verification, "generate_translator", side_effect=generate
            ) as called,
        ):
            self.assertTrue(apply_nl_test.run_verification_stage(run, config, state))
            self.assertEqual(called.call_count, 1)
        self.assertEqual(state["next_stage"], "reasoning_trace_diff_fuzzing")
        self.assertTrue((run / "translate_test_cases.py").is_file())
        cache = main.load_json(run / "iterations/000/validation/cache.json")
        self.assertEqual(cache["fingerprint"]["workspace"], main.tree_hash(snapshot))
        self.assertNotEqual(
            cache["fingerprint"]["workspace"], main.tree_hash(workspace)
        )

        resumed = {"iteration": 0, "completed_stages": ["agent"]}
        with (
            mock.patch.object(
                validation_verification,
                "resolve_gold_dataset",
                return_value=gold,
            ),
            mock.patch.object(
                validation_verification,
                "extract_input_formats",
                side_effect=AssertionError("cache miss"),
            ),
            mock.patch.object(
                validation_verification,
                "generate_translator",
                side_effect=AssertionError("regenerated"),
            ),
        ):
            self.assertTrue(apply_nl_test.run_verification_stage(run, config, resumed))
        self.assertEqual(resumed["status"], "verified")


class AgentAuthenticationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_claude_loads_dotenv_without_overriding_host(self) -> None:
        (self.root / ".env").write_text(
            "IGNORED=not-loaded\nCLAUDE_CODE_OAUTH_TOKEN='from-file'\n",
            encoding="utf-8",
        )
        with mock.patch.dict(
            os.environ, {"CLAUDE_CODE_OAUTH_TOKEN": "from-host"}, clear=True
        ):
            environment = claude_code.prepare_auth(self.root)
            self.assertEqual(os.environ["CLAUDE_CODE_OAUTH_TOKEN"], "from-host")
            self.assertEqual(os.environ["IGNORED"], "not-loaded")
            self.assertEqual(environment, ("CLAUDE_CODE_OAUTH_TOKEN",))

    def test_configuration_loads_and_records_every_dotenv_name(self) -> None:
        (self.root / ".env").write_text(
            "CLAUDE_CODE_OAUTH_TOKEN=subscription-token\n"
            "EXTRA_AGENT_OPTION='enabled value' # comment\n",
            encoding="utf-8",
        )
        with mock.patch.dict(os.environ, {}, clear=True):
            configured = agents.configuration(
                argparse.Namespace(
                    agent="claude-code",
                    agent_command=None,
                    agent_provider="anthropic",
                    agent_model="test-model",
                ),
                self.root,
            )
            self.assertEqual(
                configured["environment"],
                ["CLAUDE_CODE_OAUTH_TOKEN", "EXTRA_AGENT_OPTION"],
            )
            self.assertEqual(os.environ["EXTRA_AGENT_OPTION"], "enabled value")
            self.assertNotIn("subscription-token", json.dumps(configured))
            self.assertNotIn("enabled value", json.dumps(configured))

    def test_opencode_default_command_selects_provider_and_model(self) -> None:
        configured = agents.configuration(
            argparse.Namespace(
                agent="opencode",
                agent_command=None,
                agent_provider="deepinfra",
                agent_model="zai-org/GLM-5.3-Flash",
            ),
            self.root,
        )
        self.assertEqual(
            configured["command"],
            [
                "opencode",
                "run",
                "--format",
                "json",
                "--model",
                "deepinfra/zai-org/GLM-5.3-Flash",
            ],
        )

    def test_codex_default_command_selects_model(self) -> None:
        configured = agents.configuration(
            argparse.Namespace(
                agent="codex",
                agent_command=None,
                agent_provider="openai",
                agent_model="gpt-5.6-luna",
            ),
            self.root,
        )
        self.assertEqual(configured["command"][-3:], ["--model", "gpt-5.6-luna", "-"])

    def test_opencode_explicit_command_remains_an_override(self) -> None:
        configured = agents.configuration(
            argparse.Namespace(
                agent="opencode",
                agent_command='["custom-opencode", "run"]',
                agent_provider="deepinfra",
                agent_model="zai-org/GLM-5.3-Flash",
            ),
            self.root,
        )
        self.assertEqual(configured["command"], ["custom-opencode", "run"])

    def test_codex_stages_credential_and_persists_refresh(self) -> None:
        codex_home = self.root / "codex-home"
        codex_home.mkdir()
        credential = codex_home / "auth.json"
        credential.write_text('{"token": "old"}\n', encoding="utf-8")
        agent_home = self.root / "agent-home"
        agent_home.mkdir()

        with mock.patch.dict(os.environ, {"CODEX_HOME": str(codex_home)}, clear=True):
            self.assertEqual(codex.prepare_auth(self.root), ())
            codex.stage_auth(agent_home)
            staged = agent_home / ".codex/auth.json"
            self.assertEqual(json.loads(staged.read_text()), {"token": "old"})
            self.assertEqual(staged.stat().st_mode & 0o777, 0o600)

            staged.write_text('{"token": "refreshed"}\n', encoding="utf-8")
            codex.persist_auth(agent_home)
        self.assertEqual(json.loads(credential.read_text()), {"token": "refreshed"})
        self.assertEqual(credential.stat().st_mode & 0o777, 0o600)


if __name__ == "__main__":
    unittest.main()
