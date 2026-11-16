# Security and privacy contract

## Enabled in this starter

- Backend bound to `127.0.0.1` only.
- Frontend dev server bound to `127.0.0.1` only.
- Random local API token generated at `F:\JARVIS\data\.api_token`; frontend proxy reads it server-side.
- No API for executing arbitrary commands or scripts.
- No generic filesystem access endpoint.
- Imported file listing is limited to `F:\JARVIS\imports` with resolved-path containment checks; symlinks escaping the directory are rejected.
- No external network/search tool is implemented.
- Model inference uses local Ollama.
- Dependency/model downloads require the user to run a script and approve its prompt.

## Not guaranteed

The user's request to block all access to games and all paths outside JARVIS cannot be fully guaranteed by a Python allowlist when the process runs under the user's everyday Windows account. If the process is compromised, it inherits that account's Windows permissions. Hard isolation needs a separate Windows account, Windows Sandbox, AppContainer/lowbox, or another OS-enforced boundary. The user declined a separate account; a stronger no-account isolation option must be evaluated and penetration-tested before claiming this requirement is fully met.

## Never implement

- Shell/PowerShell arbitrary command execution from model output.
- Automatic browsing, telemetry, cloud inference, or model fallback.
- Broad drive indexing.
- Unattended destructive file actions.
- Secrets in memory or logs.

## Approval rule for future tools

A web search, external API call, software installation, file modification outside the controlled workspace, or other material action must produce a specific approval request. Approval is per operation, not a blanket permanent permission.


## v0.1.31 filesystem and document notes

The application-managed data/import directories are checked against the project root, and the import resolver rejects traversal, symbolic-link components, and Windows junction aliases. This is defense-in-depth for the local API, not an OS-enforced sandbox or a defense against arbitrary code already running as the logged-in Windows user. Keep the project on the operator-controlled `F:\JARVIS` directory, do not enable arbitrary command execution, and only place documents in `F:\JARVIS\imports`. Document parsers never execute macros or scripts; extracted document text is passed as untrusted reference material. Office archives are bounded by entry count and uncompressed size. PDF extraction is optional and text-based; no OCR is performed.
