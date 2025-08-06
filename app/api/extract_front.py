import io
import logging
import time
from PIL import Image, UnidentifiedImageError

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from config import MAX_HEIGHT, MAX_WIDTH, PROMPT_TUNISIAN_ID_FRONT, PV_PATH
from utils.prompt_utils import resize_id_card_image, save_pv
from models.id_card import FrontResponse, TunisianIDCardFront
from api import llm

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/front", response_model=FrontResponse)
async def extract_front(request: Request, image: UploadFile = File(...)):
    start = time.time()
    logger.info("[API] /front called")

    # Input validation
    if not image or image.filename == "":
        raise HTTPException(status_code=400, detail="No image file provided.")

    try:
        try:
            img = Image.open(io.BytesIO(await image.read()))
        except UnidentifiedImageError:
            raise HTTPException(status_code=400, detail="Uploaded file is not a valid image.")

        resized_img = resize_id_card_image(img, MAX_WIDTH, MAX_HEIGHT)

        result_with_pv = await llm.process_task_async(
            [PROMPT_TUNISIAN_ID_FRONT, resized_img],
            TunisianIDCardFront
        )

        if result_with_pv.get("status") == "error":
            logger.warning(f"[LLM] LLM processing failed: {result_with_pv.get('error_msg')}")
            raise HTTPException(
                status_code=503,
                detail=result_with_pv.get("error_msg", "LLM failed to process the request.")
            )

        try:
            save_pv(indicator="tunisian_id_front", pv=result_with_pv["pv"], save_dir=PV_PATH)
        except Exception as e:
            logger.warning(f"[PV] Failed to save prompt value info: {e}")

        duration = time.time() - start
        return FrontResponse(
            data=result_with_pv["result"],
            audit=result_with_pv["pv"],
            duration=str(duration)
        )

    except HTTPException:
        raise  # re-raise known FastAPI errors

    except Exception as e:
        logger.error(f"[SERVER] Unexpected error in /front: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="An error occurred during processing. Please try again later."
        )
