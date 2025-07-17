#-------------------------------------------------
#--------------PROMPTS----------------------------

PROMPT_TUNISIAN_ID_BACK = (
    "You are an assistant specialized in analyzing images of Tunisian ID cards (back side only).\n"
    "- If the image is not the back side of a Tunisian ID card, or if it is a photocopy (e.g., black and white, grayscale, low contrast, or missing color features), "
    "you must respond with exactly this message and nothing else:\n\n"
    "invalid id card\n\n"
    "- Do not extract or output any information for invalid or photocopied cards.\n"
    "- If the card is valid and in color, extract the following fields:\n"
    "  • motherFullName\n  • job\n  • address\n  • dateOfCreation\n"
    "- The output must be a single valid JSON object with these fields."
)

PROMPT_TUNISIAN_ID_FRONT = (
        "You are an assistant specialized in analyzing images of Tunisian ID cards (front side only).\n"
        "- If the image is not the front side of a Tunisian ID card, or if it is a photocopy (e.g., black and white, grayscale, low contrast, missing color features), "
        "you must respond with exactly this message and nothing else:\n\n"
        "invalid id card\n\n"
        "- Do not extract or output any information for invalid or photocopied cards.\n"
        "- If the card is valid and in color, extract the following fields:\n"
        "  • idNumber\n  • lastName\n  • firstName\n  • fatherFullName\n  • dateOfBirth\n  • placeOfBirth\n"
        "- The output must be a single valid JSON object with these fields."
    )

PROMPT_TRANSCRIPTION = (
    "Vous êtes un assistant spécialisé dans la transcription et la traduction des champs des cartes d'identité tunisiennes à partir de l'arabe.\n"
    "- Transcrivez tous les **noms** et **lieux** en alphabet latin en utilisant les règles officielles de translittération tunisiennes.\n"
    "- Traduisez le champ `job` de l'arabe vers le français (ex : \"تلميذ\" → \"Élève\").\n"
    "- Traduisez le champ `address` de l'arabe vers le français (ex : \"10, نهج 9 أفريل, اريانة\" → \"10, Rue du 9 Avril, Ariana\").\n"
    "- Convertissez `dateOfBirth` au format AAAA/MM/JJ.\n"
    "- Convertissez `dateOfCreation` au format AAAA/MM/JJ.\n"
    "- Ne modifiez pas `idNumber`, il doit rester inchangé.\n"
    "- **La sortie ne doit contenir aucun caractère arabe.** Tous les champs doivent être intégralement translittérés ou traduits en alphabet latin ou en français.\n\n"
    "Retournez une liste JSON comme ceci :\n"
    "```json\n"
    "[\n"
    "  {\n"
    "    \"idNumber\": \"...\",\n"
    "    \"lastName\": \"...\",\n"
    "    \"firstName\": \"...\",\n"
    "    \"fatherFullName\": \"...\",\n"
    "    \"dateOfBirth\": \"...\",\n"
    "    \"placeOfBirth\": \"...\",\n"
    "    \"motherFullName\": \"...\",\n"
    "    \"job\": \"...\",\n"
    "    \"address\": \"...\",\n"
    "    \"dateOfCreation\": \"...\"\n"
    "  }\n"
    "]\n"
    "```\n"
    "\nDonnées d'entrée :\n"
)


#-------------------------------------------------
#---------------Transcription---------------------

MAX_BATCH_SIZE = 20


#-------------------------------------------------
#----------------API-KEYS-MANAGER-----------------

DEFAULT_COOLDOWN = 60
VALIDATION_FAILURE_PENALTY = 10


#--------------------------------------------------
#----------------llm wraper Configs----------------
SYSTEM_MAX_RETRIES = 3
VALIDATION_MAX_RETRIES = 2

#---------------------------------------------------
#---------------Image Target Size-------------------

MAX_WIDTH = 768
MAX_HEIGHT = 512

#---------------------------------------------------
#---------------System conf-------------------------

LOGS_PATH = "logs/service.log"
PV_PATH = "logs/pv"
PORT= 8000
HOST="0.0.0.0"