import io
import time
from fastapi import Request
from fastapi import APIRouter, Body, HTTPException, UploadFile, File
from PIL import Image
from pydantic import ValidationError
from limiter_config import limiter
from models import TunisianIDCardFront, TunisianIDCardBack, TunisianIDCardData
from llm import LLM
from utils import (
    extract_json_list_from_response, extract_json_from_response,
    split_batches, build_prompt, is_invalid_id_card_message, contains_arabic
)
import logging
logger = logging.getLogger(__name__)

router = APIRouter()
MAX_RETRIES = 2
MAX_BATCH_SIZE = 20

llm = LLM()

@limiter.limit("3/minute")
@router.post("/transcript", response_model=list[TunisianIDCardData])
async def process_id_card_list(request: Request, data: list[TunisianIDCardData]):
    logger.info("[API] /transcript called")
    input_dicts = [item.dict() for item in data]
    batches = split_batches(input_dicts, MAX_BATCH_SIZE)
    logger.info(f"[INFO] Split input into {len(batches)} batch(es)")
    results = []

    for batch_index, batch in enumerate(batches):
        logger.info(f"[BATCH {batch_index}] Processing batch with {len(batch)} item(s)")
        for attempt in range(1, MAX_RETRIES + 1):
            logger.info(f"[BATCH {batch_index}] Attempt {attempt} using API key index {llm.api_key_manager.key_index}")
            try:
                response = await llm.generate([build_prompt(batch)])
                logger.info(f"[BATCH {batch_index}] LLM call succeeded")

                parsed = extract_json_list_from_response(response.text.strip())
                logger.info(f"[BATCH {batch_index}] Parsed {len(parsed)} item(s)")

                if any(
                    contains_arabic(str(value))
                    for item in parsed
                    for value in item.values() if isinstance(value, str)
                ):
                    logger.warning(f"[BATCH {batch_index}] Arabic detected in output, retrying...")
                    raise ValueError("Arabic characters detected in output, retrying...")

                validated = [TunisianIDCardData(**item) for item in parsed]
                results.extend(validated)
                logger.info(f"[BATCH {batch_index}] Batch validated and added to results")
                break
            except Exception as e:
                logger.error(f"[ERROR] Batch {batch_index} failed on attempt {attempt}: {e}")
                if attempt == MAX_RETRIES:
                    raise HTTPException(status_code=500, detail=f"Error processing batch: {e}")
                llm.rotate_key()
                time.sleep(1)

    logger.info(f"[RESULT] Total valid items: {len(results)}")
    return results


async def process_image_with_prompt(image: UploadFile, prompt: str, schema):
    logger.info("[API] Image processing request received")
    img = Image.open(io.BytesIO(await image.read()))
    for attempt in range(1, MAX_RETRIES + 1):
        logger.info(f"[IMAGE] Attempt {attempt} using API key index {llm.api_key_manager.key_index}")
        try:
            response = await llm.generate([prompt, img])
            text = response.text.strip()
            logger.info("[IMAGE] LLM call succeeded")

            if is_invalid_id_card_message(text):
                logger.warning("[IMAGE] Detected invalid ID card")
                raise HTTPException(status_code=400, detail="Invalid ID card")

            parsed = extract_json_from_response(text)
            logger.info("[IMAGE] JSON parsed successfully")
            obj = schema(**parsed)
            logger.info("[IMAGE] Schema validation successful")
            return obj
        except Exception as e:
            logger.error(f"[ERROR] Image processing failed on attempt {attempt}: {e}")
            if attempt == MAX_RETRIES:
                raise HTTPException(status_code=500, detail=f"Failed after retries: {e}")
            llm.rotate_key()
            time.sleep(1)


@limiter.limit("3/minute")
@router.post("/front", response_model=TunisianIDCardFront)
async def extract_front(request: Request, image: UploadFile = File(...)):
    logger.info("[API] /extract/front called")
    prompt = (
        "You are an assistant specialized in analyzing images of Tunisian ID cards (front side only).\n"
        "- If the image is not the front side of a Tunisian ID card, or if it is a photocopy (e.g., black and white, grayscale, low contrast, missing color features), "
        "you must respond with exactly this message and nothing else:\n\n"
        "invalid id card\n\n"
        "- Do not extract or output any information for invalid or photocopied cards.\n"
        "- If the card is valid and in color, extract the following fields:\n"
        "  • idNumber\n  • lastName\n  • firstName\n  • fatherFullName\n  • dateOfBirth\n  • placeOfBirth\n"
        "- The output must be a single valid JSON object with these fields."
    )


    return await process_image_with_prompt(image, prompt, TunisianIDCardFront)


@limiter.limit("3/minute")
@router.post("/back", response_model=TunisianIDCardBack)
async def extract_back(request: Request, image: UploadFile = File(...)):
    logger.info("[API] /extract/back called")
    prompt = (
        "You are an assistant specialized in analyzing images of Tunisian ID cards (back side only).\n"
        "- If the image is not the back side of a Tunisian ID card, or if it is a photocopy (e.g., black and white, grayscale, low contrast, or missing color features), "
        "you must respond with exactly this message and nothing else:\n\n"
        "invalid id card\n\n"
        "- Do not extract or output any information for invalid or photocopied cards.\n"
        "- If the card is valid and in color, extract the following fields:\n"
        "  • motherFullName\n  • job\n  • address\n  • dateOfCreation\n"
        "- The output must be a single valid JSON object with these fields."
    )


    return await process_image_with_prompt(image, prompt, TunisianIDCardBack)

@limiter.limit("3/minute")
@router.post("/add_api_key")
async def add_api_key(request: Request, api_key: str = Body(..., embed=True)):
    logger.info("[API] /add_api_key called")
    try:
        llm.api_key_manager.add_api_key(api_key)
        return {"message": "API key added successfully.", "total_keys": len(llm.api_key_manager.api_keys)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to add API key: {e}")