# J.A.R.V.I.S. v0.1.3 — Voice compatibility and dashboard layout

- Pins PyAV to `>=11,<19`, the compatible range for the installed faster-whisper decode path.
- Updates the optional voice installer so it also checks/fixes the PyAV major version.
- Locks the desktop dashboard to the viewport so the hologram and side panels no longer grow with the conversation.
- Makes the chat history independently scrollable and auto-scrolls to new messages unless the user has scrolled up.
- Makes the hologram grow modestly and gain additional orbiting nodes as actual saved memories increase.

The hologram growth is driven by saved memory count, not by every ordinary chat reply. This avoids treating every answer as permanently learned knowledge. Saving a memory still does not fine-tune Qwen model weights.
