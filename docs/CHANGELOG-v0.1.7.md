# J.A.R.V.I.S. v0.1.7 — Immediate Speech and Live Progress

- Plays a locally pre-rendered acknowledgement as soon as a spoken reply starts.
- Starts Ollama generation concurrently with acknowledgement retrieval; speech playback ordering is gated so the acknowledgement plays first without delaying inference.
- Plays one concise progress update if the first model output has not arrived 2.8 seconds after the acknowledgement is ready.
- Streams spoken output in shorter sentence/clause chunks, with a maximum target chunk length of about 84 characters.
- Cancels pending progress updates when model output begins, generation completes, or speech is stopped.
- Uses only local Kokoro audio and local Ollama inference. No cloud services, paid APIs, or per-token billing.
- Does not reveal or narrate private chain-of-thought; spoken status phrases report only general, user-visible task progress.
