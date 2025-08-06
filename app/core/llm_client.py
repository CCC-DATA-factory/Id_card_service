from PIL import Image
import asyncio
import google.generativeai as genai
from google.api_core.exceptions import (
    InvalidArgument, PermissionDenied, ResourceExhausted, GoogleAPIError
)
from typing import Dict, Any, List, Union, Type
from pydantic import BaseModel, ValidationError
import json
import time
import logging

from exceptions.llm_exceptions import NoResponseError
from utils.client_utils import calculate_input_tokens, calculate_output_tokens
from utils.prompt_utils import extract_json_from_response

# Mock logger for demonstration purposes
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)




class GeminiClient:
    """
    A synchronous client that uses the actual google.generativeai library.
    
    The API key is configured for the client instance. The `generate` method
    implements robust error handling and metrics tracking.
    """
    def __init__(self, name: str, model: str, api_key: str):
        self.name = name
        self.model = model
        self.api_key = api_key
        # Configure the Gemini API client. This is done once per instance.
        genai.configure(api_key=self.api_key)
        self.max_validation_retries = 2
        self.SYSTEM_MAX_RETRIES = 4

    def generate(self,
             prompt: Union[str, List[Union[str, Image.Image]]],
             output_model: Type[BaseModel]) -> Dict[str, Any]:
        val_attempts = 0
        system_attempts = 0
        
        pv = {
            "total_api_calls": 0,
            "model" : self.model,
            "instance_name" : self.name,
            "attempts": [],
            "total_input_tokens": calculate_input_tokens(prompt),
            "total_output_tokens": 0,
            "keys_used": {self.api_key[6:10]},
            "start_time": time.time(),
        }
        
        model_instance = genai.GenerativeModel(self.model)

        while True:
            attempt = {
                "timestamp": time.time(),
                "key": self.api_key[6:10],
                "status": None,
                "input_tokens": pv["total_input_tokens"],
                "output_tokens": 0,
                "error_type": None,
                "error_msg": None,
                "duration": None,
            }
            try:
                start = time.time()
                response = model_instance.generate_content(prompt)
                duration = time.time() - start

                pv["total_api_calls"] += 1
                attempt["duration"] = duration

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

                attempt["status"] = "success"
                pv["attempts"].append(attempt)

                pv["keys_used"] = list(pv["keys_used"])
                pv["duration_total"] = time.time() - pv["start_time"]

                # Return with action = "success"
                return {"action": "success", "result": {"pv": pv, "result": result}}

            except (json.JSONDecodeError, ValidationError, NoResponseError) as ve:
                val_attempts += 1
                logger.warning(f"[VALIDATION] Attempt {val_attempts} failed: {ve}")
                attempt["status"] = "validation_error"
                attempt["error_type"], attempt["error_msg"] = type(ve).__name__, str(ve)
                pv["attempts"].append(attempt)
                if val_attempts > self.max_validation_retries:
                    # After max retries, do NOT switch pool, just fail this worker -> try next worker
                    return {"action": "fail", "result": None ,"error_msg": str(ve)}
                time.sleep(0.5 * val_attempts)

            except ResourceExhausted as rexc:
                # Quota or rate limit exceeded → switch pool
                return {"action": "next_pool", "result": None, "error_msg": str(rexc)}

            except (InvalidArgument, PermissionDenied) as ie:
                logger.error(f"[FATAL] Configuration error: {ie}")
                # Fatal config error: no retry, no switch, return failure
                return {"action": "fail", "result": None, "error_msg": str(ie)}

            except GoogleAPIError as gae:
                system_attempts += 1
                logger.warning(f"[SYSTEM] API error attempt {system_attempts}: {gae}")
                attempt["status"] = "system_error"
                attempt["error_type"], attempt["error_msg"] = type(gae).__name__, str(gae)
                pv["attempts"].append(attempt)
                if system_attempts >= self.SYSTEM_MAX_RETRIES:
                    # Persistent API error, fail this worker → try next worker
                    return {"action": "next_worker", "result": None, "error_msg": str(gae)}
                time.sleep(min(30, 2 ** system_attempts))

            except Exception as e:
                logger.error(f"[UNEXPECTED] {type(e).__name__}: {e}", exc_info=True)
                # Unknown error, fail this worker → try next worker
                return {"action": "next_worker", "result": None, "error_msg": str(e)}


