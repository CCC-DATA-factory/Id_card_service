import io
import logging
from PIL import Image

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from pydantic import ValidationError
from config import MAX_HEIGHT, MAX_WIDTH, PROMPT_TUNISIAN_ID_FRONT, PV_PATH
from utils.prompt_utils import resize_id_card_image, save_pv
from exceptions.llm_exceptions import ValidationRetryError
from models.id_card import FrontResponse, TunisianIDCardFront
from api import llm


logger = logging.getLogger(__name__)
router = APIRouter()
@router.post("/front", response_model=FrontResponse)
async def extract_front(request: Request, image: UploadFile = File(...)):

    logger.info("[API] /extract/front called")
    prompt = PROMPT_TUNISIAN_ID_FRONT
    try:
        img = Image.open(io.BytesIO(await image.read()))
        resized_img = resize_id_card_image(img,MAX_WIDTH,MAX_HEIGHT)
        result_with_pv = await llm.generate([prompt, resized_img], TunisianIDCardFront)

        try:
            save_pv("tunisian_id_front", result_with_pv["pv"],save_dir=PV_PATH)
        except Exception as e:
            logger.warning(f"[PV] Failed to save prompt value info: {e}")
            
        
        return FrontResponse(
            data = result_with_pv["result"],
            audit = result_with_pv["pv"]
        )
    except ValidationRetryError as e:
        raise HTTPException(status_code=422, detail=f"Validation failed after retries: {e}")
    except RuntimeError as e:
        msg = str(e).lower()
        if "quota" in msg:
            raise HTTPException(status_code=429, detail="Quota exhausted, please try again later.")
        elif "configuration" in msg:
            raise HTTPException(status_code=500, detail="Configuration error in API keys or client.")
        else:
            raise HTTPException(status_code=503, detail="External API error, please try again later.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {e}")
