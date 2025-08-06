import json
import logging
import time
from fastapi import APIRouter, HTTPException, Request
from api import llm
from models.pv import FullPromptValue
from config import MAX_BATCH_SIZE, PROMPT_TRANSCRIPTION
from models.id_card import TranscriptResponse, TunisianIDCardData
from models.transcription import TranscriptionRequest
from utils.prompt_utils import save_pv, split_batches

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/transcript")
async def process_id_card_list(request: Request, data: list[TranscriptionRequest]):
    start = time.time()
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
            response_with_pv = await llm.process_task_async([prompt], output_model=TunisianIDCardData)

            if response_with_pv.get("status") == "error":
                logger.warning(f"[LLM] LLM processing failed: {response_with_pv.get('error_msg')}")
                raise HTTPException(
                    status_code=503,
                    detail=response_with_pv.get("error_msg", "LLM failed to process the request.")
                )

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

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"[BATCH {batch_index}] Unexpected error: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="An error occurred during processing. Please try again later.")

    merged_pv["keys_used"] = list(merged_pv["keys_used"])
    merged_pv["duration_total"] = time.time() - merged_pv["start_time"]
    merged_pv["model"] = pv["model"]
    merged_pv["instance_name"] = pv["instance_name"]
    try:
        save_pv(indicator="id_card_transcription", pv=merged_pv)
    except Exception as e:
        logger.warning(f"[PV] Failed to save prompt value info: {e}")

    logger.info(f"[RESULT] Total valid items: {len(results)}")
    duration = time.time() - start
    return {
        "results": results,
        "pv": merged_pv,
        "duration": str(duration)
    }
