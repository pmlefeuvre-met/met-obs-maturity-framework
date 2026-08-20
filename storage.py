"""File-based persistence for saved institute assessments (YAML). No Streamlit
imports.

One YAML file per institute under `saved/` (e.g. `saved/MetNo.yaml`), not
append-only history: saving overwrites the prior file for that institute.
The confirm-before-overwrite prompt lives in the main app script; this module
just does the read/write. Plain YAML (not a DB) so saved assessments stay human-
readable, greppable, and diffable in git, matching the fa1/fa2/fa3.yaml
source content convention.

The file only stores what can't be recomputed: `answers` (declared levels /
checked criteria). Scores are cheap to derive from `answers` via
`scoring.score_all`, so they're never persisted -- keeps the YAML concise and
means there's nothing to go stale. Each answer key is also stripped of its
redundant "{institute}::" prefix before writing (the file is already scoped
to one institute) and restored on read, so the app's session_state keys don't
need to change.

Every save also writes a per-assessor snapshot under `saved/history/
<institute>/<assessor-slug>.yaml`, keyed by assessor name rather than a
timestamp. This lets an assessor find their own last save for an institute
later even if someone else has since overwritten the shared file above —
it's a personal "undo the other person's overwrite" slot, not a full
version history.

`export_yaml`/`import_yaml` expose the same doc shape as plain strings, for a
client-side download/upload round trip (see the sidebar's Export/Import
controls) independent of server-side `saved/` persistence entirely.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone

import yaml

SAVE_DIR = "saved"
HISTORY_DIR = os.path.join(SAVE_DIR, "history")


@dataclass(frozen=True)
class SavedAssessment:
    institute: str
    assessor_name: str
    saved_at: str  # ISO 8601 UTC timestamp
    answers: dict  # session_state key -> value, for every key prefixed "{institute}::"


def _path(institute: str) -> str:
    return os.path.join(SAVE_DIR, f"{institute}.yaml")


def _slugify(name: str) -> str:
    """Sanitize a free-text assessor name into a safe filename component
    (no auth on this field, so guard against path traversal / separators)."""
    slug = re.sub(r"[^A-Za-z0-9_-]+", "_", name.strip()).strip("_")
    return slug[:80] or "assessor"


def _history_path(institute: str, assessor_name: str) -> str:
    return os.path.join(HISTORY_DIR, institute, f"{_slugify(assessor_name)}.yaml")


def _strip_prefix(institute: str, answers: dict) -> dict:
    prefix = f"{institute}::"
    return {(k[len(prefix):] if k.startswith(prefix) else k): v for k, v in answers.items()}


def _add_prefix(institute: str, answers: dict) -> dict:
    prefix = f"{institute}::"
    return {(k if k.startswith(prefix) else prefix + k): v for k, v in answers.items()}


def _to_doc(institute: str, assessor_name: str, saved_at: str, answers: dict) -> dict:
    return {
        "institute": institute,
        "assessor_name": assessor_name,
        "saved_at": saved_at,
        "answers": _strip_prefix(institute, answers),
    }


def _from_doc(doc: dict) -> SavedAssessment:
    institute = doc["institute"]
    return SavedAssessment(
        institute=institute,
        assessor_name=doc["assessor_name"],
        saved_at=doc["saved_at"],
        answers=_add_prefix(institute, doc.get("answers") or {}),
    )


def _read(path: str) -> SavedAssessment | None:
    if not os.path.exists(path):
        return None
    with open(path) as f:
        doc = yaml.safe_load(f)
    if not doc:
        return None
    return _from_doc(doc)


def get_assessment(institute: str) -> SavedAssessment | None:
    return _read(_path(institute))


def get_assessor_history(institute: str, assessor_name: str) -> SavedAssessment | None:
    return _read(_history_path(institute, assessor_name))


def save_assessment(institute: str, assessor_name: str, answers: dict) -> SavedAssessment:
    saved_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    doc = _to_doc(institute, assessor_name, saved_at, answers)

    os.makedirs(SAVE_DIR, exist_ok=True)
    with open(_path(institute), "w") as f:
        yaml.safe_dump(doc, f, sort_keys=False, allow_unicode=True)

    history_path = _history_path(institute, assessor_name)
    os.makedirs(os.path.dirname(history_path), exist_ok=True)
    with open(history_path, "w") as f:
        yaml.safe_dump(doc, f, sort_keys=False, allow_unicode=True)

    return SavedAssessment(institute, assessor_name, saved_at, answers)


def export_yaml(institute: str, assessor_name: str, answers: dict) -> str:
    """Serialize one institute's current answers to a YAML string (same shape
    as the on-disk save file) for the user to download and keep/share as a
    local file, independent of server-side persistence."""
    saved_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    doc = _to_doc(institute, assessor_name or "unknown", saved_at, answers)
    return yaml.safe_dump(doc, sort_keys=False, allow_unicode=True)


def import_yaml(text: str, target_institute: str) -> SavedAssessment:
    """Parse an uploaded YAML export and re-namespace its answers for
    `target_institute` (the currently selected institute in the UI), regardless
    of which institute the file was originally exported for -- the `institute`
    field on the returned SavedAssessment is the ORIGINAL one recorded in the
    file, kept for display/mismatch warnings only.

    Raises ValueError if the text isn't parseable YAML or doesn't look like a
    recognized export (e.g. the wrong file was uploaded) -- yaml.safe_load
    already rules out arbitrary object construction, this just checks the
    expected shape.
    """
    try:
        doc = yaml.safe_load(text)
    except yaml.YAMLError as e:
        raise ValueError("Not valid YAML.") from e
    if not isinstance(doc, dict) or "answers" not in doc:
        raise ValueError("Not a recognized assessment export.")
    source_institute = doc.get("institute") or target_institute
    return SavedAssessment(
        institute=source_institute,
        assessor_name=doc.get("assessor_name") or "unknown",
        saved_at=doc.get("saved_at") or "",
        answers=_add_prefix(target_institute, doc.get("answers") or {}),
    )


def list_assessments() -> list[SavedAssessment]:
    if not os.path.isdir(SAVE_DIR):
        return []
    results = []
    for fname in sorted(os.listdir(SAVE_DIR)):
        if fname.endswith(".yaml"):
            saved = get_assessment(fname[: -len(".yaml")])
            if saved:
                results.append(saved)
    return results
