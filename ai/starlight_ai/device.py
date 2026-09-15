"""Device selection: local may use CUDA; server must force CPU."""

from __future__ import annotations

import os
from typing import Literal

DeviceName = Literal["cpu", "cuda"]


def resolve_device(requested: str | None = None) -> DeviceName:
    """Resolve runtime device.

    Priority: explicit arg > ``STARLIGHT_AI_DEVICE`` > ``auto``.

    - ``cpu``: always CPU (server default).
    - ``cuda``: require CUDA or raise.
    - ``auto``: CUDA if available else CPU (local convenience).
    """
    choice = (requested or os.environ.get("STARLIGHT_AI_DEVICE") or "auto").strip().lower()
    if choice in {"cpu", "cuda", "auto"}:
        pass
    else:
        raise ValueError(f"Unsupported device={choice!r}; use cpu|cuda|auto")

    if choice == "cpu":
        return "cpu"

    import torch

    cuda_ok = bool(torch.cuda.is_available())
    if choice == "cuda":
        if not cuda_ok:
            raise RuntimeError("STARLIGHT_AI_DEVICE=cuda but torch.cuda.is_available() is False")
        return "cuda"
    return "cuda" if cuda_ok else "cpu"
