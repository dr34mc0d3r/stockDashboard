"""Model registry: save/load a trained model as one self-contained `.pt` file.

Each artifact bundles three things that must travel together to reproduce an
inference: the model **weights**, the **hyperparams** needed to rebuild the
architecture, and the **scaler** stats (so new data is normalized identically to
training). Artifacts live under `artifacts/` (gitignored) named by run id.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import torch

# src/backend/artifacts/
ARTIFACT_DIR = Path(__file__).resolve().parent.parent / "artifacts"


def artifact_path(run_id: int, stage: str) -> Path:
    return ARTIFACT_DIR / f"{stage}_run{run_id}.pt"


def save(
    run_id: int,
    stage: str,
    model: torch.nn.Module,
    hyperparams: dict,
    scaler: dict,
    n_features: int,
    metrics: dict | None = None,
) -> str:
    """Persist a trained model bundle; returns the artifact path as a string."""
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    path = artifact_path(run_id, stage)
    torch.save(
        {
            "stage": stage,
            "state_dict": model.state_dict(),
            "hyperparams": hyperparams,
            "scaler": scaler,
            "n_features": n_features,
            "metrics": metrics,
        },
        path,
    )
    return str(path)


def load(path: str) -> dict[str, Any]:
    """Load a saved bundle (caller rebuilds the model from its hyperparams)."""
    return torch.load(path, map_location="cpu", weights_only=False)
