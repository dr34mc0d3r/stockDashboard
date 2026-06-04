"""Tests for the Alpaca news client — urlopen monkeypatched, no network."""

import io
import json
import urllib.parse

import pytest

from services.alpaca_client import AlpacaError
from services.sentiment import news_client


class FakeResponse(io.BytesIO):
    """Minimal context-manager wrapper mimicking urlopen's response."""

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def make_urlopen(pages):
    """A fake urlopen serving canned JSON pages and recording each request."""
    calls = []

    def fake_urlopen(req, context=None):
        calls.append(req)
        payload = pages[min(len(calls) - 1, len(pages) - 1)]
        return FakeResponse(json.dumps(payload).encode())

    return fake_urlopen, calls


def article(i, headline="TSLA beats estimates", ts="2025-06-01T12:00:00Z"):
    return {
        "id": i,
        "created_at": ts,
        "headline": headline,
        "source": "benzinga",
        "url": "http://x",
    }


def test_fetch_follows_pagination_and_parses(monkeypatch):
    pages = [
        {"news": [article(1), article(2)], "next_page_token": "tok-2"},
        {"news": [article(3, ts="2025-06-02T09:30:00Z")], "next_page_token": None},
    ]
    fake, calls = make_urlopen(pages)
    monkeypatch.setattr(news_client.urllib.request, "urlopen", fake)

    out = news_client.fetch_news("TSLA", "2025-06-01", "2025-06-30")

    assert [a["id"] for a in out] == ["1", "2", "3"]
    assert out[0]["headline"] == "TSLA beats estimates"
    assert out[2]["ts"].year == 2025 and out[2]["ts"].tzinfo is None  # naive UTC
    # Two requests: the second carries the page token; both carry auth + params.
    assert len(calls) == 2
    q2 = urllib.parse.parse_qs(urllib.parse.urlparse(calls[1].full_url).query)
    assert q2["page_token"] == ["tok-2"]
    assert q2["include_content"] == ["false"]
    assert calls[0].get_header("Apca-api-key-id")  # auth headers present


def test_fetch_caps_at_max_articles(monkeypatch):
    pages = [{"news": [article(i) for i in range(1, 51)], "next_page_token": "more"}]
    fake, calls = make_urlopen(pages)
    monkeypatch.setattr(news_client.urllib.request, "urlopen", fake)

    out = news_client.fetch_news("TSLA", "2025-06-01", "2025-06-30", max_articles=10)

    assert len(out) == 10
    assert len(calls) == 1  # stopped without following the token
    q1 = urllib.parse.parse_qs(urllib.parse.urlparse(calls[0].full_url).query)
    assert q1["limit"] == ["10"]  # asks only for what it needs


def test_fetch_dedupes_and_skips_empty_headlines(monkeypatch):
    pages = [
        {
            "news": [article(1), article(1), article(2, headline="  ")],
            "next_page_token": None,
        }
    ]
    fake, _ = make_urlopen(pages)
    monkeypatch.setattr(news_client.urllib.request, "urlopen", fake)

    out = news_client.fetch_news("TSLA", "2025-06-01", "2025-06-30")

    assert [a["id"] for a in out] == ["1"]


def test_missing_credentials_is_a_config_error(monkeypatch):
    monkeypatch.setattr(news_client, "ALPACA_API_KEY", "")
    with pytest.raises(AlpacaError) as err:
        news_client.fetch_news("TSLA", "2025-06-01", "2025-06-30")
    assert err.value.status_code == 500
