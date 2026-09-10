"""
Shared Anthropic client wrapper.

Replaces the two previously-duplicated raw urllib.request call sites
(engines/ads_analyzer.py and app.py's approve_recommendation). Uses the official
SDK so retries/error types are handled for us, and caches the system-prompt block
by default — the ads_skills package fires ~9 calls per analysis run sharing a large,
mostly-static business-rules block, so caching keeps that from being re-billed
in full on every call.
"""

import json
import logging

import anthropic

import config

logger = logging.getLogger(__name__)

MODEL = "claude-sonnet-4-6"

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    return _client


def call(system_prompt, user_prompt, max_tokens=4096, cache_system=True):
    """Call Claude with a system + user prompt, return the text response."""
    if not config.ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY not configured")

    client = _get_client()
    system = system_prompt
    if cache_system and len(system_prompt) > 512:
        system = [{"type": "text", "text": system_prompt, "cache_control": {"type": "ephemeral"}}]

    resp = client.messages.create(
        model=MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user_prompt}],
    )
    return resp.content[0].text.strip()


def call_json(system_prompt, user_prompt, max_tokens=4096, cache_system=True):
    """Call Claude and parse the response as JSON, stripping markdown fences if present."""
    text = call(system_prompt, user_prompt, max_tokens=max_tokens, cache_system=cache_system)
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
        text = text.rsplit("```", 1)[0].strip()
    return json.loads(text)
