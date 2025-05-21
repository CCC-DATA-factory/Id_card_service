import json
import re
from typing import List, Optional


def contains_arabic(text: str) -> bool:
    arabic_char_pattern = re.compile(r'[\u0600-\u06FF]')
    return bool(arabic_char_pattern.search(text))

def extract_json_list_from_response(text: str) -> List[dict]:
    match = re.search(r'```json\s*(\[[\s\S]*?\])\s*```', text, re.DOTALL)
    if not match:
        return []
    return json.loads(match.group(1))

def extract_json_from_response(text: str) -> Optional[dict]:
    match = re.search(r'```json\s*(\{.*?\})\s*```', text, re.DOTALL)
    if not match:
        return None
    return json.loads(match.group(1))

def split_batches(data: List[dict], batch_size: int) -> List[List[dict]]:
    return [data[i:i + batch_size] for i in range(0, len(data), batch_size)]

def is_invalid_id_card_message(text: str) -> bool:
    return bool(re.search(r'invalid.*id\s*card', text, re.IGNORECASE))

def build_prompt(batch: List[dict]) -> str:
    return (
        "You are an assistant specialized in transcribing and translating Tunisian ID card fields from Arabic.\n"
        "- Transcribe all **names** and **places** into Latin script using official Tunisian transliteration rules.\n"
        "- Translate the `job` field from Arabic to English (e.g., \"تلميذ\" → \"Student\").\n"
        "- Translate the `address` field from Arabic to English (e.g., \"10, نهج 9 أفريل, اريانة\" → \"10, 9 April Street, Ariana\").\n"
        "- Convert `dateOfBirth` to YYYY/MM/DD format.\n"
        "- Convert `dateOfCreation` to YYYY/MM/DD format.\n"
        "- Do not change the `idNumber`, it must remain the same.\n"
        "- **The output must contain no Arabic characters anywhere.** All fields must be fully transliterated or translated into Latin script or English.\n\n"
        "Return a JSON list like this:\n"
        """```json
[
  {
    "idNumber": "...",
    "lastName": "...",
    "firstName": "...",
    "fatherFullName": "...",
    "dateOfBirth": "...",
    "placeOfBirth": "...",
    "motherFullName": "...",
    "job": "...",
    "address": "...",
    "dateOfCreation": "..."
  }
]
```"""
        f"\n\nInput data:\n{json.dumps(batch, ensure_ascii=False, indent=2)}"
    )


