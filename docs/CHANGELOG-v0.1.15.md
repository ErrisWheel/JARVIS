# v0.1.15 — PowerShell and inline image display

- Added process-scoped CMD launchers for the local benchmark and reasoning-model installer scripts.
- Documented safe PowerShell execution-policy steps without permanently weakening policy.
- Generated images are fetched through the authenticated same-origin API and rendered as browser blob URLs, so the inline preview does not depend on native `<img>` requests forwarding the local API token.
- Existing conversation history now hydrates valid local generated-image markers and local JARVIS image links into inline previews.
- The UI validates generated filenames and refuses to fetch arbitrary model-supplied URLs.
- The model instructions now distinguish local image generation from cloud/external tools and prohibit fabricated image URLs or internal image markers.
- Natural scene shorthand such as “give me another scenic view” is routed to local SDXL generation.
- No new packages, models or internet downloads are required.
