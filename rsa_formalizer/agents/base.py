from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from rsa_formalizer.stages.utils.guidance import (
    canonical_dataset_name,
    semantic_guidance,
)


WORKSPACE_MOUNT = "/workspace"
PROMPT_MOUNT = "/rsa/prompt.txt"
FEEDBACK_MOUNT = "/rsa/feedback"
DOCUMENTATION_MOUNT = "/rsa/catala-book"
SUBMISSION_CHECK_HELPER_MOUNT = "/rsa/check_submission.sh"
REGENERATE_ANALYSIS_HELPER_MOUNT = "/rsa/regenerate_scope_analysis.py"
MINI_SWE_AGENT_HELPER_MOUNT = "/rsa/run_mini_swe_agent.py"


class AgentConfigurationError(ValueError):
    pass


@dataclass(frozen=True)
class AgentDefinition:
    name: str
    default_command: tuple[str, ...]
    prompt_builder: Callable[[str, bool], str]
    prepare_auth: Callable[[Path], tuple[str, ...]] | None = None
    stage_auth: Callable[[Path], None] | None = None
    persist_auth: Callable[[Path], None] | None = None
    prefer_host_binary: bool = True
    configure_default_command: (
        Callable[[list[str], str | None, str], list[str]] | None
    ) = None

    def command(
        self, override: str | None, provider: str | None, model: str
    ) -> list[str]:
        if override is None:
            command = list(self.default_command)
            if self.configure_default_command is not None:
                command = self.configure_default_command(command, provider, model)
            return command
        try:
            command = json.loads(override)
        except json.JSONDecodeError as error:
            raise AgentConfigurationError(
                "--agent-command must be a JSON array of strings"
            ) from error
        if (
            not isinstance(command, list)
            or not command
            or not all(isinstance(item, str) and item for item in command)
        ):
            raise AgentConfigurationError(
                "--agent-command must be a non-empty JSON array of non-empty strings"
            )
        return command


