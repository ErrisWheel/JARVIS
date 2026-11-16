"""Local style adaptation and conservative preference capture.

The style learner stores aggregate observations only. It never persists raw
speech transcripts or message examples, and skips messages matching sensitive
content markers.
"""
from __future__ import annotations

import re
from typing import Any

MODE_PROMPTS = {
    "assistant": (
        "You are in normal assistant mode. Be quick, capable, conversational, and useful. "
        "Lead with the answer instead of a ceremonial introduction. Be concise by default, "
        "then add detail when the task needs it. Use understated dry wit and friendly banter "
        "when it fits; never force jokes or agree just to please the user."
    ),
    "teaching": "You are in Teaching Mode. Let the user teach you a subject through conversation. Ask a focused follow-up when useful, identify concepts and relationships, periodically summarize your current understanding, and clearly distinguish hypotheses from confirmed facts. Do not claim permanent learning unless a memory is actually saved. Ask before saving important operational rules or uncertain knowledge.",
    "interview": "You are in Interview Mode. Actively interview the user to understand the chosen subject. Ask ONE useful question at a time, follow up on ambiguity, and periodically summarize what you have learned. Do not invent missing details.",
    "practice": "You are in Practice Mode. Test the user's understanding with one question at a time. Wait for their answer, explain mistakes constructively, and adjust difficulty. Do not claim to change model weights.",
    "review": "You are in Review Mode. Review the retrieved saved memories and conversation context. Summarize only what is actually present; identify gaps and contradictions and ask which correction should be applied.",
    "correction": "You are in Correction Mode. Treat the user's correction seriously. Explain what changed. Do not silently rewrite a saved memory: ask for confirmation before changing or deleting a permanent memory.",
}

SENSITIVE_TERMS = {
    "password", "passcode", "api key", "secret key", "credit card", "bank account",
    "diagnosis", "medical condition", "medication", "religion", "political party",
    "sexual orientation", "race", "ethnicity", "ssn", "social security", "one-time password",
}
PREFERENCE_PATTERNS = [
    r"\bI prefer\s+(.{3,180})[.!?]?$",
    r"\bI usually\s+(.{3,180})[.!?]?$",
    r"\bMy default(?: choice| setting)? is\s+(.{3,180})[.!?]?$",
]

CASUAL_MARKERS = {
    "bro", "dude", "man", "nah", "yeah", "yep", "nope", "lol", "lmao", "ngl",
    "tbh", "idk", "imo", "wtf", "shit", "damn", "wanna", "gonna", "kinda", "tho",
    "pls", "please", "hey", "yo", "ain't", "bruh", "fuck",
}
TAGLISH_MARKERS = {
    "ako", "mo", "naman", "pala", "yung", "hindi", "wala", "lang", "ba", "kasi",
    "ganito", "paano", "gusto", "sige", "talaga", "pero", "parang", "kaya", "dito",
    "diyan", "natin", "nyo", "niyo", "lang", "pa", "nga", "eh", "kailangan",
}
FORMAL_MARKERS = {"therefore", "furthermore", "moreover", "regarding", "kindly", "hereby", "sincerely"}
PROFANITY_MARKERS = {"shit", "fuck", "fucking", "wtf", "damn"}
HUMOR_MARKERS = {"lol", "lmao", "haha", "hehe", "rofl", "lmfao", "😂", "🤣"}


def contains_sensitive_marker(text: str) -> bool:
    lower = text.casefold()
    return any(term in lower for term in SENSITIVE_TERMS)


def detect_low_risk_preference(text: str):
    normalized = text.strip()
    if contains_sensitive_marker(normalized):
        return None
    for pattern in PREFERENCE_PATTERNS:
        match = re.search(pattern, normalized, flags=re.IGNORECASE)
        if match:
            fact = match.group(1).strip().rstrip(".?! ")
            if len(fact) >= 3:
                return f"User preference/context: {fact}"
    return None


