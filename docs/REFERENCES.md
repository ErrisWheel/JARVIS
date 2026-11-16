# Technical references consulted

- Ollama Windows installation documentation: https://github.com/ollama/ollama/blob/main/docs/windows.mdx — native Windows app; custom install directory `/DIR=...`; models redirected with `OLLAMA_MODELS`.
- Ollama NVIDIA GPU support: https://github.com/ollama/ollama/blob/main/docs/gpu.mdx — supported NVIDIA GPUs includes RTX 5080; current docs specify NVIDIA driver 550+.
- Qwen3 Ollama library: https://ollama.com/library/qwen3 — `qwen3:8b` is listed at approximately 5.2 GB, Q4_K_M.
- Vite guide: https://vite.dev/guide/ — Node compatibility requirements.
- Node release schedule: https://github.com/nodejs/Release/blob/main/README.md — Node 22 is a supported LTS line; use Node 22.12+ for this project baseline.

Versions and model catalogs change. Recheck upstream compatibility when updating dependencies or swapping model families.
