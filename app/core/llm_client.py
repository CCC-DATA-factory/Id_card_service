import json
import os
import asyncio
import random
import threading
import time
from typing import List, Type, Union
from PIL import Image
from dotenv import load_dotenv
import google.generativeai as genai
from google.api_core.exceptions import (
    InvalidArgument, PermissionDenied, ResourceExhausted, GoogleAPIError
)

import logging
from pydantic import BaseModel, ValidationError

from config import SYSTEM_MAX_RETRIES, VALIDATION_MAX_RETRIES
from core.api_key_manager import APIKeyManager
from exceptions.llm_exceptions import NoResponseError, ValidationRetryError
from utils.client_utils import calculate_input_tokens, calculate_output_tokens
from utils.prompt_utils import extract_json_from_response

load_dotenv(dotenv_path="./api_keys.env")
logger = logging.getLogger(__name__)


class LLM:
    """Robust LLM client with proper key rotation and session isolation"""

    
    _global_lock = threading.Lock()  # Protects global genai.configure

    def __init__(self, model_name: str = "gemini-2.0-flash", max_validation_retries: int = VALIDATION_MAX_RETRIES):
        self.model_name = model_name
        self.max_validation_retries = max_validation_retries
        self.api_key_manager = APIKeyManager()
        self.MAX_QUOTA_RETRIES = max(5, self._count_api_keys() * 2)
        self.client_id = f"cli-{time.time_ns()}-{random.randint(10000,99999)}"

    def _count_api_keys(self) -> int:
        i, count = 1, 0
        while os.getenv(f"GOOGLE_API_KEY_{i}"):
            count += 1
            i += 1
        return count

    def _create_fresh_session(self, key: str):
        client_config = genai.types.GenerationConfig(
            candidate_count=1,
            max_output_tokens=2048,
        )
        with LLM._global_lock:
            genai.configure(api_key=key)
        return genai.GenerativeModel(
            model_name=self.model_name,
            generation_config=client_config
        )

    async def _call_api(self, prompt: Union[str, List[Union[str, Image.Image]]]):
        key = self.api_key_manager.get_best_key()
        client = await asyncio.to_thread(self._create_fresh_session, key)
        logger.info(f"[CALL] Using key {key[:9]} for this request")
        response = await asyncio.to_thread(client.generate_content, prompt)
        if response is None or not hasattr(response, 'text'):
            # Mark as failure and raise clear error
            self.api_key_manager.mark_key_failure(key)
            raise RuntimeError("No valid response from LLM")
        return response, key

    async def generate(self,
                       prompt: Union[str, List[Union[str, Image.Image]]],
                       output_model: Type[BaseModel]) -> Union[dict, BaseModel, List[BaseModel]]:
        val_attempts = 0
        quota_attempts = 0
        system_attempts = 0
        current_key = None

        pv = {
            "total_api_calls": 0,
            "attempts": [],
            "total_input_tokens": calculate_input_tokens(prompt),
            "total_output_tokens": 0,
            "keys_used": set(),
            "start_time": time.time(),
        }

        while True:
            attempt = {
                "timestamp": time.time(),
                "key": None,
                "status": None,
                "input_tokens": pv["total_input_tokens"],
                "output_tokens": 0,
                "error_type": None,
                "error_msg": None,
                "duration": None,
            }
            try:
                start = time.time()
                response, current_key = await self._call_api(prompt)
                duration = time.time() - start

                pv["total_api_calls"] += 1
                attempt["key"] = current_key[:6]
                attempt["duration"] = duration
                pv["keys_used"].add(current_key[:6])

                text = response.text.strip()
                out_tokens = calculate_output_tokens(text)
                attempt["output_tokens"] = out_tokens
                pv["total_output_tokens"] += out_tokens
                parsed = extract_json_from_response(text)
                if not parsed:
                    raise NoResponseError("No parsable content")

                if isinstance(parsed, list):
                    result = [output_model(**item) for item in parsed]
                else:
                    result = output_model(**parsed)

                # Success: mark key
                logger.info(f"[KEY-SUCCESS] Key {current_key[:6]} reset on success")
                self.api_key_manager.mark_key_success(current_key)
                attempt["status"] = "success"
                pv["attempts"].append(attempt)

                pv["keys_used"] = list(pv["keys_used"])
                pv["duration_total"] = time.time() - pv["start_time"]
                return {"pv": pv, "result": result}

            except (json.JSONDecodeError, ValidationError, NoResponseError) as ve:
                # Validation errors: do not rotate key
                val_attempts += 1
                logger.warning(f"[VALIDATION] Attempt {val_attempts} failed: {ve}")
                attempt["status"] = "validation_error"
                attempt["error_type"], attempt["error_msg"] = type(ve).__name__, str(ve)
                pv["attempts"].append(attempt)
                if val_attempts > self.max_validation_retries:
                    raise ValidationRetryError("Exceeded validation retries")
                await asyncio.sleep(0.5 * val_attempts)

            except ResourceExhausted as rexc:
                # Quota errors: rotate key
                quota_attempts += 1
                logger.warning(f"[QUOTA] Attempt {quota_attempts} resource exhausted: {rexc}")
                self.api_key_manager.mark_key_failure(current_key)
                attempt["status"] = "resource_exhausted"
                attempt["error_type"], attempt["error_msg"] = type(rexc).__name__, str(rexc)
                pv["attempts"].append(attempt)
                if quota_attempts > self.MAX_QUOTA_RETRIES:
                    raise RuntimeError("System quota exhausted")
                await asyncio.sleep(min(60, 2 ** quota_attempts))

            except (InvalidArgument, PermissionDenied) as ie:
                logger.error(f"[FATAL] Configuration error: {ie}")
                raise RuntimeError("Configuration error")

            except GoogleAPIError as gae:
                system_attempts += 1
                logger.warning(f"[SYSTEM] API error attempt {system_attempts}: {gae}")
                self.api_key_manager.mark_key_failure(current_key)
                attempt["status"] = "system_error"
                attempt["error_type"], attempt["error_msg"] = type(gae).__name__, str(gae)
                pv["attempts"].append(attempt)
                if system_attempts >= SYSTEM_MAX_RETRIES:
                    raise RuntimeError("Persistent API errors")
                await asyncio.sleep(min(30, 2 ** system_attempts))

            except Exception as e:
                logger.error(f"[UNEXPECTED] {type(e).__name__}: {e}", exc_info=True)
                raise
