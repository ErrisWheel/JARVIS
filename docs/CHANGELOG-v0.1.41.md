# J.A.R.V.I.S. v0.1.41 — Adjustable workspace layout

## Added
- Persistent drag-resizing for the desktop core-system rail and chat rail width.
- Persistent row resizing for the tablet/mobile chat panel height.
- A dedicated composer grip to resize the message field from 110px to 360px.
- Keyboard-accessible separators: arrow keys resize in 12px steps; Shift+Arrow uses 32px steps.
- A one-click reset control in the top bar. Layout preferences are stored locally in browser localStorage.
- Safe size normalization and clamping for stored layout preferences.

## Preserved
- Existing three-column dashboard, routes, panels, chat sending, voice, file attachments, model selection, memory, Operations, Development Lab, and hologram integrations.
- Responsive tablet and mobile stacking behavior.
- No backend API, database, model, dependency or network changes beyond coordinated release version metadata.

## Defaults
- Core-system rail: 230px.
- Desktop chat rail: 430px.
- Tablet/mobile chat panel: 680px.
- Message composer: 160px.

Use the top-bar reset icon to restore defaults. Desktop rail widths and responsive chat height are independently adjustable; the composer height is adjustable at every viewport size.
