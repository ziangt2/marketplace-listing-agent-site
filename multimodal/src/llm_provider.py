"""Small hosted provider boundary; exact-request cache and no secret serialization."""
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

from .config import ROOT
from .io_utils import digest, write_json

DEFAULT_MODEL = "gpt-4.1-mini-2025-04-14"


def load_local_env(path=ROOT.parent / ".env.local"):
    if not Path(path).is_file():
        return
    for line in Path(path).read_text().splitlines():
        if "=" not in line or line.lstrip().startswith("#"):
            continue
        key, value = line.split("=", 1)
        if key.strip() in {"OPENAI_API_KEY", "AGENT_LLM_MODEL", "AGENT_LLM_PROVIDER"}:
            os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


class ProviderError(RuntimeError):
    pass


class LLMProvider:
    def generate_structured(self, *, system, payload, schema, prompt_version):
        raise NotImplementedError


class OpenAIProvider(LLMProvider):
    def __init__(self, model=None, cache_root=ROOT / "data/cache/agent_llm", cache_only=False):
        load_local_env()
        if os.environ.get("AGENT_LLM_PROVIDER", "openai") != "openai":
            raise ProviderError("This iteration implements the openai provider only")
        self.model = model or os.environ.get("AGENT_LLM_MODEL", DEFAULT_MODEL)
        self.cache_root, self.cache_only = Path(cache_root), cache_only
        self.calls = []

    def generate_structured(self, *, system, payload, schema, prompt_version):
        started = time.perf_counter()
        request = {"model": self.model, "temperature": 0, "store": False,
                   "input": [{"role": "system", "content": system},
                             {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
                   "text": {"format": {"type": "json_schema", "name": prompt_version.replace("-", "_"),
                                       "strict": True, "schema": schema}}, "max_output_tokens": 2200}
        key = digest({"provider": "openai", "prompt_version": prompt_version, "request": request})
        path = self.cache_root / (key + ".json")
        cached = path.is_file()
        if cached:
            record = json.loads(path.read_text())
            if record.get("cache_key") != key or record.get("request") != request:
                raise ProviderError("Cache request identity mismatch")
        else:
            if self.cache_only:
                raise ProviderError("No cached response for this exact request")
            key_value = os.environ.get("OPENAI_API_KEY")
            if not key_value:
                raise ProviderError("OPENAI_API_KEY is required in environment or ignored .env.local")
            response = None
            network_started = time.perf_counter()
            for attempt in range(2):
                try:
                    response = requests.post("https://api.openai.com/v1/responses", timeout=(10, 50),
                        headers={"Authorization": "Bearer " + key_value, "Content-Type": "application/json"}, json=request)
                except requests.RequestException:
                    raise ProviderError("OpenAI transport failed (details omitted to protect credentials)") from None
                if response.status_code == 429 or response.status_code >= 500:
                    if attempt == 0:
                        time.sleep(1)
                        continue
                break
            if response.status_code != 200:
                raise ProviderError(f"OpenAI returned HTTP {response.status_code}")
            body = response.json()
            if body.get("status") != "completed":
                raise ProviderError("OpenAI response did not complete")
            texts = [part["text"] for output in body.get("output", []) for part in output.get("content", [])
                     if part.get("type") == "output_text"]
            try:
                parsed = json.loads("".join(texts))
            except (ValueError, TypeError):
                raise ProviderError("OpenAI returned no valid structured output") from None
            record = {"cache_key": key, "provider": "openai", "model_requested": self.model,
                      "model_returned": body.get("model"), "temperature": 0, "prompt_version": prompt_version,
                      "timestamp": datetime.now(timezone.utc).isoformat(), "request": request,
                      "response": body, "parsed": parsed, "api_ms": (time.perf_counter() - network_started) * 1000,
                      "attempts": attempt + 1}
            write_json(path, record)
        elapsed = (time.perf_counter() - started) * 1000
        self.calls.append({k: record[k] for k in ("cache_key", "provider", "model_requested", "model_returned",
                                                "temperature", "prompt_version", "timestamp", "attempts")} | {
            "cache_hit": cached, "wall_ms": elapsed, "api_ms": 0 if cached else record["api_ms"],
            "original_api_ms": record["api_ms"], "response_id": record["response"].get("id"),
            "usage": record["response"].get("usage")})
        return record["parsed"]
