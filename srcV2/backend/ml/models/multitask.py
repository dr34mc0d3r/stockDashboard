"""Stage 3 — one shared LSTM trunk, three small prediction heads.

The trunk is exactly Stage 2's LSTM (tiny, CPU-friendly). Instead of one
linear head it feeds three: direction (a logit, like Stage 2), return and
volatility (scalars, regressing the standardized targets from the dataset
builder). Multi-task learning shares the representation — the auxiliary heads
act as regularizers for each other.
"""

from __future__ import annotations

import torch
from torch import nn


class MultiTaskNet(nn.Module):
    def __init__(self, n_features: int, hidden: int = 64, layers: int = 2, dropout: float = 0.2):
        super().__init__()
        self.lstm = nn.LSTM(
            input_size=n_features,
            hidden_size=hidden,
            num_layers=layers,
            batch_first=True,
            # PyTorch only applies recurrent dropout when there are >=2 layers.
            dropout=dropout if layers > 1 else 0.0,
        )
        self.drop = nn.Dropout(dropout)
        self.head_dir = nn.Linear(hidden, 1)  # logit -> BCEWithLogitsLoss
        self.head_ret = nn.Linear(hidden, 1)  # standardized log return -> MSE
        self.head_vol = nn.Linear(hidden, 1)  # standardized log1p vol -> MSE

    def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        # x: (batch, seq_len, n_features) -> three (batch,) outputs.
        out, _ = self.lstm(x)
        z = self.drop(out[:, -1, :])  # hidden state at the final timestep
        return (
            self.head_dir(z).squeeze(-1),
            self.head_ret(z).squeeze(-1),
            self.head_vol(z).squeeze(-1),
        )


def build_model(n_features: int, hyperparams: dict) -> MultiTaskNet:
    """Construct a MultiTaskNet from a hyperparameter dict."""
    return MultiTaskNet(
        n_features=n_features,
        hidden=int(hyperparams.get("hidden", 64)),
        layers=int(hyperparams.get("layers", 2)),
        dropout=float(hyperparams.get("dropout", 0.2)),
    )
