from config import CONFIDANCE_THRESHOLD
from core.llm_client import ThreadManager
from core.id_card_validator import IdCardValidator
#from core.easy_ocr import EasyOCR
from dotenv import load_dotenv
import os
from pathlib import Path
import onnxruntime as ort

parent_dir = Path(__file__).resolve().parent.parent  

env_path = parent_dir / "api_keys.env"
MODEL_PATH = parent_dir / "assets" / "best.onnx"
load_dotenv(dotenv_path=env_path)
#gemini-2.5-flash-lite
CONFIGS_MAIN = [
    {"name": f"gemini-worker-{i}", "model": "gemini-2.5-flash", "api_key": os.getenv(f"GOOGLE_API_KEY_{i}")}
    for i in range(1, 5)
]

CONFIGS_LIGHT = [
    {"name": f"gemini-worker-{i}", "model": "gemini-2.5-flash-lite", "api_key": os.getenv(f"GOOGLE_API_KEY_{i}")}
    for i in range(1, 5)
]

llm = ThreadManager(model1_configs=CONFIGS_MAIN , model2_configs =CONFIGS_LIGHT )
validator = IdCardValidator(model_path=MODEL_PATH,confidence_threshold=CONFIDANCE_THRESHOLD)
#ocr = EasyOCR(languages=['en'], gpu=False)
