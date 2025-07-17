import json
import logging
import time
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from api import llm
from models.pv import FullPromptValue
from config import MAX_BATCH_SIZE, PROMPT_TRANSCRIPTION
from exceptions.llm_exceptions import ValidationRetryError
from models.id_card import TranscriptResponse, TunisianIDCardData
from models.transcription import TranscriptionRequest
from utils.prompt_utils import save_pv, split_batches


logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/transcript", response_model=TranscriptResponse)
async def process_id_card_list(request: Request, data: list[TranscriptionRequest]):
    logger.info("[API] /transcript called")
    input_dicts = [item.dict() for item in data]
    batches = split_batches(input_dicts, MAX_BATCH_SIZE)
    logger.info(f"[INFO] Split input into {len(batches)} batch(es)")

    results = []
    merged_pv = {
        "total_api_calls": 0,
        "total_input_tokens": 0,
        "total_output_tokens": 0,
        "attempts": [],
        "keys_used": set(),
        "start_time": time.time(),
    }

    for batch_index, batch in enumerate(batches):
        logger.info(f"[BATCH {batch_index}] Processing batch with {len(batch)} item(s)")
        prompt = PROMPT_TRANSCRIPTION + json.dumps(batch, ensure_ascii=False, indent=2)

        try:
            response_with_pv = await llm.generate([prompt], output_model=TunisianIDCardData)
            parsed = response_with_pv["result"]
            pv = response_with_pv["pv"]

            merged_pv["total_api_calls"] += pv.get("total_api_calls", 0)
            merged_pv["total_input_tokens"] += pv.get("total_input_tokens", 0)
            merged_pv["total_output_tokens"] += pv.get("total_output_tokens", 0)
            merged_pv["attempts"].extend(pv.get("attempts", []))
            merged_pv["keys_used"].update(pv.get("keys_used", []))

            parsed_items = parsed if isinstance(parsed, list) else [parsed]
            results.extend(parsed_items)
            logger.info(f"[BATCH {batch_index}] Batch validated and added to results")

        except ValidationRetryError as ve:
            logger.error(f"[BATCH {batch_index}] Validation failed after retries: {ve}")
            raise HTTPException(status_code=422, detail=f"Validation failed after retries: {ve}")

        except RuntimeError as re:
            msg = str(re).lower()
            if "quota" in msg:
                logger.error(f"[BATCH {batch_index}] Quota exhausted: {re}")
                raise HTTPException(status_code=429, detail="Quota exhausted, please try later.")
            else:
                logger.error(f"[BATCH {batch_index}] Runtime error: {re}")
                raise HTTPException(status_code=503, detail="External API error, please try later.")

        except Exception as e:
            logger.error(f"[BATCH {batch_index}] Unexpected error: {e}")
            raise HTTPException(status_code=500, detail=f"Error processing batch: {e}")

    merged_pv["keys_used"] = list(merged_pv["keys_used"])
    merged_pv["duration_total"] = time.time() - merged_pv["start_time"]

    try:
        save_pv(indicator_name="id_card_transcription", pv=merged_pv)
    except Exception as e:
        logger.warning(f"[PV] Failed to save prompt value info: {e}")

    logger.info(f"[RESULT] Total valid items: {len(results)}")

    return TranscriptResponse(
        results=results,
        pv=FullPromptValue(**merged_pv)
    )
