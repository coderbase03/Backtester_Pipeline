"""
WebSocket handler for real-time backtest progress.
"""

import json
import asyncio
import logging
from fastapi import WebSocket, WebSocketDisconnect

from ..services import backtest_service

logger = logging.getLogger(__name__)


async def backtest_websocket(ws: WebSocket):
    """
    WebSocket endpoint for running backtests with live progress updates.

    Client sends JSON:
        {"strategy": "supertrend", "symbol": "BTCUSDT", ...}

    Server streams:
        {"type": "progress", "message": "..."}
        {"type": "result", "data": {...}}
        {"type": "error", "message": "..."}
    """
    await ws.accept()

    try:
        raw = await ws.receive_text()
        params = json.loads(raw)

        await ws.send_json({"type": "progress", "message": "Starting backtest..."})

        result = await asyncio.to_thread(
            backtest_service.run_backtest,
            strategy_name=params.get("strategy", "supertrend"),
            symbol=params.get("symbol", "BTCUSDT"),
            source=params.get("source", "tradingview"),
            exchange=params.get("exchange"),
            interval=params.get("interval", "1h"),
            n_bars=params.get("n_bars", 1000),
            initial_cash=params.get("initial_cash", 100_000),
            commission=params.get("commission", 0.001),
            strategy_params=params.get("strategy_params"),
        )

        await ws.send_json({"type": "progress", "message": "Backtest complete, sending results..."})
        await ws.send_json({"type": "result", "data": result})

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except json.JSONDecodeError:
        await ws.send_json({"type": "error", "message": "Invalid JSON"})
    except Exception as e:
        logger.error("WebSocket backtest error: %s", e)
        try:
            await ws.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass
    finally:
        try:
            await ws.close()
        except Exception:
            pass