def update_style_profile(current: dict[str, Any] | None, text: str) -> dict[str, Any] | None:
    """Update aggregate speaking-style observations without retaining the source text."""
    normalized = " ".join(text.split())
    if len(normalized) < 8 or contains_sensitive_marker(normalized):
        return None

    words = re.findall(r"[\w']+", normalized.casefold())
    if not words:
        return None
    word_set = set(words)
    word_count = len(words)
    casual_hits = len(word_set & CASUAL_MARKERS)
    taglish_hits = len(word_set & TAGLISH_MARKERS)
    formal_hits = len(word_set & FORMAL_MARKERS)
    humor_hits = len(word_set & HUMOR_MARKERS) + normalized.count("😂") + normalized.count("🤣")
    has_caps = any(token.isupper() and len(token) >= 2 for token in normalized.split())
    exclamations = normalized.count("!")
    questions = normalized.count("?")

    previous = current or {}
    samples = int(previous.get("samples", 0))
    average_words = float(previous.get("average_words", 0.0))
    average_casual = float(previous.get("casual_signal", 0.0))
    average_taglish = float(previous.get("taglish_signal", 0.0))
    average_formal = float(previous.get("formal_signal", 0.0))
    average_humor = float(previous.get("humor_signal", 0.0))
    average_profanity = float(previous.get("profanity_signal", 0.0))
    alpha = 1.0 / min(samples + 1, 8)

    new_average_words = word_count if samples == 0 else average_words + alpha * (word_count - average_words)
    casual_signal = min(1.0, casual_hits / max(1.0, word_count / 12.0))
    taglish_signal = min(1.0, taglish_hits / max(1.0, word_count / 10.0))
    formal_signal = min(1.0, formal_hits / max(1.0, word_count / 12.0))
    humor_signal = min(1.0, humor_hits / max(1.0, word_count / 12.0))
    profanity_signal = min(1.0, len(word_set & PROFANITY_MARKERS) / max(1.0, word_count / 12.0))
    new_casual = casual_signal if samples == 0 else average_casual + alpha * (casual_signal - average_casual)
    new_taglish = taglish_signal if samples == 0 else average_taglish + alpha * (taglish_signal - average_taglish)
    new_formal = formal_signal if samples == 0 else average_formal + alpha * (formal_signal - average_formal)
    new_humor = humor_signal if samples == 0 else average_humor + alpha * (humor_signal - average_humor)
    new_profanity = profanity_signal if samples == 0 else average_profanity + alpha * (profanity_signal - average_profanity)

    # Explicit style feedback has more weight than message length or slang counts.
    lower_text = normalized.casefold()
    casual_directive = bool(re.search(r"\b(?:talk|speak|reply|respond|sound)\b.{0,45}\b(?:casual|naturally|like me|less formal|less robotic)\b|\b(?:stop|don't)\s+(?:sounding|being)\s+(?:so\s+)?(?:formal|robotic)\b", lower_text))
    formal_directive = bool(re.search(r"\b(?:be|sound|write|respond)\b.{0,35}\b(?:formal|professional|structured)\b", lower_text))
    short_directive = bool(re.search(r"\b(?:keep it|make it|be)\s+(?:short|brief|concise)\b|\bno long explanations\b", lower_text))
    detail_directive = bool(re.search(r"\b(?:explain|go)\s+(?:into\s+)?(?:more|full|greater)\s+detail\b|\bbe more detailed\b", lower_text))
    humor_directive = bool(re.search(r"\b(?:be|make it)\s+(?:funny|witty|sarcastic|playful)\b", lower_text))
    no_humor_directive = bool(re.search(r"\b(?:no jokes|less humor|don't joke|do not joke)\b", lower_text))

    # Infer language mix from repeated function-word patterns, not individual stored words.
    if new_taglish >= 0.28:
        language = "Taglish / English-Filipino mix"
    elif new_taglish >= 0.12:
        language = "occasional Filipino-English mixing"
    else:
        language = "mostly English"

    tone = "casual and direct" if new_casual >= 0.12 or new_formal < 0.04 else "neutral and direct"
    if formal_directive:
        tone = "more formal and structured"
    elif casual_directive:
        tone = "casual and direct"
    elif new_formal >= 0.18 and new_casual < 0.08:
        tone = "more formal and structured"
    brevity = "brief" if new_average_words < 18 else "moderately detailed" if new_average_words < 42 else "detailed"
    if short_directive:
        brevity = "brief; prioritize concise answers"
    elif detail_directive:
        brevity = "detailed when explaining; include the useful steps"
    expression = "energetic punctuation" if exclamations >= 2 or (has_caps and questions) else "plain punctuation"
    humor = "playful markers appear sometimes; light banter is welcome" if new_humor >= 0.12 else "keep humor subtle and situational"
    if humor_directive:
        humor = "user explicitly welcomes witty, playful replies; keep it natural"
    elif no_humor_directive:
        humor = "avoid jokes unless the user invites them"
    profanity = (
        "casual profanity is acceptable when it naturally fits; do not force it"
        if new_profanity >= 0.12
        else "keep language clean unless the context naturally calls for otherwise"
    )

    return {
        "samples": samples + 1,
        "average_words": round(new_average_words, 1),
        "casual_signal": round(new_casual, 3),
        "taglish_signal": round(new_taglish, 3),
        "formal_signal": round(new_formal, 3),
        "humor_signal": round(new_humor, 3),
        "profanity_signal": round(new_profanity, 3),
        "tone": tone,
        "language": language,
        "brevity": brevity,
        "expression": expression,
        "humor": humor,
        "profanity_tolerance": profanity,
    }


def style_prompt(profile: dict[str, Any] | None) -> str:
    if not profile or int(profile.get("samples", 0)) < 1:
        return ""
    return (
        "\n\nConversation-style adaptation based on aggregate patterns from the user's messages "
        "(no raw messages are stored for this profile):\n"
        f"- Overall tone: {profile.get('tone', 'casual and direct')}\n"
        f"- Language pattern: {profile.get('language', 'mostly English')}\n"
        f"- Typical message style: {profile.get('brevity', 'brief')}\n"
        f"- Expression: {profile.get('expression', 'plain punctuation')}\n"
        f"- Humor preference: {profile.get('humor', 'keep humor subtle and situational')}\n"
        f"- Language boundaries: {profile.get('profanity_tolerance', 'do not force slang or profanity')}\n"
        f"- Observed messages: {profile.get('samples', 0)}\n"
        "Adapt naturally toward this rhythm and language mix without copying the user's exact phrases, "
        "overusing slang/profanity, or making assumptions about their identity. Mirror their language "
        "when they switch between English, Filipino, and Taglish."
    )
