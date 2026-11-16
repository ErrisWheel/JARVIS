"""Persistent, explicit operator preferences. Only direct low-risk instructions are captured."""
from __future__ import annotations

import re
from typing import Any
from .database import get_operator_instructions, set_operator_instruction

RULES: tuple[tuple[str, re.Pattern[str], str], ...] = (
    ("emoji", re.compile(r"\b(?:never|don't|do not|stop)\s+(?:ever\s+)?(?:use|include|send|add)\s+emojis?\b|\bno\s+emojis?\b", re.I),
     "Never use emojis in replies."),
    ("humor", re.compile(r"\b(?:not funny|no jokes?|stop joking|don't joke|do not joke|no humor|less humor)\b", re.I),
     "Do not make jokes or use playful banter unless the operator explicitly invites it."),
    ("brevity", re.compile(r"\b(?:keep it|make it|be)\s+(?:short|brief|concise)\b|\bno long explanations\b", re.I),
     "Prefer concise, direct answers unless the operator asks for detail."),
    ("format", re.compile(r"\b(?:always|please)\s+(?:give|send|return|provide)\s+(?:me\s+)?(?:the\s+)?(?:whole|full|complete)\s+(?:file|code|script)\b", re.I),
     "When asked for a complete file, return the full file rather than a fragment."),
)


def capture_explicit_instruction(message: str) -> dict[str, Any] | None:
    text = (message or "").strip()
    if not text or len(text) > 2000:
        return None
    for category, pattern, instruction in RULES:
        if pattern.search(text):
            set_operator_instruction(category, instruction, source="explicit-operator-correction")
            return {"category": category, "instruction": instruction, "updated": True}
    return None


def instruction_prompt() -> str:
    items = get_operator_instructions()
    if not items:
        return ""
    rows = "\n".join(f"- {item['instruction']}" for item in items)
    return (
        "\n\nPERSISTENT OPERATOR INSTRUCTIONS (higher priority than persona/style preferences):\n"
        f"{rows}\n"
        "Follow these directly. Do not acknowledge a correction and then repeat the corrected behavior. "
        "If the operator says stop/cancel, stop the current output or action instead of joking about it."
    )
