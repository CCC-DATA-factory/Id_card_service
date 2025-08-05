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
        self.max_validation_retries = 3
        self.SYSTEM_MAX_RETRIES = 5

    def generate(self,
                 prompt: Union[str, List[Union[str, Image.Image]]],
                 output_model: Type[BaseModel]) -> Dict[str, Any]:
        """
        Calls the real Gemini API to generate content with retries and error handling.
        This is a synchronous, blocking function designed to be run in a thread.
        
        Returns:
            A dictionary with either a success result or an error status.
        """
        val_attempts = 0
        system_attempts = 0
        
        pv = {
            "total_api_calls": 0,
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
                
                return {"pv": pv, "result": result}

            except (json.JSONDecodeError, ValidationError, NoResponseError) as ve:
                val_attempts += 1
                logger.warning(f"[VALIDATION] Attempt {val_attempts} failed: {ve}")
                attempt["status"] = "validation_error"
                attempt["error_type"], attempt["error_msg"] = type(ve).__name__, str(ve)
                pv["attempts"].append(attempt)
                if val_attempts > self.max_validation_retries:
                    # Exceeded retries, return an error status
                    return {"status": "error", "error_type": "ValidationRetryError", "error_msg": str(ve)}
                time.sleep(0.5 * val_attempts)

            except ResourceExhausted as rexc:
                # Return a specific status to signal a retry for the ThreadManager
                return {"status": "retry", "error_type": "ResourceExhaustedError", "error_msg": str(rexc)}

            except (InvalidArgument, PermissionDenied) as ie:
                logger.error(f"[FATAL] Configuration error: {ie}")
                return {"status": "error", "error_type": "FatalConfigError", "error_msg": str(ie)}

            except GoogleAPIError as gae:
                system_attempts += 1
                logger.warning(f"[SYSTEM] API error attempt {system_attempts}: {gae}")
                attempt["status"] = "system_error"
                attempt["error_type"], attempt["error_msg"] = type(gae).__name__, str(gae)
                pv["attempts"].append(attempt)
                if system_attempts >= self.SYSTEM_MAX_RETRIES:
                    # Exceeded retries, return an error status
                    return {"status": "error", "error_type": "PersistentApiError", "error_msg": str(gae)}
                time.sleep(min(30, 2 ** system_attempts))

            except Exception as e:
                logger.error(f"[UNEXPECTED] {type(e).__name__}: {e}", exc_info=True)
                return {"status": "error", "error_type": "UnexpectedError", "error_msg": str(e)}


class ThreadManager:
    
    """
    Manages the worker instances for asynchronous, round-robin task processing.
    """
    def __init__(self, configs: List[Dict]):
        self.instances = [GeminiClient(cfg['name'], cfg['model'], cfg['api_key']) for cfg in configs]
        self.instance_count = len(self.instances)
        
        self.task_counter = 0
        self.counter_lock = asyncio.Lock()

    async def process_task_async(self, prompt: Union[str, List[Union[str, Image.Image]]], output_model: Type[BaseModel]) -> Dict[str, Any]:
        """
        Processes a single task asynchronously using a round-robin worker.
        It will reassign the task to the next worker if a 'retry' status is returned.
        """
        max_retries = self.instance_count
        for _ in range(max_retries):
            async with self.counter_lock:
                instance_index = self.task_counter % self.instance_count
                self.task_counter += 1
                
            instance = self.instances[instance_index]
            
            print(f"Attempting task with instance '{instance.name}'...")
            
            response = await asyncio.to_thread(instance.generate, prompt, output_model)
            
            if response.get("status") == "retry":
                print(f"Worker '{instance.name}' is exhausted. Reassigning task...")
                # Continue the loop to try the next worker
                continue
            else:
                # If the status is not 'retry', return the response immediately
                return response
        
        # If the loop finishes, it means all workers have failed
        return {"status": "error", "error_type": "AllWorkersExhausted", "error_msg": "Failed to process task after multiple retries."}
