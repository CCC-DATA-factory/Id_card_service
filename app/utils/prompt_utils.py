import json
import re
from typing import List, Optional, Union
from PIL import Image
import os
from datetime import datetime


def resize_id_card_image(img: Image.Image, MAX_WIDTH = 768, MAX_HEIGHT = 512) -> Image.Image:
    """
    Resize the image to a maximum size while maintaining aspect ratio and high quality.
    Ensures the resized image is optimal for Gemini Flash 2.0 token limits.
    """
    original_size = img.size
    img = img.convert("RGB") 
    img.thumbnail((MAX_WIDTH, MAX_HEIGHT), Image.LANCZOS)  
    return img

def contains_arabic(text: str) -> bool:
    arabic_char_pattern = re.compile(r'[\u0600-\u06FF]')
    return bool(arabic_char_pattern.search(text))

def extract_json_from_response(text: str) -> Union[dict, List[dict]]:
    """
    Extracts a JSON object or list of objects from an LLM response.
    The JSON content should be wrapped between ```json ... ```.

    Returns:
        A dictionary or a list of dictionaries parsed from the JSON.
        Returns an empty list if no valid JSON is found.
    """
    match = re.search(r'```json\s*([\s\S]*?)\s*```', text, re.DOTALL)
    if not match:
        return []

    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError:
        return []

def split_batches(data: List[dict], batch_size: int) -> List[List[dict]]:
    return [data[i:i + batch_size] for i in range(0, len(data), batch_size)]

def is_invalid_id_card_message(text: str) -> bool:
    return bool(re.search(r'invalid.*id\s*card', text, re.IGNORECASE))


def save_pv(indicator: str, pv: dict, save_dir: str = "logs/pv"):
    os.makedirs(save_dir, exist_ok=True)
    
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    filename = f"{timestamp}_{indicator}.json"
    path = os.path.join(save_dir, filename)

    data = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "indicator": indicator,
        "pv": pv
    }

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    return path
