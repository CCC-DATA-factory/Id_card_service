import os
import random
import time
import heapq
import threading
import logging
from typing import List, Dict

from dotenv import load_dotenv

from config import DEFAULT_COOLDOWN, VALIDATION_FAILURE_PENALTY
load_dotenv(dotenv_path="./api_keys.env")

logger = logging.getLogger(__name__)

class APIKeyManager:
    """Efficient API key manager with cooldown and failure tracking."""


    def __init__(self):
        self.api_keys: List[str] = []
        self.key_metadata: Dict[str, dict] = {}
        self.available_keys: List[tuple[float, str]] = []  # Heap of (cooldown_until, key)
        self.lock = threading.RLock()
        self._initialize_keys()

    def _initialize_keys(self):
        with self.lock:
            i = 1
            while (key := os.getenv(f"GOOGLE_API_KEY_{i}")):
                if key not in self.key_metadata:
                    self.api_keys.append(key)
                    self.key_metadata[key] = {
                        'success_count': 0,
                        'failure_count': 0,
                        'cooldown_until': 0.0
                    }
                    heapq.heappush(self.available_keys, (0.0, key))
                    logger.info(f"[ENV] Loaded GOOGLE_API_KEY_{i}")
                else:
                    logger.debug(f"[ENV] Duplicate key GOOGLE_API_KEY_{i} skipped")
                i += 1

            if not self.api_keys:
                raise RuntimeError("No API keys found in .env file.")
            logger.info(f"[ENV] Total API keys loaded: {len(self.api_keys)}")

    def get_best_key(self) -> str:
        with self.lock:
            now = time.time()
            logger.debug("Entering get_best_key()")
            # Drain heap once
            ready_keys = []
            temp = []
            while self.available_keys:
                cd, k = heapq.heappop(self.available_keys)
                md = self.key_metadata[k]
                if md['cooldown_until'] <= now:
                    ready_keys.append(k)
                else:
                    temp.append((md['cooldown_until'], k))

            # Restore cooling keys
            for entry in temp:
                heapq.heappush(self.available_keys, entry)

            # If any ready, pick the one with lowest failure_count (randomize ties)
            if ready_keys:
                # gather min failure_count
                min_fail = min(self.key_metadata[k]['failure_count'] for k in ready_keys)
                candidates = [k for k in ready_keys if self.key_metadata[k]['failure_count'] == min_fail]
                chosen = random.choice(candidates) if len(candidates) > 1 else candidates[0]
                logger.debug(f"Selected ready key {chosen[:6]} with failure_count={min_fail}")
                # Refresh its heap entry
                self._refresh_key_in_heap(chosen)
                return chosen

            # Otherwise fallback to the soonest cooling key
            soonest = min(self.key_metadata, key=lambda k: self.key_metadata[k]['cooldown_until'])
            logger.warning(f"All keys cooling; using soonest: {soonest[:6]}")
            return soonest

    def mark_key_success(self, key: str):
        with self.lock:
            if key not in self.key_metadata:
                logger.warning(f"mark_key_success: unknown key {key[:6]}")
                return
            md = self.key_metadata[key]
            md['success_count'] += 1
            md['failure_count'] = 0
            md['cooldown_until'] = 0.0
            self._refresh_key_in_heap(key)
            logger.info(f"[KEY-SUCCESS] {key[:6]} success_count={md['success_count']} cooldown reset")

    def mark_key_failure(self, key: str, cooldown_seconds: float = None):
        with self.lock:
            if key not in self.key_metadata:
                logger.warning(f"mark_key_failure: unknown key {key[:6]}")
                return
            md = self.key_metadata[key]
            md['failure_count'] += 1
            base = cooldown_seconds or DEFAULT_COOLDOWN
            cd = base * (1.5 ** min(md['failure_count'], 4))
            md['cooldown_until'] = time.time() + cd
            self._refresh_key_in_heap(key)
            logger.warning(f"[KEY-FAIL] {key[:6]} failure_count={md['failure_count']} cooldown={cd:.1f}s")

    def mark_validation_failure(self, key: str):
        self.mark_key_failure(key, VALIDATION_FAILURE_PENALTY)

    def add_api_key(self, key: str):
        with self.lock:
            if key in self.key_metadata:
                logger.info(f"[ADD] Key {key[:6]} already present")
                return
            self.api_keys.append(key)
            self.key_metadata[key] = {
                'success_count': 0,
                'failure_count': 0,
                'cooldown_until': 0.0
            }
            heapq.heappush(self.available_keys, (0.0, key))
            logger.info(f"[ADD] New key {key[:6]} added")

    def _refresh_key_in_heap(self, key: str):
        # Remove stale entries and reinsert with updated cooldown
        cd = self.key_metadata[key]['cooldown_until']
        self.available_keys = [(c, k) for (c, k) in self.available_keys if k != key]
        heapq.heappush(self.available_keys, (cd, key))
        heapq.heapify(self.available_keys)
