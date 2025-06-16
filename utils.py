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
        "Vous êtes un assistant spécialisé dans la transcription et la traduction des champs des cartes d'identité tunisiennes à partir de l'arabe.\n"
        "- Transcrivez tous les **noms** et **lieux** en alphabet latin en utilisant les règles officielles de translittération tunisiennes.\n"
        "- Traduisez le champ `job` de l'arabe vers le français (ex : \"تلميذ\" → \"Élève\").\n"
        "- Traduisez le champ `address` de l'arabe vers le français (ex : \"10, نهج 9 أفريل, اريانة\" → \"10, Rue du 9 Avril, Ariana\").\n"
        "- Convertissez `dateOfBirth` au format AAAA/MM/JJ.\n"
        "- Convertissez `dateOfCreation` au format AAAA/MM/JJ.\n"
        "- Ne modifiez pas `idNumber`, il doit rester inchangé.\n"
        "- **La sortie ne doit contenir aucun caractère arabe.** Tous les champs doivent être intégralement translittérés ou traduits en alphabet latin ou en français.\n\n"
        "Retournez une liste JSON comme ceci :\n"
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
        f"\n\nDonnées d'entrée :\n{json.dumps(batch, ensure_ascii=False, indent=2)}"
    )

