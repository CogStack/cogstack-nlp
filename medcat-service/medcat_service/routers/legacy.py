import logging
import traceback

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from medcat_service.dependencies import MedCatProcessorDep

router = APIRouter(tags=["Legacy"])
log = logging.getLogger(__name__)


@router.post("/api/retrain_medcat")
async def retrain_medcat(request: Request, medcat_processor: MedCatProcessorDep) -> JSONResponse:
    """
    Deprecated API.

    Retrain Medcat.

    This has been migrated from Flask to FastAPI without full testing. Contact CogStack if any issues are found.
    """

    payload = await request.json()

    if payload is None or "content" not in payload or payload["content"] is None:
        raise HTTPException(status_code=400, detail="Input Payload should be JSON with 'content'")

    try:
        result = medcat_processor.retrain_medcat(payload["content"], payload["replace_cdb"])
        app_info = medcat_processor.get_app_info()
        return JSONResponse(status_code=200, content={"result": result, "annotations": payload["content"],
                                                      "medcat_info": app_info})

    except Exception as e:
        log.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Internal processing error {e}")
