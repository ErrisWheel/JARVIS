import pytest

from app.config import _validate_local_ollama_base_url


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("http://127.0.0.1:11434", "http://127.0.0.1:11434"),
        ("http://localhost:11434/", "http://localhost:11434"),
        ("http://[::1]:11434", "http://[::1]:11434"),
    ],
)
def test_local_ollama_addresses_are_accepted(value, expected):
    assert _validate_local_ollama_base_url(value) == expected


@pytest.mark.parametrize(
    "value",
    [
        "http://192.168.1.25:11434",
        "http://10.0.0.8:11434",
        "http://ollama.example.com:11434",
        "http://0.0.0.0:11434",
        "https://127.0.0.1:11434",
        "http://user:password@127.0.0.1:11434",
        "http://127.0.0.1:11434/api",
        "http://127.0.0.1:11434?proxy=remote",
        "http://127.0.0.1:99999",
    ],
)
def test_nonlocal_or_malformed_ollama_addresses_are_rejected(value):
    with pytest.raises(ValueError):
        _validate_local_ollama_base_url(value)


def test_missing_ollama_url_uses_local_default():
    assert _validate_local_ollama_base_url(None) == "http://127.0.0.1:11434"
