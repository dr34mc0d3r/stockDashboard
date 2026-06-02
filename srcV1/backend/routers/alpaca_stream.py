from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from services.alpaca_client_websocket import (
    DEFAULT_CHANNELS,
    DEFAULT_SYMBOLS,
    AlpacaWebSocketError,
    stream_messages,
)

router = APIRouter(prefix="/api", tags=["stream"])


def _csv(raw: str | None, default: list[str]) -> list[str]:
    if not raw:
        return default
    return [item for item in raw.split(",") if item]


@router.websocket("/stream")
async def alpaca_stream(websocket: WebSocket):
    """Proxy Alpaca's live market-data stream to the browser.

    The frontend opens a websocket to /api/stream; we connect to Alpaca,
    authenticate with the server-side credentials, and forward each batch of
    frames. Optional query params ?symbols=AAPL,MSFT and ?channels=bars,trades
    override the default subscription.
    """
    await websocket.accept()

    symbols = _csv(websocket.query_params.get("symbols"), DEFAULT_SYMBOLS)
    channels = _csv(websocket.query_params.get("channels"), DEFAULT_CHANNELS)

    try:
        async for message in stream_messages(symbols, channels):
            await websocket.send_json(message)
    except AlpacaWebSocketError as e:
        # Surface upstream/auth failures to the client before closing.
        await websocket.send_json({"error": str(e)})
        await websocket.close(code=1011)
    except WebSocketDisconnect:
        # Client went away; stream_messages closes the Alpaca socket on exit.
        pass
