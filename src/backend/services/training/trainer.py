"""Background training loop for the Stage 2 LSTM.

Runs in a worker thread so the API stays responsive. The single source of truth
for progress is the `training_runs` row: each epoch appends a record to its
`progress` JSON and commits, so the frontend just polls `GET /runs/{id}`.

Structure (top to bottom = the life of a run):
  _build_loaders   raw splits → torch DataLoaders
  _train_epoch     one optimizer pass over the training set
  _evaluate        loss/accuracy/confusion over any loader
  _run_epochs      the epoch loop: scheduler, early stopping, progress callback
  _score_and_save  best weights → test scoring → artifact on disk
  _train           thin DB-status wrapper around all of the above
  start_training   spawns _train in a daemon thread
"""

from __future__ import annotations

import copy
import threading
import traceback
from collections.abc import Callable

import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader, TensorDataset

from constants import EARLY_STOP_DELTA, PROB_THRESHOLD
from db import SessionLocal
from ml import registry
from ml.models.lstm import build_model
from models import TrainingRun
from services.datasets import Dataset, build_dataset, load_bars

# Keep CPU usage civil on a 2-core machine.
torch.set_num_threads(2)


def _loader(X: np.ndarray, y: np.ndarray, batch: int, shuffle: bool) -> DataLoader:
    ds = TensorDataset(torch.from_numpy(X).float(), torch.from_numpy(y).float())
    return DataLoader(ds, batch_size=batch, shuffle=shuffle)


def _build_loaders(ds: Dataset, batch: int) -> tuple[DataLoader, DataLoader, DataLoader]:
    """Train/val/test DataLoaders; only the training set is shuffled."""
    return (
        _loader(ds.X_train, ds.y_train, batch, shuffle=True),
        _loader(ds.X_val, ds.y_val, batch, shuffle=False),
        _loader(ds.X_test, ds.y_test, batch, shuffle=False),
    )


def _train_epoch(model: nn.Module, loader: DataLoader, optimizer, loss_fn) -> float:
    """One full pass over the training set; returns the mean training loss."""
    model.train()
    running, seen = 0.0, 0
    for xb, yb in loader:
        optimizer.zero_grad()
        loss = loss_fn(model(xb), yb)
        loss.backward()
        optimizer.step()
        running += loss.item() * len(yb)
        seen += len(yb)
    return running / seen if seen else 0.0


@torch.no_grad()
def _evaluate(model: nn.Module, loader: DataLoader, loss_fn) -> tuple[float, float, dict]:
    """Return (mean_loss, accuracy, confusion) over a loader."""
    model.eval()
    total_loss, n = 0.0, 0
    tp = tn = fp = fn = 0
    for xb, yb in loader:
        logits = model(xb)
        total_loss += loss_fn(logits, yb).item() * len(yb)
        preds = (torch.sigmoid(logits) >= PROB_THRESHOLD).float()
        tp += int(((preds == 1) & (yb == 1)).sum())
        tn += int(((preds == 0) & (yb == 0)).sum())
        fp += int(((preds == 1) & (yb == 0)).sum())
        fn += int(((preds == 0) & (yb == 1)).sum())
        n += len(yb)
    acc = (tp + tn) / n if n else 0.0
    return (total_loss / n if n else 0.0, acc, {"tp": tp, "tn": tn, "fp": fp, "fn": fn})


