"""Deterministic task routing helpers for local JARVIS conversations."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

CONTINUATION_RE = re.compile(
    r"\b(?:continue(?:\s+(?:from\s+(?:here|there|where\s+you\s+left\s+off)|where\s+I\s+left\s+off))?|"
    r"keep\s+going|carry\s+on|finish\s+(?:the\s+)?(?:rest|remaining\s+part)|"
    r"pick\s+up\s+where\s+you\s+left\s+off|finish\s+it\s+in\s+one\s+go|"
    r"all\s+in\s+one\s+go|give\s+it\s+all\s+at\s+once|"
    r"do\s+not\s+split\s+it|don't\s+split\s+it)\b",
    re.IGNORECASE,
)
WHOLE_FILE_RE = re.compile(
    r"\b(?:whole|entire|complete|full)\s+(?:javascript\s+|typescript\s+|python\s+|css\s+|html\s+)?(?:file|script|source|code)\b|"
    r"\bsend\s+(?:me\s+)?the\s+(?:whole|entire|complete|full)\b|"
    r"\ball\s+of\s+the\s+(?:code|file|script)\b",
    re.IGNORECASE,
)
CODE_RE = re.compile(
    r"\b(?:code|coding|program|programming|javascript|typescript|python|html|css|sql|debug|bug|function|class|script|website|application|app|api|backend|frontend|file|files|repository|repo)\b",
    re.IGNORECASE,
)
TASK_FOLLOWUP_RE = re.compile(
    r"\b(?:add|remove|change|replace|fix|update|modify|adjust|switch)\b|"
    r"\buse\s+(?:a|an|the)\b|\bmake\s+it\b|\binstead\b|"
    r"\bthat\s+(?:line|function|button|section|file|script|code)\b|"
    r"\bthe\s+(?:function|file|script|code)\b", re.I
)
COMPLEX_RE = re.compile(
    r"\b(?:debug|diagnose|architect|design|refactor|implement|build|create|write|research|compare|analy[sz]e|plan|review|optimi[sz]e|integrate|migrate|generate)\b",
    re.IGNORECASE,
)

@dataclass(frozen=True)
class TaskProfile:
    kind: str
    continuation: bool
    whole_file: bool
    code_task: bool
    complex: bool
    num_ctx: int
    num_predict: int
    max_continuations: int
    temperature: float


def classify_task(message: str, previous_state: dict[str, Any] | None = None) -> TaskProfile:
    text = (message or "").strip()
    previous_kind = str((previous_state or {}).get("task_kind") or "")
    active_code_context = previous_kind in {"coding", "complete_code_output", "code_continuation"}
    contextual_followup = bool(
        active_code_context and len(text) <= 1000 and TASK_FOLLOWUP_RE.search(text)
    )
    continuation = bool(CONTINUATION_RE.search(text)) or bool(contextual_followup)
    whole_file = bool(WHOLE_FILE_RE.search(text))
    code_task = bool(CODE_RE.search(text)) or bool(re.search(r"```|\bfunction\s+\w+|\bconst\s+\w+\s*=", text))
    # Short revisions inherit the active coding task instead of resetting task state.
    code_task = code_task or continuation
    complex_task = bool(COMPLEX_RE.search(text)) and len(text) > 45
    if whole_file:
        kind = "complete_code_output"
    elif continuation:
        kind = "code_continuation" if code_task else "continuation"
    elif code_task:
        kind = "coding"
    elif complex_task:
        kind = "complex"
    else:
        kind = "conversation"

    if whole_file or (continuation and code_task):
        return TaskProfile(kind, continuation, whole_file, True, True, 16384, 4096, 3, 0.25)
    if code_task:
        return TaskProfile(kind, continuation, whole_file, True, True, 16384, 4096, 2, 0.28)
    if complex_task:
        return TaskProfile(kind, continuation, whole_file, False, True, 8192, 2048, 1, 0.48)
    return TaskProfile(kind, continuation, whole_file, False, False, 8192, 1024, 0, 0.58)


def extract_code_anchor(text: str, max_chars: int = 5000) -> str:
    """Extract the last explicit fenced block or a short code-like tail as a continuation anchor."""
    source = text or ""
    fences = list(re.finditer(r"```[^\n]*\n(.*?)```", source, flags=re.DOTALL))
    if fences:
        return fences[-1].group(1).strip()[-max_chars:]
    lines = source.splitlines()
    code_lines: list[str] = []
    for line in reversed(lines):
        if not line.strip():
            if code_lines:
                break
            continue
        if re.search(r"(?:=|=>|\{|\}|;|\(|\)|\b(?:const|let|var|function|return|class|import|export)\b|</?[A-Za-z])", line):
            code_lines.append(line)
        elif code_lines:
            break
    return "\n".join(reversed(code_lines))[-max_chars:]


def continuation_directive(message: str, state: dict[str, Any] | None = None) -> str:
    profile = classify_task(message, state)
    if profile.whole_file:
        return (
            "\n\nOUTPUT REQUIREMENT — COMPLETE FILE: The operator explicitly requested the whole/complete file. "
            "Return the entire requested file from its first line to its final line. Do not provide a fragment, "
            "do not restart an unrelated earlier file, do not use ellipses or placeholders, and do not claim "
            "completion until every required section is present. Prefer one complete code fence per file with a filename label."
        )
    if not profile.continuation:
        return ""
    state = state or {}
    current_anchor = extract_code_anchor(message)
    assistant_tail = str(state.get("last_assistant_tail") or "")
    last_task_kind = str(state.get("task_kind") or "")
    saved_user_anchor = str(state.get("last_user_code_anchor") or "")
    if current_anchor:
        anchor_block = f"\nExact continuation anchor supplied in the current operator message (the next output must begin AFTER this; never repeat it):\n{current_anchor[-3500:]}"
    elif assistant_tail and last_task_kind in {"coding", "complete_code_output", "code_continuation"}:
        anchor_block = f"\nThe previous assistant output ended with this exact text; continue immediately after it without repeating it:\n{assistant_tail[-1800:]}"
    elif saved_user_anchor:
        anchor_block = f"\nExact code anchor saved from the operator's previous message (the next output must begin AFTER this; never repeat it):\n{saved_user_anchor[-3500:]}"
    else:
        anchor_block = "\nUse the immediately preceding assistant message as the continuation point. Continue only from its final unfinished point."
    return (
        "\n\nOUTPUT REQUIREMENT — CONTINUE IN PLACE: This is a continuation request, not a request to regenerate the file. "
        "Do not repeat the product array, variable declarations, function headers, or any earlier content already supplied. "
        "Start with the very next line/character required after the anchor. Do not add a new introduction or restart the code. "
        "If the operator supplies a partial line, complete that line first. If the last output ended mid-line, continue that line."
        + anchor_block
    )


def should_auto_continue(profile: TaskProfile, done_reason: str | None, round_index: int) -> bool:
    return bool(
        done_reason == "length"
        and profile.max_continuations > round_index
        and (profile.complex or profile.code_task or profile.whole_file or profile.continuation)
    )
