"""Stage 2 — a small LSTM that classifies next-bar direction (up/down).

Deliberately tiny (hidden<=64, <=2 layers) so it trains in seconds-to-minutes on
a 2-core CPU. The LSTM reads a window of scaled OHLCV bars; we take the hidden
state at the final timestep, drop it through a linear head, and emit a single
logit for P(up). Binary cross-entropy with logits is the loss.
"""

from __future__ import annotations

import torch
from torch import nn


class LSTMClassifier(nn.Module):
    def __init__(self, n_features: int, hidden: int = 64, layers: int = 2,
                 dropout: float = 0.2):
        super().__init__()
        self.lstm = nn.LSTM(
            input_size=n_features,
            hidden_size=hidden,
            num_layers=layers,
            batch_first=True,
            # PyTorch only applies recurrent dropout when there are >=2 layers.
            dropout=dropout if layers > 1 else 0.0,
        )
        self.head = nn.Sequential(
            nn.Dropout(dropout),
            nn.Linear(hidden, 1),  # single logit -> BCEWithLogitsLoss
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: (batch, seq_len, n_features)
        out, _ = self.lstm(x)
        last = out[:, -1, :]  # hidden state at the final timestep
        return self.head(last).squeeze(-1)  # (batch,)


def build_model(n_features: int, hyperparams: dict) -> LSTMClassifier:
    """Construct an LSTMClassifier from a hyperparameter dict."""
    return LSTMClassifier(
        n_features=n_features,
        hidden=int(hyperparams.get("hidden", 64)),
        layers=int(hyperparams.get("layers", 2)),
        dropout=float(hyperparams.get("dropout", 0.2)),
    )
