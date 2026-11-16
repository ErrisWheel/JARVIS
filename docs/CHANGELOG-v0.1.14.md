# J.A.R.V.I.S. v0.1.14 — Intelligence and Instruction-Following Overhaul

## Behavior and context
- Adds persistent operator-instruction storage, separate from the adaptive style profile.
- Seeds the previously explicit operator preferences (no emojis; no unsolicited jokes) once during the database migration. They remain removable in Memory management.
- Places security rules first, explicit operator instructions second, the current request and task constraints next, and personality last.
- Expands bounded recent conversation context and stores a compact per-conversation task state.
- Stores recent user code anchors and the assistant's last output tail for continuation requests.

## Code and output reliability
- Replaces the previous fixed 512-token streaming output budget with task-aware budgets.
- Uses larger context/output budgets for code and complete-file tasks, while keeping simple conversational questions smaller.
- Automatically continues complex research and coding output when Ollama reports that generation stopped because of the output limit. Continuation context is compacted between passes while preserving the original user request, system rules and recent context. Continuation passes append to the existing answer instead of restarting it.
- Marks an answer as potentially incomplete if the configured continuation allowance is exhausted.
- Adds a safe ZIP export endpoint for complete fenced code blocks. Exports are stored under `F:\JARVIS\generated\exports` and include a review-before-running notice.
- Adds an explicit Stop control and maps short stop/cancel commands to cancellation rather than another model request.

## Model evaluation
- Adds an offline Ollama behavior regression benchmark for explicit instructions, code continuation, complete-file output, and truthful capability statements.
- Adds an optional installer for Qwen3.5 9B and GPT-OSS 20B. Downloads require typed approval and do not change the selected/default model.

## Security boundary
- No shell execution tool is added.
- Existing self-development approval/protected-file policy is unchanged.
- Exports are restricted to safe filenames, extensions, bounded sizes and the configured JARVIS root.
- All inference and benchmark requests go to the local Ollama endpoint.
