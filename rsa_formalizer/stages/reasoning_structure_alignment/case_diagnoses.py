"""Validate the repair agent's diagnoses of all feedback cases or only remaining discrepancies."""
from __future__ import annotations

import json
from pathlib import Path

from rsa_formalizer.stages.utils.common import RunnerError
from rsa_formalizer.stages import utils as exp

FILENAME = 'case_diagnoses.json'
CLASSIFICATIONS = frozenset({'Catala wrong', 'LLM wrong', 'Both wrong', 'Unresolved'})
MAX_REPORT_BYTES = 1024 * 1024


def begin_replay(feedback: Path, snapshot_hash: str) -> None:
    """Invalidate the previous successful replay while a new one is running."""
    exp.atomic_json(feedback / 'latest_replay.json', {
        'status': 'running', 'candidate_snapshot_sha256': snapshot_hash,
        'recorded_at': exp.utc_now(),
    })


def publish_replay(feedback: Path, stage: Path, report: dict) -> None:
    """Bind the remaining-case list to the exact source snapshot replayed."""
    exp.atomic_json(feedback / 'latest_replay.json', {
        'status': 'complete',
        'attempt': stage.name,
        'candidate_snapshot_sha256': exp.tree_hash(stage / 'snapshot'),
        'remaining_case_ids': report['remaining_case_ids'],
        'evidence_index': report['evidence_index'],
        'recorded_at': exp.utc_now(),
    })


def latest_replay(feedback: Path, workspace: Path | None = None) -> dict:
    """Read the latest completed replay, with recovery for pre-marker runs."""
    pointer = feedback / 'latest_replay.json'
    try:
        if pointer.is_file():
            latest = exp.load_json(pointer)
        else:
            # Older, already-running sessions do not publish the pointer. Their
            # latest attempt still has an immutable snapshot and public index.
            reviews = feedback.parent / 'session/candidate_reviews'
            attempts = [p for p in reviews.glob('attempt-*') if p.name[8:].isdigit()]
            stage = max(attempts, key=lambda p: int(p.name[8:]))
            report = exp.load_json(stage / 'review.json')
            evidence = feedback / 'replays' / stage.name / 'index.json'
            if evidence.is_file():
                remaining = exp.load_json(evidence)['remaining_case_ids']
            else:
                comparison = exp.load_json(stage / 'comparison.json')
                remaining = remaining_cases(comparison)
            latest = {
                'status': 'complete', 'attempt': stage.name,
                'candidate_snapshot_sha256': exp.tree_hash(stage / 'snapshot'),
                'remaining_case_ids': remaining,
                'evidence_index': report.get('evidence_index'),
            }
        ids = latest.get('remaining_case_ids')
        if (latest.get('status') != 'complete' or not isinstance(ids, list)
                or any(not isinstance(identifier, str) for identifier in ids)
                or len(set(ids)) != len(ids)):
            raise ValueError('latest replay is incomplete or has an invalid remaining-case list')
        workspace = workspace if workspace is not None else feedback.parent.parent / 'workspace'
        if exp.tree_hash(workspace) != latest.get('candidate_snapshot_sha256'):
            raise ValueError('workspace changed after the latest replay')
        return latest
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise RunnerError(
            'Replay the current workspace before submitting case_diagnoses.json: '
            f'{error}'
        ) from error


def remaining_cases(comparison: dict) -> list[str]:
    """RSA includes value mismatches; baseline comparisons contain no graphs."""
    return [row['id'] for row in comparison['cases']
            if row.get('final_answer_aligned') is not True
            or (row.get('computation_graph_alignment') or {}).get('value_mismatches')]


def validate(report_path: Path, feedback: Path, *, remaining_only: bool = False,
             workspace: Path | None = None) -> list[dict[str, str]]:
    """Require exact coverage of the latest replay, or legacy initial reports."""
    try:
        index = json.loads((feedback / 'index.json').read_text(encoding='utf-8'))
        expected = {item['case_id'] for item in index['reports']}
        if remaining_only:
            expected = set(latest_replay(feedback, workspace)['remaining_case_ids'])
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise RunnerError(f'cannot read expected case diagnoses from feedback index: {error}') from error
    if report_path.is_symlink():
        raise RunnerError('case_diagnoses.json must be a regular JSON file, not a symlink')
    try:
        if report_path.stat().st_size > MAX_REPORT_BYTES:
            raise RunnerError('case_diagnoses.json exceeds the 1 MiB report limit')
        rows = json.loads(report_path.read_text(encoding='utf-8'))
    except (OSError, ValueError) as error:
        raise RunnerError(f'missing or invalid case_diagnoses.json: {error}') from error
    if not isinstance(rows, list):
        raise RunnerError('case_diagnoses.json must be a JSON list of case dictionaries')
    seen = set()
    for number, row in enumerate(rows, 1):
        if not isinstance(row, dict) or set(row) != {'case_id', 'diagnosis', 'classification'}:
            raise RunnerError(f'case diagnosis {number} must contain exactly case_id, diagnosis, classification')
        case_id = row['case_id']
        if not isinstance(case_id, str) or not case_id.strip():
            raise RunnerError(f'case diagnosis {number} has an invalid case_id')
        if case_id in seen:
            raise RunnerError(f'duplicate case diagnosis: {case_id}')
        seen.add(case_id)
        diagnosis = row['diagnosis']
        if (not isinstance(diagnosis, str) or not diagnosis.strip()
                or len(diagnosis) > 600 or any(c in diagnosis for c in '\r\n')):
            raise RunnerError(f'{case_id}: diagnosis must be a nonempty single line of at most 600 characters')
        classification = row['classification']
        if not isinstance(classification, str) or classification not in CLASSIFICATIONS:
            raise RunnerError(f'{case_id}: classification must be one of {sorted(CLASSIFICATIONS)}')
    missing, extra = sorted(expected - seen), sorted(seen - expected)
    if missing or extra:
        raise RunnerError(f'case diagnosis coverage mismatch (missing={missing}, unexpected={extra})')
    return rows
