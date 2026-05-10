from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, Optional

import httpx


class LLMClient:
    """OpenAI, Anthropic, or Google Gemini (Generative Language API) with JSON-first helpers."""

    def __init__(
        self,
        *,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        timeout_s: float = 120.0,
    ) -> None:
        self.provider = (provider or os.getenv("IIE_LLM_PROVIDER") or "gemini").lower()
        self.openai_key = os.getenv("OPENAI_API_KEY")
        self.anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        self.gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        self.model = model or os.getenv("IIE_LLM_MODEL") or self._default_model()
        self.timeout_s = timeout_s

    def _default_model(self) -> str:
        if self.provider == "anthropic":
            return "claude-3-5-sonnet-20241022"
        if self.provider == "gemini":
            return "gemini-2.5-flash-lite"
        return "gpt-4o-mini"

    def complete_text(self, system: str, user: str) -> str:
        raw = self._complete_raw(system, user, force_json=False)
        return raw.strip()

    def complete_json(self, system: str, user: str) -> Dict[str, Any]:
        raw = self._complete_raw(system, user, force_json=True)
        parsed = self._parse_json_loose(raw)
        if parsed is not None:
            return parsed
        fix_system = (
            system
            + "\n\nYour previous reply was invalid JSON. Reply again with ONLY valid JSON, "
            "same schema, no markdown fences, no commentary."
        )
        raw2 = self._complete_raw(fix_system, user, force_json=True)
        parsed2 = self._parse_json_loose(raw2)
        if parsed2 is not None:
            return parsed2
        raise ValueError("LLM returned non-JSON twice")

    def _complete_raw(self, system: str, user: str, *, force_json: bool) -> str:
        if self.provider == "anthropic":
            return self._anthropic(system, user)
        if self.provider == "gemini":
            return self._gemini(system, user, force_json=force_json)
        return self._openai(system, user, force_json=force_json)

    def _openai(self, system: str, user: str, *, force_json: bool) -> str:
        if not self.openai_key:
            raise RuntimeError("OPENAI_API_KEY not set for OpenAI provider")
        url = "https://api.openai.com/v1/chat/completions"
        body: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.2,
        }
        if force_json:
            body["response_format"] = {"type": "json_object"}
        headers = {"Authorization": f"Bearer {self.openai_key}", "Content-Type": "application/json"}
        with httpx.Client(timeout=self.timeout_s) as client:
            r = client.post(url, json=body, headers=headers)
            r.raise_for_status()
            data = r.json()
        return data["choices"][0]["message"]["content"]

    def _anthropic(self, system: str, user: str) -> str:
        if not self.anthropic_key:
            raise RuntimeError("ANTHROPIC_API_KEY not set for Anthropic provider")
        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": self.anthropic_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        body = {
            "model": self.model,
            "max_tokens": 4096,
            "system": system,
            "messages": [{"role": "user", "content": user}],
            "temperature": 0.2,
        }
        with httpx.Client(timeout=self.timeout_s) as client:
            r = client.post(url, json=body, headers=headers)
            r.raise_for_status()
            data = r.json()
        parts = data.get("content") or []
        texts = [p.get("text", "") for p in parts if p.get("type") == "text"]
        return "".join(texts)

    def _gemini(self, system: str, user: str, *, force_json: bool) -> str:
        if not self.gemini_key:
            raise RuntimeError("GEMINI_API_KEY or GOOGLE_API_KEY not set for Gemini provider")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        gen_cfg: Dict[str, Any] = {"temperature": 0.2}
        if force_json:
            gen_cfg["responseMimeType"] = "application/json"
        body: Dict[str, Any] = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"parts": [{"text": user}]}],
            "generationConfig": gen_cfg,
        }
        with httpx.Client(timeout=self.timeout_s) as client:
            r = client.post(url, params={"key": self.gemini_key}, json=body)
            r.raise_for_status()
            data = r.json()
        cands = data.get("candidates") or []
        if not cands:
            err = data.get("error", {}).get("message") if isinstance(data.get("error"), dict) else None
            raise RuntimeError(err or "Gemini returned no candidates (blocked or empty response)")
        parts = (cands[0].get("content") or {}).get("parts") or []
        texts = [p.get("text", "") for p in parts if isinstance(p, dict)]
        return "".join(texts)

    @staticmethod
    def _parse_json_loose(raw: str) -> Optional[Dict[str, Any]]:
        raw = raw.strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)
        try:
            val = json.loads(raw)
            return val if isinstance(val, dict) else None
        except json.JSONDecodeError:
            return None
