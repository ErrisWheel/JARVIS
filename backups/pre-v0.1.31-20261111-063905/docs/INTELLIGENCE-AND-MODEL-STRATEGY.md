# Intelligence strategy: capability, reliability and model limits

J.A.R.V.I.S. should be evaluated as a complete local assistant system, not only by the size of its language model. Retrieval, memory quality, tool reliability, task state, output validation, and safe file operations all contribute to useful capability.

## What this release improves
- Operator corrections are stored as explicit instructions, separately from inferred style.
- Recent conversation history is bounded and accompanied by a compact continuation state.
- Code continuation has an explicit anchor and task-specific generation budget.
- Long coding output can continue automatically when Ollama reports an output-length stop.
- Complete code blocks can be packaged into downloadable files.
- Local model candidates can be compared on repeatable JARVIS-specific cases.

## Candidate models for this PC

The RTX 5080 has 16 GB of VRAM, and the PC has 32 GB of system RAM. Model size alone does not determine runtime memory: context/KV cache, Windows display usage, other GPU workloads, and offloading also matter.

- `qwen3.5:9b` is the sensible first candidate to test for general assistant work. The Ollama library currently lists it around 6.6–7.6 GB depending on build. This is a model download size, not a promise of exact runtime VRAM use.
- `gpt-oss:20b` is a stronger reasoning-oriented candidate worth evaluating. Its Ollama package is about 14 GB; that is tight on a 16 GB card once Windows and inference memory are included, so partial CPU/system-RAM offload may be needed and could reduce speed.

The installer never downloads these without an explicit typed approval and does not alter the selected model. Benchmark the current `qwen3:8b` first, then compare each installed candidate on the same local test suite and actual tasks.

## Honest target

The project can improve reliability substantially by adding deterministic tools and stricter state management around the model. It cannot honestly promise that a local model on this hardware will outperform every commercial Pro model on every domain. Commercial services may use larger models, more compute, proprietary training and infrastructure. The right engineering target is measurable: improve JARVIS's task success on the operator's real workflows, preserve privacy and cost constraints, and document failures instead of pretending they did not happen.

## Non-negotiable boundaries
- Local inference by default; no paid APIs or subscription services.
- No shell/terminal execution tool exposed to the model.
- No automatic access beyond the configured JARVIS project root and approved imports.
- Destructive or security-sensitive changes remain approval-gated.
- Self-development code cannot edit its protected enforcement layer.
