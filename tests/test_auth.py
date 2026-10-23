# tests/test_auth.py
import pytest
from fastapi import HTTPException

from src.auth import require_api_key


def test_no_key_configured_allows_any_request(monkeypatch):
    monkeypatch.delenv("API_KEY", raising=False)

    # Neither header nor query param supplied -- must not raise.
    require_api_key(x_api_key=None, api_key=None)


def test_correct_header_key_is_accepted(monkeypatch):
    monkeypatch.setenv("API_KEY", "secret123")

    require_api_key(x_api_key="secret123", api_key=None)


def test_correct_query_param_key_is_accepted(monkeypatch):
    # Needed for the document-viewer <iframe>, which can't send a header --
    # see src/auth.py's docstring.
    monkeypatch.setenv("API_KEY", "secret123")

    require_api_key(x_api_key=None, api_key="secret123")


def test_missing_key_is_rejected_when_one_is_configured(monkeypatch):
    monkeypatch.setenv("API_KEY", "secret123")

    with pytest.raises(HTTPException) as exc_info:
        require_api_key(x_api_key=None, api_key=None)
    assert exc_info.value.status_code == 401


def test_wrong_key_is_rejected(monkeypatch):
    monkeypatch.setenv("API_KEY", "secret123")

    with pytest.raises(HTTPException) as exc_info:
        require_api_key(x_api_key="wrong", api_key=None)
    assert exc_info.value.status_code == 401


def test_header_takes_precedence_over_query_param(monkeypatch):
    monkeypatch.setenv("API_KEY", "secret123")

    # Correct header should win even if a stale/wrong query param is present.
    require_api_key(x_api_key="secret123", api_key="wrong")
