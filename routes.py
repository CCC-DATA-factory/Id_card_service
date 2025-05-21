import io
import time
from fastapi import APIRouter, Body, HTTPException, UploadFile, File
from PIL import Image
from pydantic import ValidationError

from models import TunisianIDCardFront, TunisianIDCardBack, TunisianIDCardData
from llm import LLM
from utils import (
    extract_json_list_from_response, extract_json_from_response,
    split_batches, build_prompt, is_invalid_id_card_message, contains_arabic
)

router = APIRouter()
MAX_RETRIES = 3
MAX_BATCH_SIZE = 20

llm = LLM()


@router.post("/transcript", response_model=list[TunisianIDCardData])
async def process_id_card_list(data: list[TunisianIDCardData]):
    print("[API] /transcript called")
    input_dicts = [item.dict() for item in data]
    batches = split_batches(input_dicts, MAX_BATCH_SIZE)
    print(f"[INFO] Split input into {len(batches)} batch(es)")
    results = []

    for batch_index, batch in enumerate(batches):
        print(f"[BATCH {batch_index}] Processing batch with {len(batch)} item(s)")
        for attempt in range(1, MAX_RETRIES + 1):
            print(f"[BATCH {batch_index}] Attempt {attempt} using API key index {llm.key_index}")
            try:
                response = llm.generate([build_prompt(batch)])
                print(f"[BATCH {batch_index}] LLM call succeeded")

                parsed = extract_json_list_from_response(response.text.strip())
                print(f"[BATCH {batch_index}] Parsed {len(parsed)} item(s)")

                if any(
                    contains_arabic(str(value))
                    for item in parsed
                    for value in item.values() if isinstance(value, str)
                ):
                    print(f"[BATCH {batch_index}] Arabic detected in output, retrying...")
                    raise ValueError("Arabic characters detected in output, retrying...")

                validated = [TunisianIDCardData(**item) for item in parsed]
                results.extend(validated)
                print(f"[BATCH {batch_index}] Batch validated and added to results")
                break
            except Exception as e:
                print(f"[ERROR] Batch {batch_index} failed on attempt {attempt}: {e}")
                if attempt == MAX_RETRIES:
                    raise HTTPException(status_code=500, detail=f"Error processing batch: {e}")
                llm.rotate_key()
                time.sleep(1)

    print(f"[RESULT] Total valid items: {len(results)}")
    return results


async def process_image_with_prompt(image: UploadFile, prompt: str, schema):
    print("[API] Image processing request received")
    img = Image.open(io.BytesIO(await image.read()))
    for attempt in range(1, MAX_RETRIES + 1):
        print(f"[IMAGE] Attempt {attempt} using API key index {llm.key_index}")
        try:
            response = llm.generate([prompt, img])
            text = response.text.strip()
            print("[IMAGE] LLM call succeeded")

            if is_invalid_id_card_message(text):
                print("[IMAGE] Detected invalid ID card")
                raise HTTPException(status_code=400, detail="Invalid ID card")

            parsed = extract_json_from_response(text)
            print("[IMAGE] JSON parsed successfully")
            obj = schema(**parsed)
            print("[IMAGE] Schema validation successful")
            return obj
        except Exception as e:
            print(f"[ERROR] Image processing failed on attempt {attempt}: {e}")
            if attempt == MAX_RETRIES:
                raise HTTPException(status_code=500, detail=f"Failed after retries: {e}")
            llm.rotate_key()
            time.sleep(1)


@router.post("/front", response_model=TunisianIDCardFront)
async def extract_front(image: UploadFile = File(...)):
    print("[API] /extract/front called")
    prompt = (
        "You are an assistant specialized in extracting information from images of Tunisian ID cards front side. "
        "If the image is not a Tunisian ID card front, respond with this message: invalid id card. "
        "Extract the following details from the image: idNumber, lastName, firstName, fatherFullName, dateOfBirth, placeOfBirth. "
        "Output format must be JSON."
    )
    return await process_image_with_prompt(image, prompt, TunisianIDCardFront)


@router.post("/back", response_model=TunisianIDCardBack)
async def extract_back(image: UploadFile = File(...)):
    print("[API] /extract/back called")
    prompt = (
        "You are an assistant specialized in extracting information from images of Tunisian ID cards back side. "
        "If the image is not a Tunisian ID card back, respond with this message: invalid id card. "
        "Extract the following details from the image: motherFullName, job, address, dateOfCreation. "
        "Output format must be JSON."
    )
    return await process_image_with_prompt(image, prompt, TunisianIDCardBack)

@router.post("/add_api_key")
async def add_api_key(api_key: str = Body(..., embed=True)):
    print("[API] /add_api_key called")
    try:
        llm.add_api_key(api_key)
        return {"message": "API key added successfully.", "total_keys": len(llm.api_keys)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to add API key: {e}")