def formalization_prompt(dataset_name: str, feedback_available: bool) -> str:
    feedback = (
        f"Read the previous disagreement report mounted read-only at {FEEDBACK_MOUNT}. Your goal is to analyze and resolve \
these issues by deciding whether the attached natural language reasoning is wrong or your Catala implementation is wrong. \
If Catala implementation is wrong, fix it.\n"
        if feedback_available  # Non-initial runs
        else "You must formalize the entire dataset in a single run; don't stop until you achieve the best possible draft.\n"
    )
    semantic_interface = semantic_guidance(dataset_name)
    guidance_name = canonical_dataset_name(dataset_name) or dataset_name
    uses_api_contract = guidance_name in {"airline", "sara"}
    sara_fixed_inputs = guidance_name == "sara"
    output_contract_guidance = (
        "The dataset supplies `Api.catala_en` as the evaluator-facing contract. "
        "Its protected prose fixes each requirement ID, scope, and output, and "
        "its metadata fence predeclares the required scope and output variable. "
        "Do not rename or remove those scopes or outputs. "
        + (
            "For SARA, keep the predeclared `world`, `taxpayer`, and `period` "
            "inputs as the complete public input contract. "
            if sara_fixed_inputs
            else "Add factual inputs to the API scope. "
        )
        + "Add internal variables and section subscopes to the API declaration, "
        "and implement only cross-section "
        "composition in the API definition. `Definitions.catala_en` is exclusively "
        "for shared factual types and provision-neutral helpers; it must not contain "
        "statutory rules, required outputs, or API orchestration. Neither Definitions "
        "nor Api may contain RSA/XML block annotations.\n\n"
        + "Do not edit `Definitions.catala_en`; it is the fixed shared input "
        "contract.\n\n"
        if uses_api_contract
        else "Each bullet has a stable requirement ID. Before finishing, fill "
        f"`{WORKSPACE_MOUNT}/REQUIREMENT_OUTPUTS.json` with exactly one mapping "
        "for every ID. Each mapping names the Catala source file, an implemented "
        "machine-callable scope in that file, and one top-level output variable "
        "of that scope. Filenames, scope names, and output variable names are "
        "case-sensitive. The harness will derive and validate the output schema "
        "statically; do not add output paths or type descriptions to this file.\n\n"
    )
    helper_contract = (
        "the protected API contract"
        if uses_api_contract
        else "every requirement mapping"
    )
    test_requirement = (
        "" if uses_api_contract
        else "finish by running `clerk test .` and fixing every reported error. "
    )
    local_checks = (
        """The workspace is an isolated Clerk project. Run these commands from
{WORKSPACE_MOUNT} early and repeatedly:

    clerk start
    clerk typecheck .
    clerk build ocaml/Api.cmo
    clerk test .

`clerk start` initializes the standard library in the temporary build directory;
`clerk typecheck .` checks every Catala document; `clerk build ocaml/Api.cmo`
compiles the evaluator API and its dependencies, checking module exports; and
`clerk test .` runs any local test scopes. Scopes used across modules must be
exported through `catala-metadata` declarations. Do not stop while these checks
still fail. The protected evaluator tests run during verification
after submission; they are not in this workspace.
"""
        if uses_api_contract
        else """The workspace is an isolated Clerk project. Run these commands from
{WORKSPACE_MOUNT} early and repeatedly:

    clerk start
    clerk typecheck .
    clerk test .

`clerk start` initializes the standard library in the temporary build directory;
`clerk typecheck .` builds and checks every Catala document; and `clerk test .`
runs every input-free test scope. To execute a particular input-free scope, use:

    clerk run path/to/document.catala_* --scope=ScopeName

Add small input-free test scopes inside
existing Catala fences when useful, and run them with `clerk test .` or the
targeted `clerk run` command. Do not stop while typechecking or tests still fail.
Stopping when the draft feels complete only asks the harness to validate it; it
does not establish that the Catala is valid or semantically correct.
"""
    ).format(WORKSPACE_MOUNT=WORKSPACE_MOUNT)
    interface_guidance = (
        "It lists the observable tasks required by the human-authored tests. "
        "Implement the predeclared evaluator-facing interface in `Api.catala_en`; "
        + (
            "use its fixed factual inputs and choose the internal decomposition. "
            if sara_fixed_inputs
            else "choose the factual input types and internal decomposition. "
        )
        if uses_api_contract
        else "It lists the observable tasks required by the human-authored tests, but "
        "deliberately does not specify an interface. Expose machine-callable scopes "
        "for those tasks. Choose your own input types, output types, scope names, "
        "and internal decomposition. "
    )
    guidance = (
        "\n\n# Required functionality\n\n"
        f"Read `{WORKSPACE_MOUNT}/{guidance_name}.md`. Ignore any directions "
        "there about generating or editing an input-description JSON file; "
        "this runner uses Catala declarations and their JSON schema directly. "
        f"{interface_guidance}"
        "Inputs must represent case facts rather than conclusions "
        "that the statute or policy is supposed to derive. "
        "Statutory intermediate quantities must be derived by the Catala program "
        "and must not be required as API inputs merely because a provision refers "
        "to them. "
        f"{output_contract_guidance}"
        f"After the Catala scopes typecheck and {helper_contract} is complete, "
        f"{test_requirement}"
        f"Run `{SUBMISSION_CHECK_HELPER_MOUNT} /workspace` as the final "
        "submission check and fix any reported errors.\n\n"
        f"{semantic_interface}\n"
        if semantic_interface
        else ""
    )
    edit_policy = (
        "Edit only text inside existing Catala fences. In `Api.catala_en`, "
        "keep the protected requirement prose and every predeclared scope/output "
        "name unchanged; add internal declarations, subscopes, and "
        "definitions needed to implement it. Never edit statute prose, RSA "
        "comments or IDs, requirement IDs, fence delimiters, the manifest, "
        "filenames, or any other file."
        if semantic_interface and uses_api_contract
        else "Edit only text inside existing Catala fences and the `file`, `scope`, "
        f"and `output` values in `{WORKSPACE_MOUNT}/REQUIREMENT_OUTPUTS.json`. "
        "Never edit statute prose, RSA comments or IDs, requirement IDs, "
        "fence delimiters, the manifest, filenames, or any other file."
        if semantic_interface
        else "Edit only text inside existing Catala fences. Never edit statute prose, "
        "RSA comments or IDs, fence delimiters, the manifest, filenames, or any "
        "other file."
    )
    return f"""You are formalizing the {dataset_name!r} statute dataset in Catala.

The dataset is mounted at {WORKSPACE_MOUNT}. Fill the existing
empty or incomplete `catala` and `catala-metadata` fences in the `.catala_*`
documents. Follow the supplied layout: use neutral preamble or unannotated
infrastructure fences when present, and put provision code in mapped local blocks.
Disperse declarations and scope definitions across the existing Catala fences, placing each with the statutory block it formalizes; do not collect them in one block.
For each provision-local fence, formalize the immediately preceding statutory
text in that fence so there is one-to-one correspondence between the statutory text and the formalized code.
Implementing a mapped rule in another shared block should be avoided; ALWAYS formalize it inside its corresponding provision fence. This includes mapped parent aggregation and trailing `:closing` spans; only genuinely provision-neutral infrastructure belongs in unannotated fences.
A provision fence must encode that provision's operative conditions and legal
consequence. Repeated boilerplate, copying an input to an output, returning a
constant, or adding an unrelated placeholder scope does not formalize the
provision and will be rejected. Connect provision-local rules through Catala
scope calls and dependencies into the evaluator-facing output; do not replace
them with a disconnected monolithic approximation.
Before finishing, verify that all fences are correctly filled. If any fence includes meaningless content like comments or no-op, the submission will be rejected. A single Catala scope definition can be distributed across multiple fences: repeat `scope A:` in each relevant fence, and Catala will merge those blocks into the same scope. Use this to place each rule's definition or exception beside the provision it formalizes while keeping the rule connected to a machine-callable output.

Treat absence as data, not as a convenient default. Represent every input or
intermediate fact that may legitimately be unstated as `optional of T`. In the
JSON interface an absent optional value is `null`; in Catala it is `Absent`.
Never replace absence with a fabricated ordinary value such as `0`, `$0`,
`false`, an arbitrary date, or an arbitrary enumeration case. Before using an
optional value in arithmetic, comparison, field access, a scope call, or any
other operation requiring `T`, inspect it with a complete `match` covering both
`Absent` and `Present content value`. The `Present` branch may use the value.
The `Absent` branch must continue through the statute's baseline, default, or
inapplicable branch without reading that value; absence must not automatically
make the enclosing calculation or final result `Absent`. Test whether a rule is
applicable before inspecting optionals used only by that rule, so irrelevant
missing facts do not block the computation. Do not manufacture a `T` merely to
unwrap an optional. Define a Catala input default only when the statute or task
specifies that exact default independently of whether the caller supplied the
fact. Keep every required evaluator-facing output non-optional; use an optional
output only when the task itself says that no result may exist.

Encode intrinsic validity constraints for factual inputs as Catala assertions
so generated cases remain within each fact's natural domain. Examples include
shares between 0% and 100%, and nonnegative ages, durations, counts, or amounts
when negative values are meaningless. Encode structural and chronological
invariants inherent in a field's definition as well. Add only constraints
imposed by the statute, task, or meaning of the fact; never narrow the domain
merely to make tests convenient. Keep the meaning of each factual input clear
in its Catala declaration.

{edit_policy} Do not add or remove fences or files. Work directly in
{WORKSPACE_MOUNT}; do not merely print proposed code in your response.

Do not browse the web, fetch repositories, or retrieve external implementations.
Network settings are blocked.

The Catala 1.2-compatible tutorial and language reference are mounted read-only
at {DOCUMENTATION_MOUNT}. Start with `{DOCUMENTATION_MOUNT}/README.md`, then use
the tutorial and reference files linked there.

{local_checks}

{feedback}{guidance}
"""
