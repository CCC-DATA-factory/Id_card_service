import os
import time
import asyncio
import random
from typing import List, Union
from PIL import Image
from dotenv import load_dotenv
import google.generativeai as genai
from google.api_core.exceptions import InvalidArgument, PermissionDenied, ResourceExhausted, GoogleAPIError

import logging
logger = logging.getLogger(__name__)  # use global logging setup from main.py

load_dotenv(dotenv_path="api_keys.env")


class APIKeyManager:
    """
    Manages multiple API keys, rotation, and cooldowns for keys that recently failed.
    """
    COOLDOWN_SECONDS = 60

    def __init__(self):
        self.api_keys = self._load_keys_from_env()
        if not self.api_keys:
            raise RuntimeError("No API keys found in .env file.")
        self.key_index = 0
        self.key_fail_times = {}

    def _load_keys_from_env(self) -> List[str]:
        keys = []
        i = 1
        while True:
            key = os.getenv(f"GOOGLE_API_KEY_{i}")
            if not key:
                break
            keys.append(key)
            logger.info(f"[ENV] Loaded GOOGLE_API_KEY_{i}")
            i += 1
        logger.info(f"[ENV] Total API keys loaded: {len(keys)}")
        return keys

    def get_active_key(self) -> str:
        return self.api_keys[self.key_index]

    def rotate_key(self):
        num_keys = len(self.api_keys)
        for _ in range(num_keys):
            self.key_index = (self.key_index + 1) % num_keys
            cooldown_until = self.key_fail_times.get(self.key_index, 0)
            if time.time() >= cooldown_until:
                logger.info(f"[ROTATE] Using new key index: {self.key_index}")
                return
        self.key_index = (self.key_index + 1) % num_keys
        logger.warning(f"[ROTATE] All keys might be on cooldown. Forced rotate to index: {self.key_index}")

    def mark_key_failure(self):
        cooldown_until = time.time() + self.COOLDOWN_SECONDS
        self.key_fail_times[self.key_index] = cooldown_until
        logger.warning(f"[KEY-FAIL] Key index {self.key_index} marked failed until {cooldown_until:.0f}")

    def add_api_key(self, key: str):
        if key not in self.api_keys:
            self.api_keys.append(key)
            logger.info(f"[ADD] New API key added. Total keys: {len(self.api_keys)}")
        else:
            logger.info(f"[ADD] API key already exists. Skipping.")


class LLM:
    """
    Async-safe LLM wrapper with retries, exponential backoff, and secure key rotation.
    """
    def __init__(self, model_name: str = "gemini-2.0-flash", max_retries: int = 3):
        logger.info(f"[LLM INIT] Initializing model: {model_name}")
        self.api_key_manager = APIKeyManager()
        self.max_retries = max_retries
        self.model_name = model_name
        self._configure_api()
        self.model = genai.GenerativeModel(model_name)
        logger.info(f"[LLM INIT] Ready with key index: {self.api_key_manager.key_index}")

    def _configure_api(self):
        active_key = self.api_key_manager.get_active_key()
        genai.configure(api_key=active_key)
        self.model = genai.GenerativeModel(self.model_name)  
        logger.info(f"[CONFIG] Configured with key index: {self.api_key_manager.key_index}")


    def rotate_key(self):
        self.api_key_manager.rotate_key()


        
    async def generate(self, prompt: Union[str, List[Union[str, Image.Image]]]):
        attempts = 0
        while attempts < self.max_retries:
            try:
                loop = asyncio.get_running_loop()
                logger.info(f"[GENERATE] Attempt {attempts+1} using key index {self.api_key_manager.key_index}")
                response = await loop.run_in_executor(None, lambda: self.model.generate_content(prompt))
                logger.info("[GENERATE] Success")
                return response

            except ResourceExhausted as e:
                logger.warning(f"[RETRY ERROR] Resource exhausted with key index {self.api_key_manager.key_index}: {e}")
                self.api_key_manager.mark_key_failure()
                attempts += 1
                if attempts >= self.max_retries:
                    logger.error("[FAILED] Max retries reached. Aborting.")
                    raise RuntimeError("All API keys failed due to resource exhaustion. Generation aborted.")
                self.api_key_manager.rotate_key()
                self._configure_api()
                delay = (2 ** attempts) + random.uniform(0, 1)
                logger.info(f"[RETRY] Waiting {delay:.2f}s before retry...")
                await asyncio.sleep(delay)

            except (InvalidArgument, PermissionDenied) as e:
                logger.error(f"[FATAL] API error (no retry): {e}")
                raise RuntimeError(f"API error: {e}")

            except GoogleAPIError as e:
                logger.error(f"[FATAL] Google API error: {e}")
                raise RuntimeError(f"Google API failure: {e}")

            except Exception as e:
                logger.error(f"[FATAL] Unexpected error: {e}")
                raise RuntimeError(f"Unexpected LLM failure: {e}")
