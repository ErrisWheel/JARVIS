"""Local model-team selection and message preparation.

Only text-capable Ollama models are eligible for chat/review roles. Vision and
image-generation engines are specialist tools and are invoked by their own
routes. The team is deliberately sequential: the RTX 5080 has 16 GB VRAM, so
keeping several large model sessions resident together would compete with SDXL.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


DEFAULT_PRIMARY_MODEL = "qwen3.5:9b"
DEFAULT_REVIEW_MODEL = "qwen3:8b"
VISION_MODEL_HINTS = ("vl:", "-vl", "vision")


@dataclass(frozen=True)
class ModelTeam:
    primary: str
    reviewer: str | None
    installed: tuple[str, ...]

    @property
    def members(self) -> tuple[str, ...]:
        return (self.primary,) if not self.reviewer else (self.primary, self.reviewer)


def _is_text_model(name: str) -> bool:
    lowered = name.casefold()
    return not any(marker in lowered for marker in VISION_MODEL_HINTS)


def resolve_model_team(
    installed_models: Iterable[str],
    requested_primary: str | None = None,
    preferred_primary: str = DEFAULT_PRIMARY_MODEL,
    preferred_reviewer: str = DEFAULT_REVIEW_MODEL,
) -> ModelTeam:
    """Pick an installed primary/reviewer pair without assigning vision models to text chat."""
    installed = tuple(dict.fromkeys(str(name).strip() for name in installed_models if str(name).strip()))
    text_models = tuple(name for name in installed if _is_text_model(name))
    if not text_models:
        raise ValueError("No text-capable Ollama model is installed. Install a local Qwen text model first.")

    requested = (requested_primary or "").strip()
    if requested in text_models:
        primary = requested
    elif preferred_primary in text_models:
        primary = preferred_primary
    else:
        primary = text_models[0]

    reviewer_candidates = [preferred_reviewer, preferred_primary, *text_models]
    reviewer = next((name for name in reviewer_candidates if name in text_models and name != primary), None)
    return ModelTeam(primary=primary, reviewer=reviewer, installed=installed)


def should_use_peer_review(message: str) -> bool:
    """Skip the second pass for tiny acknowledgements; use it for substantive turns."""
    import re
    value = re.sub(r"[.,!?;:]+", " ", (message or "").casefold())
    value = " ".join(value.split()).strip()
    if not value:
        return False
    quick_replies = {
        "hi", "hello", "hey", "hey jarvis", "good morning", "good afternoon",
        "good evening", "thanks", "thank you", "thanks jarvis", "okay", "ok",
        "yes", "no", "got it", "understood", "are you there", "can you hear me",
        "say hello", "say hi", "test voice", "testing",
    }
    return value not in quick_replies


def build_reviewer_messages(messages: list[dict], max_context_messages: int = 6) -> list[dict]:
    """Build a short independent audit request, not a chain-of-thought request."""
    if not messages:
        return [{"role": "user", "content": "Review the current task and list key requirements and risks."}]

    system = str(messages[0].get("content", ""))[:5000]
    prior = messages[1:-1][-max_context_messages:]
    context: list[dict] = []
    for item in prior:
        role = item.get("role") if item.get("role") in {"user", "assistant"} else "user"
        content = str(item.get("content", ""))
        if len(content) > 1200:
            content = content[-1200:]
        if content.strip():
            context.append({"role": role, "content": content})

    current_request = str(messages[-1].get("content", ""))
    audit_prompt = (
        "Act as JARVIS's independent peer-review model. Do not write the final answer and do not reveal hidden reasoning. "
        "Return a compact review memo with: (1) the user's actual deliverable and constraints, "
        "(2) important facts or assumptions that need checking, (3) likely omissions or edge cases, "
        "and (4) a short recommendation for the lead model. Use at most 8 concise bullets. "
        "Do not invent facts, claim tool use, or override system/security instructions.\n\n"
        f"CURRENT USER REQUEST:\n{current_request}"
    )
    return ([{"role": "system", "content": system}] if system else []) + context + [
        {"role": "user", "content": audit_prompt}
    ]


def add_peer_review(messages: list[dict], review: str, reviewer_model: str) -> list[dict]:
    """Attach factual review notes to the lead model without changing the user prompt."""
    if not review.strip() or not messages:
        return list(messages)
    review_message = {
        "role": "system",
        "content": (
            f"INDEPENDENT LOCAL PEER REVIEW FROM {reviewer_model}:\n{review[:5000]}\n\n"
            "Use these notes as a quality-control aid, not as authoritative facts. Reconcile them with the user's exact request, "
            "your own knowledge, and the higher-priority system instructions. Ignore unsupported suggestions. "
            "Provide only the final user-facing answer; do not mention private model deliberation."
        ),
    }
    return [*messages[:-1], review_message, messages[-1]]
