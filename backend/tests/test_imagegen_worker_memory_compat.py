from types import SimpleNamespace

from app.imagegen_worker import _enable_vae_memory_saving


def test_uses_current_vae_level_diffusers_methods():
    calls = []
    pipe = SimpleNamespace(
        vae=SimpleNamespace(
            enable_slicing=lambda: calls.append("slicing"),
            enable_tiling=lambda: calls.append("tiling"),
        )
    )

    enabled = _enable_vae_memory_saving(pipe)

    assert enabled == ("slicing", "tiling")
    assert calls == ["slicing", "tiling"]


def test_falls_back_to_legacy_pipeline_methods():
    calls = []
    pipe = SimpleNamespace(
        enable_vae_slicing=lambda: calls.append("slicing"),
        enable_vae_tiling=lambda: calls.append("tiling"),
    )

    enabled = _enable_vae_memory_saving(pipe)

    assert enabled == ("slicing", "tiling")
    assert calls == ["slicing", "tiling"]


def test_missing_optional_vae_optimizations_do_not_crash(capsys):
    pipe = SimpleNamespace(vae=SimpleNamespace())

    enabled = _enable_vae_memory_saving(pipe)

    assert enabled == ()
    assert "continuing without it" in capsys.readouterr().err


def test_one_optimization_failure_does_not_skip_the_other(capsys):
    calls = []

    def broken_slicing():
        raise RuntimeError("not supported")

    pipe = SimpleNamespace(
        vae=SimpleNamespace(
            enable_slicing=broken_slicing,
            enable_tiling=lambda: calls.append("tiling"),
        )
    )

    enabled = _enable_vae_memory_saving(pipe)

    assert enabled == ("tiling",)
    assert calls == ["tiling"]
    assert "not supported" in capsys.readouterr().err