import asyncio
from typing import List, Dict, Union, Type
from PIL import Image
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

class ThreadManager:
    def __init__(self, model1_configs: List[Dict], model2_configs: List[Dict], max_retries: int = 2):
        self.model1_workers = [GeminiClient(**cfg) for cfg in model1_configs]
        self.model2_workers = [GeminiClient(**cfg) for cfg in model2_configs]

        self.use_model2 = False
        self.lock = asyncio.Lock()
        self.max_retries = max_retries

        # Round-robin indexes
        self.model1_index = 0
        self.model2_index = 0

    async def _reactivate_model1_after_sleep(self, hours=4):
        logger.info(f"[INFO] Sleeping {hours} hours before reactivating model 1 pool.")
        await asyncio.sleep(hours * 3600)
        async with self.lock:
            self.use_model2 = False
            logger.info("[INFO] 4 hours passed, switched back to model 1 workers")

    async def process_task_async(
        self,
        prompt: Union[str, List[Union[str, Image.Image]]],
        output_model: Type[BaseModel],
        retry_depth: int = 0
    ) -> Dict:
        if retry_depth > self.max_retries:
            logger.error("[ERROR] Max retry depth exceeded. Service unavailable.")
            return {
                "status": "error",
                "error_type": "ServiceUnavailable",
                "error_msg": "Service is not available, contact the team or try later."
            }

        async with self.lock:
            use_model2 = self.use_model2
            model1_index = self.model1_index
            model2_index = self.model2_index

        # Select active pool
        pools = (
            [self.model2_workers, self.model1_workers]
            if use_model2 else
            [self.model1_workers, self.model2_workers]
        )

        # Also prepare the indexes for round-robin
        pool_indexes = (
            [model2_index, model1_index]
            if use_model2 else
            [model1_index, model2_index]
        )

        for pool_idx, (workers, start_index) in enumerate(zip(pools, pool_indexes)):
            current_pool_name = 'model 2' if (pool_idx == 0 and use_model2) or (pool_idx == 1 and not use_model2) else 'model 1'
            num_workers = len(workers)
            logger.info(f"[INFO] Using {current_pool_name} workers")

            for i in range(num_workers):
                index = (start_index + i) % num_workers
                instance = workers[index]

                logger.info(f"[INFO] Attempting task with instance '{instance.name}' ({current_pool_name})...")
                response = await asyncio.to_thread(instance.generate, prompt, output_model)

                action = response.get("action")
                error_msg = response.get("error_msg")
                result = response.get("result")

                if action == "success":
                    logger.info(f"[SUCCESS] Worker '{instance.name}' completed task successfully.")

                    # Update the round-robin index
                    async with self.lock:
                        if current_pool_name == "model 1":
                            self.model1_index = (index + 1) % num_workers
                        else:
                            self.model2_index = (index + 1) % num_workers

                    return result

                elif action == "next_worker":
                    logger.warning(f"[WARN] Worker '{instance.name}' failed, trying next in pool. Error: {error_msg}")
                    continue

                elif action == "next_pool":
                    logger.warning(f"[WARN] Quota exhausted for '{instance.name}', switching pool. Error: {error_msg}")
                    async with self.lock:
                        self.use_model2 = not use_model2
                    if self.use_model2:
                        asyncio.create_task(self._reactivate_model1_after_sleep(4))
                    return await self.process_task_async(prompt, output_model, retry_depth + 1)

                elif action == "fail":
                    logger.error(f"[ERROR] Fatal error from '{instance.name}': {error_msg}")
                    return {
                        "status": "error",
                        "error_type": "FatalError",
                        "error_msg": error_msg
                    }

                else:
                    logger.error(f"[ERROR] Unexpected failure from '{instance.name}'")
                    return {
                        "status": "error",
                        "error_type": "UnableToProcess",
                        "error_msg": "Unable to process request, please try again later."
                    }

        logger.error("[ERROR] All workers and pools exhausted.")
        return {
            "status": "error",
            "error_type": "AllPoolsExhausted",
            "error_msg": "All workers and pools exhausted, please try later or contact support."
        }
