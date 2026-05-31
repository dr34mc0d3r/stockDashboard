import asyncio
import json
from collections.abc import AsyncIterator

import websocket  # provided by the "websocket-client" package

from config import ALPACA_API_KEY, ALPACA_SECRET_KEY

# Alpaca's live market-data stream. The "iex" feed is compatible with
# free-tier credentials (matching feed=iex used by the historical REST client).
STREAM_URL = "wss://stream.data.alpaca.markets/v2/iex"

# Channels that can be subscribed to per symbol: "bars", "trades", "quotes".
DEFAULT_CHANNELS = ["bars"]
DEFAULT_SYMBOLS = ["AAPL"]


class AlpacaWebSocketError(Exception):
    """Raised when the Alpaca stream connection cannot be established."""

    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.status_code = status_code


def _auth_message() -> str:
    return json.dumps(
        {"action": "auth", "key": ALPACA_API_KEY, "secret": ALPACA_SECRET_KEY}
    )


def _subscribe_message(symbols: list[str], channels: list[str]) -> str:
    msg = {"action": "subscribe"}
    for channel in channels:
        msg[channel] = symbols
    return json.dumps(msg)


def _expect_success(reply, expected_msg: str) -> None:
    """Alpaca replies with a list of frames; raise unless one is the success
    message we're waiting for (e.g. "connected" or "authenticated")."""
    frames = reply if isinstance(reply, list) else [reply]
    for frame in frames:
        if frame.get("T") == "success" and frame.get("msg") == expected_msg:
            return
        if frame.get("T") == "error":
            raise AlpacaWebSocketError(
                f"Alpaca stream error: {frame.get('msg', frame)}", status_code=401
            )
    raise AlpacaWebSocketError(
        f"Unexpected Alpaca reply (waiting for '{expected_msg}'): {frames}"
    )


class AlpacaWebSocketClient:
    """Synchronous wrapper around the Alpaca live market-data stream.

    The websocket-client library is blocking, so the async helpers below run
    these methods in a worker thread to avoid stalling the event loop.
    """

    def __init__(
        self,
        symbols: list[str] | None = None,
        channels: list[str] | None = None,
    ):
        if not ALPACA_API_KEY or not ALPACA_SECRET_KEY:
            raise AlpacaWebSocketError(
                "Alpaca API credentials are not configured.", status_code=500
            )
        self.symbols = [s.upper() for s in (symbols or DEFAULT_SYMBOLS)]
        self.channels = channels or DEFAULT_CHANNELS
        self._ws: websocket.WebSocket | None = None

    def connect(self) -> dict:
        """Open the socket, authenticate, and subscribe.

        Returns the subscription-confirmation message from Alpaca. Raises
        AlpacaWebSocketError on connection or authentication failure.
        """
        try:
            self._ws = websocket.create_connection(STREAM_URL, timeout=30)
        except Exception as e:  # OSError, WebSocketException, etc.
            raise AlpacaWebSocketError(f"Could not reach Alpaca stream: {e}")

        # The server greets us with [{"T":"success","msg":"connected"}].
        _expect_success(json.loads(self._ws.recv()), "connected")

        self._ws.send(_auth_message())
        _expect_success(json.loads(self._ws.recv()), "authenticated")

        self._ws.send(_subscribe_message(self.symbols, self.channels))
        return json.loads(self._ws.recv())  # subscription confirmation

    def recv(self) -> list | None:
        """Block for the next batch of frames. Returns None when closed."""
        if self._ws is None:
            return None
        try:
            raw = self._ws.recv()
        except websocket.WebSocketConnectionClosedException:
            return None
        return json.loads(raw) if raw else None

    def close(self) -> None:
        if self._ws is not None:
            try:
                self._ws.close()
            finally:
                self._ws = None


async def stream_messages(
    symbols: list[str] | None = None,
    channels: list[str] | None = None,
) -> AsyncIterator[list]:
    """Yield batches of frames from the Alpaca market-data stream.

    Connection and each blocking read run in a worker thread so the FastAPI
    event loop stays responsive. The socket is always closed on teardown,
    including when the consumer stops iterating early.
    """
    client = AlpacaWebSocketClient(symbols, channels)
    subscription = await asyncio.to_thread(client.connect)
    try:
        yield subscription
        while True:
            message = await asyncio.to_thread(client.recv)
            if message is None:
                break
            yield message
    finally:
        await asyncio.to_thread(client.close)
