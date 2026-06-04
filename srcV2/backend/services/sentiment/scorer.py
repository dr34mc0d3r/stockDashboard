"""Lazy FinBERT batch scorer.

ALL transformers/model imports happen inside functions, so the app (and every
non-Stage-4 test) runs without the optional `sentiment` dependency group
installed. The model loads once per process (~440MB download on the very
first call, then served from the Hugging Face cache) and runs on CPU with the
same 2-thread cap as training.
"""

from __future__ import annotations

MODEL_NAME = "ProsusAI/finbert"
BATCH_SIZE = 16  # keeps peak memory flat on a 2-core machine
MAX_TOKENS = 64  # headlines are short; truncation guards the odd essay-length one

_model = None
_tokenizer = None


def _load():
    """Load tokenizer+model once per process (lazy, cached in module globals)."""
    global _model, _tokenizer
    if _model is None:
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        torch.set_num_threads(2)
        _tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
        _model = AutoModelForSequenceClassification.from_pretrained(MODEL_NAME)
        _model.eval()
    return _tokenizer, _model


def score_headlines(headlines: list[str]) -> list[dict]:
    """FinBERT class probabilities per headline: [{pos, neg, neutral}, ...].

    Batched softmax over the model's three classes, mapped through its own
    id2label config (so a different label order can never silently flip
    positive and negative).
    """
    import torch

    tokenizer, model = _load()
    labels = {i: label.lower() for i, label in model.config.id2label.items()}

    out: list[dict] = []
    for lo in range(0, len(headlines), BATCH_SIZE):
        batch = headlines[lo : lo + BATCH_SIZE]
        enc = tokenizer(
            batch, return_tensors="pt", truncation=True, max_length=MAX_TOKENS, padding=True
        )
        with torch.no_grad():
            probs = torch.softmax(model(**enc).logits, dim=-1)
        for row in probs:
            scores = {labels[i]: float(row[i]) for i in range(len(labels))}
            out.append(
                {
                    "pos": scores.get("positive", 0.0),
                    "neg": scores.get("negative", 0.0),
                    "neutral": scores.get("neutral", 0.0),
                }
            )
    return out
