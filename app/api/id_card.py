import io
import logging
import time
from PIL import Image, UnidentifiedImageError

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from models.combined import TunisianIDCardResponse
from config import MAX_HEIGHT, MAX_WIDTH, PROMPT_TUNISIAN_ID, PV_PATH
from utils.prompt_utils import resize_id_card_image, save_pv
from api import llm

logger = logging.getLogger(__name__)
router = APIRouter()

# Dummy image (20x20 transparent)
def create_dummy_image():
    return Image.new("RGB", (20, 20), color=(255, 255, 255))

@router.post("/id_card")
async def id_card(request: Request, front: UploadFile = File(None), back: UploadFile = File(None)):
    start = time.time()
    logger.info("[API] /id_card called")

    try:
        if not front and not back:
            raise HTTPException(status_code=400, detail="At least one image (front or back) is required.")

        # FRONT IMAGE
        try:
            front_img = Image.open(io.BytesIO(await front.read())) if front else create_dummy_image()
        except (UnidentifiedImageError, Exception):
            logger.warning("[WARN] Invalid or missing front image. Using dummy.")
            front_img = create_dummy_image()

        # BACK IMAGE
        try:
            back_img = Image.open(io.BytesIO(await back.read())) if back else create_dummy_image()
        except (UnidentifiedImageError, Exception):
            logger.warning("[WARN] Invalid or missing back image. Using dummy.")
            back_img = create_dummy_image()

        front_resized = resize_id_card_image(front_img, MAX_WIDTH, MAX_HEIGHT)
        back_resized = resize_id_card_image(back_img, MAX_WIDTH, MAX_HEIGHT)

        result_with_pv = await llm.process_task_async(
            [PROMPT_TUNISIAN_ID, front_resized, back_resized],
            TunisianIDCardResponse
        )

        if result_with_pv.get("status") == "error":
            logger.warning(f"[LLM] LLM processing failed: {result_with_pv.get('error_msg')}")
            raise HTTPException(
                status_code=503,
                detail=result_with_pv.get("error_msg", "LLM failed to process the request.")
            )

        try:
            save_pv("tunisian_id_card_all", result_with_pv["pv"], save_dir=PV_PATH)
        except Exception as e:
            logger.warning(f"[PV] Failed to save prompt-value log: {e}")

        duration = time.time() - start
        return {
            "data": result_with_pv["result"].model_dump(),
            "audit": result_with_pv["pv"],
            "duration": str(duration)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[SERVER] Unexpected error in /id_card: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="An error occurred during processing. Please try again later."
        )
