# J.A.R.V.I.S. v0.1.13 — SDXL Diffusers compatibility hotfix

- Fixed image generation crashing when the installed Diffusers release does not expose `StableDiffusionXLPipeline.enable_vae_slicing()` or `enable_vae_tiling()`.
- Uses the current VAE-level APIs (`pipe.vae.enable_slicing()` and `pipe.vae.enable_tiling()`) when available.
- Retains compatibility with older pipeline-level methods.
- Treats VAE slicing/tiling as optional optimizations: an unavailable optimization is logged but no longer aborts generation.
- No model, runtime, package download, or reinstall is required.

## Verification

- Added compatibility tests for current Diffusers, older Diffusers, unavailable helpers, and one-helper failure.
- Run the backend test suite and perform one real SDXL generation on the target RTX 5080 PC.
