import os
import time
from typing import List, Union
from PIL import Image
from dotenv import load_dotenv
import google.generativeai as genai
from google.api_core.exceptions import InvalidArgument, PermissionDenied, ResourceExhausted

load_dotenv(dotenv_path="api_keys.env")

class LLM:
    def __init__(self, model_name: str = "gemini-2.0-flash", max_retries: int = 3):
        print("[INIT] Loading API keys from api_keys.env...")
        self.api_keys = self._load_keys_from_env()
        if not self.api_keys:
            raise RuntimeError("No API keys found in .env file.")

        self.env_path = "api_keys.env"
        self.key_index = 0
        self.max_retries = max_retries
        self.model_name = model_name

        print(f"[INIT] Using model: {model_name}")
        self._configure_api()
        self.model = genai.GenerativeModel(model_name)
        print(f"[INIT] Ready with API key index {self.key_index}")

    def _load_keys_from_env(self) -> List[str]:
        keys = []
        i = 1
        while True:
            key = os.getenv(f"GOOGLE_API_KEY_{i}")
            if not key:
                break
            keys.append(key)
            print(f"[ENV] Found GOOGLE_API_KEY_{i}")
            i += 1
        print(f"[ENV] Loaded {len(keys)} API keys.")
        return keys

    def _configure_api(self):
        active_key = self.api_keys[self.key_index]
        genai.configure(api_key=active_key)
        print(f"[CONFIG] Configured with API key index {self.key_index}")

    def rotate_key(self):
        old_index = self.key_index
        self.key_index = (self.key_index + 1) % len(self.api_keys)
        self._configure_api()
        print(f"[ROTATE] Switched from key index {old_index} to {self.key_index}")

    def get_active_key(self) -> str:
        return self.api_keys[self.key_index]

    def add_api_key(self, key: str):
        if key not in self.api_keys:
            self.api_keys.append(key)
            print(f"[ADD] Added new API key. Total: {len(self.api_keys)}")
            self._save_api_keys_to_env()
        else:
            print("[ADD] API key already exists.")

    def _save_api_keys_to_env(self):
        print("[SAVE] Persisting API keys to .env file...")
        with open(self.env_path, "r") as f:
            lines = f.readlines()

        existing_keys = {}
        for i, line in enumerate(lines):
            if line.startswith("GOOGLE_API_KEY_"):
                key_num = int(line.split("=")[0].split("_")[-1])
                existing_keys[key_num] = i

        for index, key in enumerate(self.api_keys, start=1):
            line_content = f"GOOGLE_API_KEY_{index}={key}\n"
            if index in existing_keys:
                lines[existing_keys[index]] = line_content
            else:
                lines.append(line_content)

        with open(self.env_path, "w") as f:
            f.writelines(lines)

        print(f"[SAVE] Saved {len(self.api_keys)} API key(s) to .env.")


    def generate(self, prompt: Union[str, List[Union[str, Image.Image]]]):
        attempts = 0
        while attempts < self.max_retries:
            print(f"[GENERATE] Attempt {attempts + 1} using key index {self.key_index}")
            try:
                response = self.model.generate_content(prompt)
                print("[GENERATE] Success")
                return response
            except (InvalidArgument, PermissionDenied, ResourceExhausted) as e:
                print(f"[ERROR] LLM Error with key {self.get_active_key()}: {e}")
                attempts += 1
                if attempts >= self.max_retries:
                    print("[ERROR] All retries exhausted. Aborting.")
                    raise RuntimeError("All API keys failed. Generation aborted.")
                self.rotate_key()
                time.sleep(1)
            except Exception as e:
                print(f"[ERROR] Unexpected failure: {e}")
                raise RuntimeError(f"[ERROR] Unexpected LLM failure: {e}")
