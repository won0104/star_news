"""Capture the local Python import closure that defines staged runtime behavior.

Repository HEAD is provenance. This snapshot is a byte-level compatibility gate
for downstream Gold-only checkpoints and predicted evaluator artifacts.
"""

from __future__ import annotations

import ast
from hashlib import sha256
import importlib.util
import json
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[2]
ENTRYPOINTS = (
    "training/v3_pretraining/staged.py",
    "training/v3_pretraining/harness.py",
    "training/v3_pretraining/targets.py",
    "training/v3_pretraining/metric_policy.py",
    "training/v3_pretraining/evaluation.py",
    "training/v3_pretraining/phase_evaluation.py",
    "training/v3_pretraining/epoch_selection.py",
    "training/v3_pretraining/calibration_table.py",
    "training/v3_pretraining/code_snapshot.py",
    "training/scripts/v3_staged_train.py",
    "runtime/v3_pretraining/serving.py",
)
TRAINING_ENTRYPOINTS = tuple(path for path in ENTRYPOINTS
                             if path not in ("runtime/v3_pretraining/serving.py",
                                             "training/v3_pretraining/phase_evaluation.py",
                                             "training/v3_pretraining/epoch_selection.py",
                                             "training/v3_pretraining/calibration_table.py",
                                             "training/scripts/v3_staged_train.py",
                                             "training/v3_pretraining/evaluation.py",
                                             "training/v3_pretraining/metric_policy.py"))
# These imports serve predicted diagnostics or Phase 1-only metric selection.
# The Phase 2–6 Gold optimizer never calls them, so their changes must not
# invalidate a completed downstream training checkpoint.
TRAINING_EXCLUDED = (
    "runtime/v3_pretraining/entity_pair_blocking.py",
    "runtime/v3_pretraining/relation_routing.py",
    "runtime/v3_pretraining/serving.py",
    "runtime/v3_pretraining/source_funnel.py",
    "training/v3_pretraining/evaluation.py",
    "training/v3_pretraining/epoch_selection.py",
    "training/v3_pretraining/metric_policy.py",
    "training/v3_pretraining/phase_evaluation.py",
    "training/v3_pretraining/predicted_source_replay.py",
)


def _module_name(path: Path) -> str:
    parts = path.with_suffix("").parts
    return ".".join(parts[:-1] if parts[-1] == "__init__" else parts)


def _local_module(root: Path, name: str) -> Path | None:
    if not name or name.split(".", 1)[0] not in {"training", "runtime", "models"}:
        return None
    relative = Path(*name.split("."))
    for candidate in (relative.with_suffix(".py"), relative / "__init__.py"):
        if (root / candidate).is_file():
            return candidate
    return None


def _imports(root: Path, relative: Path) -> set[Path]:
    tree = ast.parse((root / relative).read_text(encoding="utf-8"),
                     filename=str(relative))
    current = _module_name(relative)
    package = current if relative.name == "__init__.py" else current.rpartition(".")[0]
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = importlib.util.resolve_name(
                    "." * node.level + (node.module or ""), package)
            else:
                base = node.module or ""
            names.add(base)
            names.update(base + "." + alias.name for alias in node.names)
    result = set()
    for name in names:
        candidate = _local_module(root, name)
        if candidate is not None:
            result.add(candidate)
    return result


def relevant_code_snapshot(root: Path = PROJECT,
                           entrypoints: tuple[str, ...] = ENTRYPOINTS,
                           excluded: tuple[str, ...] = ()) -> dict:
    """Hash all reachable local modules and package initializers, in path order."""
    root = Path(root)
    pending = {Path(value) for value in entrypoints}
    skipped = {Path(value) for value in excluded}
    visited: set[Path] = set()
    while pending:
        relative = pending.pop()
        if relative in visited or relative in skipped:
            continue
        if not (root / relative).is_file() or relative.suffix != ".py":
            raise ValueError(f"relevant code module missing: {relative}")
        visited.add(relative)
        pending.update(_imports(root, relative) - visited)
        for parent in list(relative.parents)[:-1]:
            initializer = parent / "__init__.py"
            if (root / initializer).is_file() and initializer not in visited:
                pending.add(initializer)
    files = {path.as_posix(): sha256((root / path).read_bytes()).hexdigest()
             for path in sorted(visited)}
    digest = sha256(json.dumps(files, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return {"files": files, "sha256": digest}


def training_code_snapshot() -> dict:
    """Gate Gold training behavior without binding predicted evaluator code."""
    return relevant_code_snapshot(
        entrypoints=TRAINING_ENTRYPOINTS, excluded=TRAINING_EXCLUDED)


def selection_code_snapshot() -> dict:
    """Bind downstream epoch selection independently of Gold train readiness."""
    return relevant_code_snapshot(
        entrypoints=("training/v3_pretraining/epoch_selection.py",
                     "training/v3_pretraining/code_snapshot.py"))
