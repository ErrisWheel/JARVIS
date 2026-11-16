# J.A.R.V.I.S. v0.1.8 — Natural Turn-Taking and Faster Speech

- Simple conversational checks and short factual questions no longer receive acknowledgement or progress filler.
- Substantial tasks can receive a brief acknowledgement and one truthful progress update while local Ollama inference runs.
- Ollama streaming begins immediately; status-audio retrieval runs concurrently and gates only playback ordering, never model generation.
- The previous acknowledgement-before-inference serial wait has been removed.
- Defaults to Kokoro `am_michael` instead of the older-sounding `bm_george` preset.
- Raises default speech rate from 0.96x to 1.12x and adds selectable rates from 1.00x to 1.15x.
- Starts preparing spoken clauses earlier by lowering the clause threshold and maximum segment size.
- Status audio cache is keyed by voice and speed so selected settings are respected.
- Continues to use local Kokoro and local Ollama only; no paid APIs, subscriptions, or cloud speech.
