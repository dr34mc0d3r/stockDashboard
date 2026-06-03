"""Background training loop for the Stage 2 LSTM.

Runs in a worker thread so the API stays responsive. The single source of truth
for progress is the `training_runs` row: each epoch appends a record to its
`progress` JSON and commits, so the frontend just polls `GET /runs/{id}`.

Early stopping watches validation loss with a patience window and restores the
best weights before saving — standard guard against overfitting a tiny model.
"""

from __future__ import annotations

import copy
import threading
import traceback

import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader, TensorDataset

from db import SessionLocal
from ml import registry
from ml.models.lstm import build_model
from models import TrainingRun
from services.datasets import build_dataset, load_bars

# Keep CPU usage civil on a 2-core machine.
torch.set_num_threads(2)


def _loader(X: np.ndarray, y: np.ndarray, batch: int, shuffle: bool) -> DataLoader:
    ds = TensorDataset(
        torch.from_numpy(X).float(), torch.from_numpy(y).float()
    )
    return DataLoader(ds, batch_size=batch, shuffle=shuffle)


@torch.no_grad()
def _evaluate(model: nn.Module, loader: DataLoader, loss_fn) -> tuple[float, float, dict]:
    """Return (mean_loss, accuracy, confusion) over a loader."""
    model.eval()
    total_loss, n = 0.0, 0
    tp = tn = fp = fn = 0
    for xb, yb in loader:
        logits = model(xb)
        total_loss += loss_fn(logits, yb).item() * len(yb)
        preds = (torch.sigmoid(logits) >= 0.5).float()
        tp += int(((preds == 1) & (yb == 1)).sum())
        tn += int(((preds == 0) & (yb == 0)).sum())
        fp += int(((preds == 1) & (yb == 0)).sum())
        fn += int(((preds == 0) & (yb == 1)).sum())
        n += len(yb)
    acc = (tp + tn) / n if n else 0.0
    return (total_loss / n if n else 0.0, acc,
            {"tp": tp, "tn": tn, "fp": fp, "fn": fn})


def _train(run_id: int, symbol: str, timeframe: str, hp: dict,
           start: str | None, end: str | None) -> None:
    """The actual training body (runs in a worker thread)."""
    session = SessionLocal()
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

        batch = int(hp.get("batch", 64))
        train_dl = _loader(ds.X_train, ds.y_train, batch, shuffle=True)
        val_dl = _loader(ds.X_val, ds.y_val, batch, shuffle=False)
        test_dl = _loader(ds.X_test, ds.y_test, batch, shuffle=False)

        model = build_model(ds.n_features, hp)
        optimizer = torch.optim.Adam(model.parameters(), lr=float(hp.get("lr", 1e-3)))
        loss_fn = nn.BCEWithLogitsLoss()

        epochs = int(hp.get("epochs", 30))
        patience = int(hp.get("patience", 5))
        best_val = float("inf")
        best_state = copy.deepcopy(model.state_dict())
        stale = 0
        progress: list[dict] = []

        for epoch in range(1, epochs + 1):
            model.train()
            running, seen = 0.0, 0
            for xb, yb in train_dl:
                optimizer.zero_grad()
                loss = loss_fn(model(xb), yb)
                loss.backward()
                optimizer.step()
                running += loss.item() * len(yb)
                seen += len(yb)
            train_loss = running / seen if seen else 0.0
            val_loss, val_acc, _ = _evaluate(model, val_dl, loss_fn)

            progress.append({
                "epoch": epoch,
                "train_loss": round(train_loss, 5),
                "val_loss": round(val_loss, 5),
                "val_acc": round(val_acc, 5),
            })
            # Persist progress so the UI can poll mid-training.
            run.progress = progress
            session.commit()

            if val_loss < best_val - 1e-4:
                best_val, best_state, stale = val_loss, copy.deepcopy(model.state_dict()), 0
            else:
                stale += 1
                if stale >= patience:
                    break

        # Restore best weights, then score the held-out test set.
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

        path = registry.save(run_id, run.stage, model, hp, ds.scaler.to_dict(),
                             ds.n_features, metrics)
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
    finally:
        session.close()


def start_training(run_id: int, symbol: str, timeframe: str, hp: dict,
                   start: str | None = None, end: str | None = None) -> None:
    """Spawn the training loop in a daemon thread and return immediately."""
    thread = threading.Thread(
        target=_train, args=(run_id, symbol, timeframe, hp, start, end), daemon=True
    )
    thread.start()