def _run_epochs(
    model: nn.Module,
    train_dl: DataLoader,
    val_dl: DataLoader,
    optimizer,
    loss_fn,
    hp: dict,
    on_epoch: Callable[[list[dict]], None],
) -> tuple[dict, list[dict], float]:
    """The epoch loop: train, validate, schedule the LR, stop early.

    Pure training logic — persistence happens through the `on_epoch` callback,
    which receives the progress list after every epoch.

    Returns (best_state_dict, progress, best_val_loss).
    """
    epochs = int(hp.get("epochs", 30))
    patience = int(hp.get("patience", 5))
    # Halve the LR when val loss plateaus (lr_patience < early-stop patience,
    # so the schedule kicks in before training gives up). Per-epoch LR is
    # recorded so the UI can chart it live.
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
        optimizer,
        mode="min",
        factor=float(hp.get("lr_factor", 0.5)),
        patience=int(hp.get("lr_patience", 2)),
    )
    best_val = float("inf")
    best_state = copy.deepcopy(model.state_dict())
    stale = 0
    progress: list[dict] = []

    for epoch in range(1, epochs + 1):
        train_loss = _train_epoch(model, train_dl, optimizer, loss_fn)
        val_loss, val_acc, _ = _evaluate(model, val_dl, loss_fn)

        progress.append(
            {
                "epoch": epoch,
                "train_loss": round(train_loss, 5),
                "val_loss": round(val_loss, 5),
                "val_acc": round(val_acc, 5),
                # LR used during this epoch (capture before the scheduler steps).
                "lr": optimizer.param_groups[0]["lr"],
            }
        )
        on_epoch(progress)

        scheduler.step(val_loss)  # may reduce the LR for the next epoch

        if val_loss < best_val - EARLY_STOP_DELTA:
            best_val, best_state, stale = val_loss, copy.deepcopy(model.state_dict()), 0
        else:
            stale += 1
            if stale >= patience:
                break

    return best_state, progress, best_val


def _score_and_save(
    run_id: int,
    stage: str,
    model: nn.Module,
    best_state: dict,
    test_dl: DataLoader,
    loss_fn,
    ds: Dataset,
    hp: dict,
    progress: list[dict],
    best_val: float,
) -> tuple[dict, str]:
    """Restore the best weights, score the held-out test set, save the artifact.

    Returns (metrics, artifact_path).
    """
    model.load_state_dict(best_state)
    test_loss, test_acc, confusion = _evaluate(model, test_dl, loss_fn)
    metrics = {
        "test_loss": round(test_loss, 5),
        "test_acc": round(test_acc, 5),
        "confusion": confusion,
        "best_val_loss": round(best_val, 5),
        "epochs_run": len(progress),
        "class_balance": ds.class_balance,
        "n_train": int(len(ds.y_train)),
        "n_val": int(len(ds.y_val)),
        "n_test": int(len(ds.y_test)),
    }
    path = registry.save(run_id, stage, model, hp, ds.scaler.to_dict(), ds.n_features, metrics)
    return metrics, path


def _train(
    run_id: int, symbol: str, timeframe: str, hp: dict, start: str | None, end: str | None
) -> None:
    """The DB-status wrapper around a whole run (executes in a worker thread)."""
    with SessionLocal() as session:
        run = session.get(TrainingRun, run_id)
        try:
            run.status = "running"
            session.commit()

            raw = load_bars(session, symbol, timeframe, start, end)
            ds = build_dataset(
                raw,
                seq_len=int(hp.get("seq_len", 60)),
                horizon=int(hp.get("horizon", 1)),
                split=tuple(hp.get("split", (0.7, 0.15, 0.15))),
            )
            train_dl, val_dl, test_dl = _build_loaders(ds, int(hp.get("batch", 64)))

            model = build_model(ds.n_features, hp)
            optimizer = torch.optim.Adam(model.parameters(), lr=float(hp.get("lr", 1e-3)))
            loss_fn = nn.BCEWithLogitsLoss()

            def persist_progress(progress: list[dict]) -> None:
                # Assign a *new* list each epoch — SQLAlchemy won't flag an
                # in-place mutation of the same JSON list object as dirty, so it
                # would otherwise never update.
                run.progress = [*progress]
                session.commit()

            best_state, progress, best_val = _run_epochs(
                model, train_dl, val_dl, optimizer, loss_fn, hp, persist_progress
            )
            metrics, path = _score_and_save(
                run_id,
                run.stage,
                model,
                best_state,
                test_dl,
                loss_fn,
                ds,
                hp,
                progress,
                best_val,
            )

            run.metrics = metrics
            run.artifact_path = path
            run.status = "done"
            session.commit()
        except Exception as e:  # noqa: BLE001 — record any failure on the run row
            session.rollback()
            run = session.get(TrainingRun, run_id)
            run.status = "error"
            run.detail = f"{e}\n{traceback.format_exc()}"
            session.commit()


def start_training(
    run_id: int,
    symbol: str,
    timeframe: str,
    hp: dict,
    start: str | None = None,
    end: str | None = None,
) -> None:
    """Spawn the training loop in a daemon thread and return immediately."""
    thread = threading.Thread(
        target=_train, args=(run_id, symbol, timeframe, hp, start, end), daemon=True
    )
    thread.start()
