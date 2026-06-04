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


# ---------------------------------------------------------------------------
# Stage 3: the multi-task path (shared trunk, three heads)
# ---------------------------------------------------------------------------
# Parallel `_*_mt` functions rather than overloading the Stage 2 ones — each
# stage's loop stays readable on its own.


def _build_loaders_mt(ds, batch: int) -> tuple[DataLoader, DataLoader, DataLoader]:
    """Loaders whose batches carry (X, y_dir, y_ret, y_vol)."""

    def loader(X, y_dir, y_ret, y_vol, shuffle):
        tensors = TensorDataset(
            torch.from_numpy(X).float(),
            torch.from_numpy(y_dir).float(),
            torch.from_numpy(y_ret).float(),
            torch.from_numpy(y_vol).float(),
        )
        return DataLoader(tensors, batch_size=batch, shuffle=shuffle)

    return (
        loader(ds.X_train, ds.y_dir_train, ds.y_ret_train, ds.y_vol_train, True),
        loader(ds.X_val, ds.y_dir_val, ds.y_ret_val, ds.y_vol_val, False),
        loader(ds.X_test, ds.y_dir_test, ds.y_ret_test, ds.y_vol_test, False),
    )


def _multitask_loss(outputs, y_dir, y_ret, y_vol, weights, bce, mse) -> torch.Tensor:
    """Weighted sum: w_dir·BCE(direction) + w_ret·MSE(return) + w_vol·MSE(vol)."""
    dir_logit, ret_pred, vol_pred = outputs
    return (
        weights[0] * bce(dir_logit, y_dir)
        + weights[1] * mse(ret_pred, y_ret)
        + weights[2] * mse(vol_pred, y_vol)
    )


def _train_epoch_mt(model, loader, optimizer, weights, bce, mse) -> float:
    """One optimizer pass; returns the mean total (weighted) training loss."""
    model.train()
    running, seen = 0.0, 0
    for xb, yd, yr, yv in loader:
        optimizer.zero_grad()
        loss = _multitask_loss(model(xb), yd, yr, yv, weights, bce, mse)
        loss.backward()
        optimizer.step()
        running += loss.item() * len(yd)
        seen += len(yd)
    return running / seen if seen else 0.0


@torch.no_grad()
def _evaluate_mt(model, loader, weights, ret_std: float) -> dict:
    """Per-head metrics over a loader.

    Returns total weighted loss plus: direction loss/accuracy/confusion,
    return MSE (standardized) and MAE in natural log-return units, volatility
    MSE/MAE (standardized log-space — comparable across runs).
    """
    model.eval()
    bce = nn.BCEWithLogitsLoss()
    mse = nn.MSELoss()
    logits, rets, vols, y_dirs, y_rets, y_vols = [], [], [], [], [], []
    for xb, yd, yr, yv in loader:
        dir_logit, ret_pred, vol_pred = model(xb)
        logits.append(dir_logit)
        rets.append(ret_pred)
        vols.append(vol_pred)
        y_dirs.append(yd)
        y_rets.append(yr)
        y_vols.append(yv)
    if not logits:
        return {
            "loss": 0.0,
            "dir_loss": 0.0,
            "dir_acc": 0.0,
            "confusion": {"tp": 0, "tn": 0, "fp": 0, "fn": 0},
            "ret_mse": 0.0,
            "ret_mae": 0.0,
            "vol_mse": 0.0,
            "vol_mae": 0.0,
        }

    dir_logit = torch.cat(logits)
    ret_pred, vol_pred = torch.cat(rets), torch.cat(vols)
    y_dir, y_ret, y_vol = torch.cat(y_dirs), torch.cat(y_rets), torch.cat(y_vols)

    dir_loss = bce(dir_logit, y_dir).item()
    ret_mse = mse(ret_pred, y_ret).item()
    vol_mse = mse(vol_pred, y_vol).item()
    total = weights[0] * dir_loss + weights[1] * ret_mse + weights[2] * vol_mse

    preds = (torch.sigmoid(dir_logit) >= PROB_THRESHOLD).float()
    tp = int(((preds == 1) & (y_dir == 1)).sum())
    tn = int(((preds == 0) & (y_dir == 0)).sum())
    fp = int(((preds == 1) & (y_dir == 0)).sum())
    fn = int(((preds == 0) & (y_dir == 1)).sum())
    n = len(y_dir)

    return {
        "loss": total,
        "dir_loss": dir_loss,
        "dir_acc": (tp + tn) / n if n else 0.0,
        "confusion": {"tp": tp, "tn": tn, "fp": fp, "fn": fn},
        "ret_mse": ret_mse,
        # MAE back in natural log-return units: |Δ standardized| × train std.
        "ret_mae": (ret_pred - y_ret).abs().mean().item() * ret_std,
        "vol_mse": vol_mse,
        "vol_mae": (vol_pred - y_vol).abs().mean().item(),
    }


