"""
Pine Script converter API routes.
"""

from fastapi import APIRouter, HTTPException
from ...schemas.converter import PineConvertRequest, PineConvertResponse
from ...services import converter_service

router = APIRouter(prefix="/converter", tags=["converter"])


@router.post("/pine-to-python", response_model=PineConvertResponse)
async def convert_pine(req: PineConvertRequest):
    """Convert Pine Script to Python or vice versa."""
    try:
        result = converter_service.convert_pine(
            code=req.code,
            direction=req.direction,
            model=req.model,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Conversion failed: {e}")
