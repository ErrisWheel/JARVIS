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