def _run_epochs_mt(model, train_dl, val_dl, optimizer, hp, ret_std, on_epoch):
    """The multi-task epoch loop; mirrors `_run_epochs` with richer progress.

    `val_loss` is the TOTAL weighted loss — the scheduler and early stopping
    key on it, and the UI's loss plot reads it. `val_acc` is the direction
    head's accuracy so the Stage 2 accuracy plot keeps working.
    """
    weights = (
        float(hp.get("w_dir", 1.0)),
        float(hp.get("w_ret", 1.0)),
        float(hp.get("w_vol", 1.0)),
    )
    bce, mse = nn.BCEWithLogitsLoss(), nn.MSELoss()
    epochs = int(hp.get("epochs", 30))
    patience = int(hp.get("patience", 5))
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
        train_loss = _train_epoch_mt(model, train_dl, optimizer, weights, bce, mse)
        val = _evaluate_mt(model, val_dl, weights, ret_std)

        progress.append(
            {
                "epoch": epoch,
                "train_loss": round(train_loss, 5),
                "val_loss": round(val["loss"], 5),
                "val_acc": round(val["dir_acc"], 5),
                "lr": optimizer.param_groups[0]["lr"],
                "dir_loss": round(val["dir_loss"], 5),
                "ret_mae": round(val["ret_mae"], 6),
                "vol_mae": round(val["vol_mae"], 5),
            }
        )
        on_epoch(progress)

        scheduler.step(val["loss"])

        if val["loss"] < best_val - EARLY_STOP_DELTA:
            best_val, best_state, stale = val["loss"], copy.deepcopy(model.state_dict()), 0
        else:
            stale += 1
            if stale >= patience:
                break

    return best_state, progress, best_val, weights


def _train_multitask(
    run_id: int, symbol: str, timeframe: str, hp: dict, start: str | None, end: str | None
) -> None:
    """The DB-status wrapper for a Stage 3 run (executes in a worker thread)."""
    # Local imports keep Stage 2 runs free of any Stage 3 import cost.
    from ml.models.multitask import build_model as build_multitask_model
    from services import bar_service
    from services.datasets import build_multitask_dataset
    from services.features import feature_pipeline

    with SessionLocal() as session:
        run = session.get(TrainingRun, run_id)
        try:
            run.status = "running"
            session.commit()

            # One query feeds both the indicator pipeline (dict bars with
            # timestamps) and the raw OHLCV array for the dataset builder.
            rows = bar_service.query_bars(session, symbol, timeframe, start, end, limit=10_000_000)
            bars = [
                {
                    "timestamp": r.ts.isoformat(),
                    "open": float(r.open),
                    "high": float(r.high),
                    "low": float(r.low),
                    "close": float(r.close),
                    "volume": int(r.volume),
                }
                for r in rows
            ]
            raw = np.array(
                [[b["open"], b["high"], b["low"], b["close"], b["volume"]] for b in bars],
                dtype=np.float64,
            )

            items = hp.get("indicators", [])
            matrix, names, feature_set = feature_pipeline.build_features(
                session, symbol, timeframe, bars, items
            )

            # Stage 4: append cached FinBERT daily-sentiment columns. Just two
            # more columns in the matrix — datasets.py needs no changes.
            sent_cfg = hp.get("sentiment") or {}
            if sent_cfg.get("enabled"):
                from services.sentiment.sentiment_features import build_sentiment_matrix

                sent_matrix, sent_names = build_sentiment_matrix(
                    session,
                    symbol,
                    [r.ts for r in rows],
                    lag_days=int(sent_cfg.get("lag_days", 1)),
                )
                matrix = np.hstack([matrix, sent_matrix])
                names = [*names, *sent_names]

            ds = build_multitask_dataset(
                raw,
                matrix,
                names,
                seq_len=int(hp.get("seq_len", 60)),
                horizon=int(hp.get("horizon", 1)),
                vol_window=int(hp.get("vol_window", 5)),
                split=tuple(hp.get("split", (0.7, 0.15, 0.15))),
            )
            train_dl, val_dl, test_dl = _build_loaders_mt(ds, int(hp.get("batch", 64)))

            model = build_multitask_model(ds.n_features, hp)
            optimizer = torch.optim.Adam(model.parameters(), lr=float(hp.get("lr", 1e-3)))

            def persist_progress(progress: list[dict]) -> None:
                run.progress = [*progress]  # new list: see Stage 2 note
                session.commit()

            best_state, progress, best_val, weights = _run_epochs_mt(
                model, train_dl, val_dl, optimizer, hp, ds.ret_stats.std, persist_progress
            )

            # Restore the best weights and score the held-out test set.
            model.load_state_dict(best_state)
            test = _evaluate_mt(model, test_dl, weights, ds.ret_stats.std)
            metrics = {
                # Direction-head keys named exactly as Stage 2 so RunsTable,
                # RunVerdict and the baseline line work unchanged.
                "test_loss": round(test["dir_loss"], 5),
                "test_acc": round(test["dir_acc"], 5),
                "confusion": test["confusion"],
                "best_val_loss": round(best_val, 5),
                "epochs_run": len(progress),
                "class_balance": ds.class_balance,
                "n_train": int(len(ds.y_dir_train)),
                "n_val": int(len(ds.y_dir_val)),
                "n_test": int(len(ds.y_dir_test)),
                # Stage 3 per-head test metrics:
                "total_test_loss": round(test["loss"], 5),
                "ret_mse": round(test["ret_mse"], 6),
                "ret_mae": round(test["ret_mae"], 6),
                "vol_mse": round(test["vol_mse"], 6),
                "vol_mae": round(test["vol_mae"], 5),
                "n_features": int(ds.n_features),
                "warmup_rows": int(ds.warmup_rows),
                "feature_set": feature_set,
            }
            path = registry.save(
                run_id,
                run.stage,
                model,
                hp,
                ds.scaler.to_dict(),
                ds.n_features,
                metrics,
                extras={
                    "ret_stats": ds.ret_stats.to_dict(),
                    "vol_stats": ds.vol_stats.to_dict(),
                    "feature_names": ds.feature_names,
                },
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


def start_training_multitask(
    run_id: int,
    symbol: str,
    timeframe: str,
    hp: dict,
    start: str | None = None,
    end: str | None = None,
) -> None:
    """Spawn the multi-task training loop in a daemon thread."""
    thread = threading.Thread(
        target=_train_multitask, args=(run_id, symbol, timeframe, hp, start, end), daemon=True
    )
    thread.start()
