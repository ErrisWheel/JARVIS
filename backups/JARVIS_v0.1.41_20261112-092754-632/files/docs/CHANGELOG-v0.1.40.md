# J.A.R.V.I.S. v0.1.40 — Operations and Intelligence Expansion

## Integrated capabilities

- Workspace-owned memories and conversations, with legacy conversations migrated to the default Personal workspace.
- Conversation history management: workspace filters, search, pin, rename, archive/restore, move, and JSON export.
- Optional local embedding retrieval and same-workspace similarity graph, with FTS5/BM25 fallback.
- Persistent activity timeline and replay of actual backend events in the existing hologram. No fabricated model-thought events.
- Supervised local task planning with capability checks, explicit run approval, step persistence, cancellation, and manual resume after interruption.
- Persistent permission manager checked by supported backend routes; external network and arbitrary shell are locked off.
- Declarative local skills registry. It does not execute arbitrary extension code.
- SQLite online snapshots, integrity checks, and explicit restore confirmation.
- Local image attachments for the configured vision model and imported-document workflows.
- Preserved supervised code proposal/apply/rollback workflow.
- Updated local image-generation instructions so harmless, non-sexual, non-deceptive image requests are not blanket-refused solely because the subject is a real person.
- Workspace move typing correction and updated architecture/roadmap docs.

## Honest capability boundaries

- Semantic RAG is optional and requires an embedding model already installed and explicitly selected. No automatic model download. BM25 remains the default fallback.
- Voice interruption and browser audio constraints are retained; no dedicated native acoustic echo-cancellation DSP pipeline is claimed.
- PDF text extraction does not OCR scanned pages.
- Skill manifests are declarative only.
- The task runner does not execute shell commands or access the internet.
- SQLite backups do not back up model files, imports, or the whole application.
- Local image generation is subject to safety restrictions; the blanket identity-based refusal is removed, not all safeguards.
