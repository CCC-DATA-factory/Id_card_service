import io
import logging
import time
from typing import List
from PIL import Image, UnidentifiedImageError

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from models.combined import TunisianIDCardResponse
from config import MAX_HEIGHT, MAX_WIDTH, PROMPT_TUNISIAN_ID, PROMPT_TUNISIAN_ID_BATCH_MESSY_V2, PV_PATH
from utils.prompt_utils import resize_id_card_image, save_pv
from api import llm

logger = logging.getLogger(__name__)
router = APIRouter()

# Dummy image (20x20 transparent)
def create_dummy_image():
    return Image.new("RGB", (20, 20), color=(255, 255, 255))

@router.post("/id_cards_batch")
async def id_cards_batch(
    request: Request,
    fronts: List[UploadFile] = File(None),
    backs: List[UploadFile] = File(None)
):
    start = time.time()
    logger.info("[API] /id_cards called")

    try:
        if not fronts or not backs:
            raise HTTPException(status_code=400, detail="Both fronts and backs lists are required.")

        if len(fronts) != len(backs):
            raise HTTPException(status_code=400, detail="Fronts and backs lists must have the same length.")

        batch_inputs = []
        for i, (front, back) in enumerate(zip(fronts, backs), start=1):
            try:
                front_img = Image.open(io.BytesIO(await front.read())) if front else create_dummy_image()
            except (UnidentifiedImageError, Exception):
                logger.warning(f"[WARN] Invalid or missing front image for card {i}. Using dummy.")
                front_img = create_dummy_image()

            try:
                back_img = Image.open(io.BytesIO(await back.read())) if back else create_dummy_image()
            except (UnidentifiedImageError, Exception):
                logger.warning(f"[WARN] Invalid or missing back image for card {i}. Using dummy.")
                back_img = create_dummy_image()

            front_resized = resize_id_card_image(front_img, MAX_WIDTH, MAX_HEIGHT)
            back_resized = resize_id_card_image(back_img, MAX_WIDTH, MAX_HEIGHT)

            batch_inputs.append([front_resized, back_resized])

        result_with_pv = await llm.process_task_async(
            [PROMPT_TUNISIAN_ID_BATCH_MESSY_V2] + [img for pair in batch_inputs for img in pair],
            TunisianIDCardResponse  
        )

        if result_with_pv.get("status") == "error":
            logger.warning(f"[LLM] LLM processing failed: {result_with_pv.get('error_msg')}")
            raise HTTPException(
                status_code=503,
                detail=result_with_pv.get("error_msg", "LLM failed to process the request.")
            )

        try:
            save_pv("tunisian_id_card_batch", result_with_pv["pv"], save_dir=PV_PATH)
        except Exception as e:
            logger.warning(f"[PV] Failed to save prompt-value log: {e}")

        duration = time.time() - start
        return {
            "data": [res.model_dump() for res in result_with_pv["result"]],
            "audit": result_with_pv["pv"],
            "duration": str(duration)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[SERVER] Unexpected error in /id_cards: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="An error occurred during processing. Please try again later."
        )