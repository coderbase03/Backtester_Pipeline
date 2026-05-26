"""
Data management API routes.
"""

from fastapi import APIRouter, HTTPException
from ...schemas.data import (
    DataDownloadRequest,
    BulkDownloadRequest,
    DataDownloadResponse,
    SymbolInfo,
)
from ...services import data_service

router = APIRouter(prefix="/data", tags=["data"])


@router.post("/download", response_model=DataDownloadResponse)
async def download_data(req: DataDownloadRequest):
    """Download market data for a symbol."""
    result = data_service.download_data(
        symbol=req.symbol,
        source=req.source,
        exchange=req.exchange,
        interval=req.interval,
        n_bars=req.n_bars,
    )
    return result


@router.post("/download/bulk")
async def bulk_download(req: BulkDownloadRequest):
    """Download data for multiple symbols."""
    results = []
    for sym in req.symbols:
        r = data_service.download_data(
            symbol=sym,
            source=req.source,
            exchange=req.exchange,
            interval=req.interval,
            n_bars=req.n_bars,
        )
        results.append(r)

    success = sum(1 for r in results if r["success"])
    return {
        "results": results,
        "total": len(results),
        "success_count": success,
    }


@router.get("/symbols", response_model=list[SymbolInfo])
async def get_symbols():
    """List cached symbols."""
    return data_service.get_cached_symbols()


@router.get("/summary")
async def get_data_summary():
    """Per-symbol-timeframe data summary with date ranges and bar counts."""
    return data_service.get_data_summary()
