"""LLM summarisation via any OpenAI-compatible Chat Completions endpoint
(Groq, OpenAI, Azure OpenAI, vLLM, Ollama...). Optional: without a key the copilot
falls back to a deterministic template, so it degrades instead of failing."""

from __future__ import annotations

import logging
import time

import httpx

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an SRE incident copilot. You write a short, factual first-responder brief.
Rules:
- Use ONLY the evidence provided. Never invent metrics, versions, commits or timestamps.
- If the evidence is insufficient, say what is missing.
- You RECOMMEND actions; you never claim to have taken any.
- Cite runbook sections by their heading in square brackets.
Format (Markdown, max ~180 words):
**Impact** one sentence. **Likely cause** one or two sentences with the numbers.
**Recommended next steps** 2-4 bullets. **Confidence** low/medium/high with one reason."""


class LLMClient:
    def __init__(
        self, base_url: str, api_key: str | None, model: str, timeout: float = 20.0, transport: httpx.BaseTransport | None = None
    ):
        self.enabled = bool(api_key)
        self.model = model
        self._client = httpx.Client(
            base_url=base_url.rstrip("/"),
            timeout=timeout,
            headers={"Authorization": f"Bearer {api_key}"} if api_key else {},
            transport=transport,
        )

    def summarise(self, evidence_markdown: str) -> tuple[str | None, float]:
        if not self.enabled:
            return None, 0.0
        start = time.perf_counter()
        try:
            resp = self._client.post(
                "/chat/completions",
                json={
                    "model": self.model,
                    "temperature": 0.1,
                    "max_tokens": 400,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": evidence_markdown},
                    ],
                },
            )
            resp.raise_for_status()
            text = resp.json()["choices"][0]["message"]["content"].strip()
            return text, time.perf_counter() - start
        except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
            log.warning("LLM call failed, using deterministic brief: %s", exc)
            return None, time.perf_counter() - start
