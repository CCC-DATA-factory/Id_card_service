import io
import logging
import time
from PIL import Image, UnidentifiedImageError

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from fastapi.responses import PlainTextResponse
from prometheus_client import Counter, Summary, generate_latest, CONTENT_TYPE_LATEST
from models.combined import TunisianIDCardResponse
from config import MAX_HEIGHT, MAX_WIDTH, PROMPT_TUNISIAN_ID, PV_PATH
from utils.prompt_utils import resize_id_card_image, save_pv
from api import llm , validator , ocr

logger = logging.getLogger(__name__)
router = APIRouter()


# Prometheus metrics
REQUEST_COUNT = Counter("id_card_requests_total", "Total ID card requests", ["status"])
REQUEST_LATENCY = Summary("id_card_request_latency_seconds", "Latency of /id_card requests in seconds")
ERROR_COUNT = Counter("id_card_errors_total", "Total ID card errors", ["error_type"])

# Dummy image (20x20 white)
def create_dummy_image():
    return Image.new("RGB", (20, 20), color=(255, 255, 255))

@router.post("/id_card")
async def id_card(request: Request, front: UploadFile = File(None), back: UploadFile = File(None)):
    start = time.time()
    logger.info("[API] /id_card called")

    try:
        if not front and not back:
            ERROR_COUNT.labels(error_type="missing_image").inc()
            REQUEST_COUNT.labels(status="error").inc()
            raise HTTPException(status_code=400, detail="At least one image (front or back) is required.")

        # FRONT IMAGE
        try:
            front_img = Image.open(io.BytesIO(await front.read())) if front else create_dummy_image()
        except UnidentifiedImageError:
            logger.warning("[WARN] Invalid front image. Using dummy.")
            ERROR_COUNT.labels(error_type="invalid_front_image").inc()
            front_img = create_dummy_image()
        except Exception as e:
            logger.warning(f"[WARN] Front image error: {e}. Using dummy.")
            ERROR_COUNT.labels(error_type="front_image_error").inc()
            front_img = create_dummy_image()

        # BACK IMAGE
        try:
            back_img = Image.open(io.BytesIO(await back.read())) if back else create_dummy_image()
        except UnidentifiedImageError:
            logger.warning("[WARN] Invalid back image. Using dummy.")
            ERROR_COUNT.labels(error_type="invalid_back_image").inc()
            back_img = create_dummy_image()
        except Exception as e:
            logger.warning(f"[WARN] Back image error: {e}. Using dummy.")
            ERROR_COUNT.labels(error_type="back_image_error").inc()
            back_img = create_dummy_image()

        #---------------------------------------------------------------------
        #---------------------------------------------------------------------
        result = validator.validate_card_pair(front_img, back_img)
        if  result['data']['back']['status'] == "invalid" or  result['data']['front']['status'] == "invalid":
             return result
        


        #---------------------------------------------------------------------
        #---------------------------------------------------------------------    


        front_resized = resize_id_card_image(front_img, MAX_WIDTH, MAX_HEIGHT)
        back_resized = resize_id_card_image(back_img, MAX_WIDTH, MAX_HEIGHT)

        result_with_pv = await llm.process_task_async(
            [PROMPT_TUNISIAN_ID, front_resized, back_resized],
            TunisianIDCardResponse
        )

        if result_with_pv.get("status") == "error":
            ERROR_COUNT.labels(error_type="llm_error").inc()
            REQUEST_COUNT.labels(status="error").inc()
            logger.warning(f"[LLM] LLM processing failed: {result_with_pv.get('error_msg')}")
            ERROR_COUNT.labels(error_type="unexpected_error").inc()
            cin = ocr.extract_id_number(front_resized, min_confidence=0.6)
            if not cin:
                result['data']['front']['status'] = "invalid"
                return result
            #---------------------------------------------------------------------
            dummy_response = {
                    "front": {
                        "status": "Valid",
                        "data": {
                        "idNumber": cin,
                        "lastName": "UNKNOWN",
                        "firstName": "UNKNOWN",
                        "fatherFullName": "UNKNOWN",
                        "dateOfBirth": "UNKNOWN",
                        "placeOfBirth": "UNKNOWN"
                        }
                    },
                    "back": {
                        "status": "Valid",
                        "data": {
                        "motherFullName": "UNKNOWN",
                        "job": "UNKNOWN",
                        "address": "UNKNOWN",
                        "dateOfCreation": "UNKNOWN"
                        }
                    }
                    }
            return {
                "data":dummy_response,
                "audit": "OCR only - no LLM called",
                "duration": "None"
            }


        try:
            save_pv("tunisian_id_card_all", result_with_pv["pv"], save_dir=PV_PATH)
        except Exception as e:
            logger.warning(f"[PV] Failed to save prompt-value log: {e}")
            ERROR_COUNT.labels(error_type="pv_save_error").inc()

        duration = time.time() - start
        REQUEST_COUNT.labels(status="success").inc()
        REQUEST_LATENCY.observe(duration)

        return {
            "data": result_with_pv["result"].model_dump(),
            "audit": result_with_pv["pv"],
            "duration": str(duration)
        }

    except HTTPException:
        raise
    except Exception as e:
        ERROR_COUNT.labels(error_type="unexpected_error").inc()
        REQUEST_COUNT.labels(status="error").inc()
        logger.error(f"[SERVER] Unexpected error in /id_card: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="An error occurred during processing. Please try again later."
        )

@router.get("/metrics")
async def metrics():
    data = generate_latest()
    return PlainTextResponse(data, media_type=CONTENT_TYPE_LATEST)
