"""
NDMP OS v6.0 - Tests for angelone_auth.py, angelone_instrument_lookup.py,
angelone_oi_poller.py, and generate_angelone_session.py.
No live Angel One API calls anywhere — all HTTP and client interactions mocked.
"""

import json
import os
import time as time_module

import pandas as pd
import pytest
from cryptography.fernet import Fernet

from ndmp_core.src.angelone_auth import AngelOneSessionManager
from ndmp_core.src.angelone_instrument_lookup import AngelOneInstrumentLookup
from ndmp_core.src.angelone_oi_poller import AngelOneOIPoller
from ndmp_core.src.generate_angelone_session import generate_session, write_access_token
from ndmp_core.src.exceptions import (
    AngelOneAuthError,
    AngelOneAPIError,
    AngelOneInstrumentLookupError,
)


# ---------------------------------------------------------------------------
# AngelOneSessionManager
# ---------------------------------------------------------------------------

def test_session_manager_round_trip(monkeypatch):
    key = Fernet.generate_key()
    plaintext = "test-jwt-token"
    encrypted = Fernet(key).encrypt(plaintext.encode())

    monkeypatch.setenv("ANGELONE_TOKEN_ENC_KEY", key.decode())
    monkeypatch.setenv("ANGELONE_ACCESS_TOKEN_ENCRYPTED", encrypted.decode())

    manager = AngelOneSessionManager()
    assert manager.get_access_token() == plaintext


def test_session_manager_missing_env(monkeypatch):
    monkeypatch.delenv("ANGELONE_TOKEN_ENC_KEY", raising=False)
    monkeypatch.delenv("ANGELONE_ACCESS_TOKEN_ENCRYPTED", raising=False)

    manager = AngelOneSessionManager()
    with pytest.raises(AngelOneAuthError, match="ANGELONE_TOKEN_ENC_KEY"):
        manager.get_access_token()


def test_session_manager_wrong_key(monkeypatch):
    right_key = Fernet.generate_key()
    wrong_key = Fernet.generate_key()
    encrypted = Fernet(right_key).encrypt(b"some-token")

    monkeypatch.setenv("ANGELONE_TOKEN_ENC_KEY", wrong_key.decode())
    monkeypatch.setenv("ANGELONE_ACCESS_TOKEN_ENCRYPTED", encrypted.decode())

    manager = AngelOneSessionManager()
    with pytest.raises(AngelOneAuthError, match="expired"):
        manager.get_access_token()


# ---------------------------------------------------------------------------
# AngelOneInstrumentLookup
# ---------------------------------------------------------------------------

def test_instrument_lookup_uses_cache_if_fresh(tmp_path):
    cache_path = tmp_path / "instruments.json"
    cache_path.write_text(json.dumps([
        {"token": "3456", "symbol": "BEL26AUGFUT", "exch_seg": "NFO"},
    ]))

    lookup = AngelOneInstrumentLookup(cache_path=str(cache_path))
    token = lookup.resolve_token("BEL26AUGFUT", "NFO")

    assert token == "3456"


def test_instrument_lookup_no_match_raises(tmp_path):
    cache_path = tmp_path / "instruments.json"
    cache_path.write_text(json.dumps([
        {"token": "3456", "symbol": "BEL26AUGFUT", "exch_seg": "NFO"},
    ]))

    lookup = AngelOneInstrumentLookup(cache_path=str(cache_path))
    with pytest.raises(AngelOneInstrumentLookupError, match="No Angel One instrument found"):
        lookup.resolve_token("NONEXISTENT", "NFO")


def test_instrument_lookup_ambiguous_match_raises(tmp_path):
    cache_path = tmp_path / "instruments.json"
    cache_path.write_text(json.dumps([
        {"token": "1", "symbol": "DUP", "exch_seg": "NFO"},
        {"token": "2", "symbol": "DUP", "exch_seg": "NFO"},
    ]))

    lookup = AngelOneInstrumentLookup(cache_path=str(cache_path))
    with pytest.raises(AngelOneInstrumentLookupError, match="Ambiguous"):
        lookup.resolve_token("DUP", "NFO")


def test_instrument_lookup_fetches_when_no_cache(tmp_path, monkeypatch):
    cache_path = tmp_path / "instruments.json"

    class _FakeResponse:
        def raise_for_status(self):
            pass
        def json(self):
            return [{"token": "999", "symbol": "TRENT26AUGFUT", "exch_seg": "NFO"}]

    monkeypatch.setattr(
        "ndmp_core.src.angelone_instrument_lookup.requests.get",
        lambda url, timeout: _FakeResponse(),
    )

    lookup = AngelOneInstrumentLookup(cache_path=str(cache_path))
    token = lookup.resolve_token("TRENT26AUGFUT", "NFO")

    assert token == "999"
    assert cache_path.exists()  # fetched result was cached


# ---------------------------------------------------------------------------
# AngelOneOIPoller
# ---------------------------------------------------------------------------

class _FakeInstrumentLookup:
    def __init__(self, token_map):
        self.token_map = token_map

    def resolve_token(self, symbol, exch_seg="NSE"):
        return self.token_map[symbol]


class _FakeSmartApiClient:
    def __init__(self, data_by_token):
        self.data_by_token = data_by_token
        self.calls = []

    def getMarketData(self, mode, exchangeTokens):
        self.calls.append((mode, exchangeTokens))
        all_tokens = [t for tokens in exchangeTokens.values() for t in tokens]
        fetched = [
            {"symbolToken": t, "opnInterest": self.data_by_token[t]}
            for t in all_tokens if t in self.data_by_token
        ]
        return {"status": True, "data": {"fetched": fetched, "unfetched": []}}


def test_poller_requires_symbols():
    with pytest.raises(ValueError):
        AngelOneOIPoller(symbols=[])


def test_poller_batched_call_persists_snapshot(tmp_path):
    lookup = _FakeInstrumentLookup({"BEL26AUGFUT": "111", "TRENT26AUGFUT": "222"})
    client = _FakeSmartApiClient({"111": 50000, "222": 75000})

    poller = AngelOneOIPoller(
        symbols=[
            {"symbol": "BEL26AUGFUT", "exch_seg": "NFO"},
            {"symbol": "TRENT26AUGFUT", "exch_seg": "NFO"},
        ],
        data_dir=str(tmp_path),
        instrument_lookup=lookup,
        smart_api_client=client,
    )

    snapshot = poller.poll_once()

    assert len(snapshot) == 2
    assert len(client.calls) == 1  # ONE batched call, not one per symbol

    bel_path = tmp_path / "BEL26AUGFUT.parquet"
    assert bel_path.exists()
    stored = pd.read_parquet(bel_path)
    assert stored.iloc[0]["open_interest"] == 50000


def test_poller_appends_across_cycles(tmp_path):
    lookup = _FakeInstrumentLookup({"BEL26AUGFUT": "111"})
    client = _FakeSmartApiClient({"111": 50000})

    poller = AngelOneOIPoller(
        symbols=[{"symbol": "BEL26AUGFUT", "exch_seg": "NFO"}],
        data_dir=str(tmp_path),
        instrument_lookup=lookup,
        smart_api_client=client,
    )

    poller.poll_once()
    client.data_by_token["111"] = 52000
    poller.poll_once()

    stored = pd.read_parquet(tmp_path / "BEL26AUGFUT.parquet")
    assert list(stored["open_interest"]) == [50000, 52000]


def test_poller_raises_on_missing_oi_field(tmp_path):
    lookup = _FakeInstrumentLookup({"BEL26AUGFUT": "111"})

    class _MissingOIClient:
        def getMarketData(self, mode, exchangeTokens):
            return {"status": True, "data": {"fetched": [{"symbolToken": "111"}]}}

    poller = AngelOneOIPoller(
        symbols=[{"symbol": "BEL26AUGFUT", "exch_seg": "NFO"}],
        data_dir=str(tmp_path),
        instrument_lookup=lookup,
        smart_api_client=_MissingOIClient(),
    )
    with pytest.raises(AngelOneAPIError, match="opnInterest"):
        poller.poll_once()


def test_poller_raises_on_partial_response(tmp_path):
    lookup = _FakeInstrumentLookup({"BEL26AUGFUT": "111", "TRENT26AUGFUT": "222"})
    client = _FakeSmartApiClient({"111": 50000})  # TRENT missing from response

    poller = AngelOneOIPoller(
        symbols=[
            {"symbol": "BEL26AUGFUT", "exch_seg": "NFO"},
            {"symbol": "TRENT26AUGFUT", "exch_seg": "NFO"},
        ],
        data_dir=str(tmp_path),
        instrument_lookup=lookup,
        smart_api_client=client,
    )
    with pytest.raises(AngelOneAPIError, match="did not include data"):
        poller.poll_once()


def test_poller_raises_on_non_ok_response(tmp_path):
    lookup = _FakeInstrumentLookup({"BEL26AUGFUT": "111"})

    class _ErrorClient:
        def getMarketData(self, mode, exchangeTokens):
            return {"status": False, "message": "session expired"}

    poller = AngelOneOIPoller(
        symbols=[{"symbol": "BEL26AUGFUT", "exch_seg": "NFO"}],
        data_dir=str(tmp_path),
        instrument_lookup=lookup,
        smart_api_client=_ErrorClient(),
    )
    with pytest.raises(AngelOneAPIError, match="non-ok response"):
        poller.poll_once()


# ---------------------------------------------------------------------------
# generate_angelone_session
# ---------------------------------------------------------------------------

def test_generate_session_success(monkeypatch):
    monkeypatch.setenv("ANGELONE_API_KEY", "test-api-key")

    class _FakeSmartConnect:
        def __init__(self, api_key):
            pass
        def generateSession(self, client_code, mpin, totp):
            return {"status": True, "data": {"jwtToken": "new-jwt-token"}}

    monkeypatch.setattr(
        "ndmp_core.src.generate_angelone_session.SmartConnect",
        _FakeSmartConnect,
        raising=False,
    )
    # Patch the deferred import target
    import sys, types
    fake_module = types.ModuleType("SmartApi")
    fake_module.SmartConnect = _FakeSmartConnect
    sys.modules["SmartApi"] = fake_module

    token = generate_session("C123", "1234", "567890")
    assert token == "new-jwt-token"


def test_generate_session_failure_response(monkeypatch):
    monkeypatch.setenv("ANGELONE_API_KEY", "test-api-key")

    class _FakeSmartConnect:
        def __init__(self, api_key):
            pass
        def generateSession(self, client_code, mpin, totp):
            return {"status": False, "message": "Invalid totp"}

    import sys, types
    fake_module = types.ModuleType("SmartApi")
    fake_module.SmartConnect = _FakeSmartConnect
    sys.modules["SmartApi"] = fake_module

    with pytest.raises(AngelOneAuthError, match="generateSession\\(\\) failed"):
        generate_session("C123", "1234", "000000")


def test_write_access_token_creates_line_if_absent(tmp_path):
    key = Fernet.generate_key()
    fernet = Fernet(key)
    env_path = tmp_path / "angelone.env"
    env_path.write_text("ANGELONE_CLIENT_CODE=C123\n")

    write_access_token(str(env_path), fernet, "fresh-token")

    lines = env_path.read_text().splitlines()
    token_line = [l for l in lines if l.startswith("ANGELONE_ACCESS_TOKEN_ENCRYPTED=")][0]
    encrypted_value = token_line.split("=", 1)[1]
    assert fernet.decrypt(encrypted_value.encode()).decode() == "fresh-token"


def test_write_access_token_replaces_existing_line(tmp_path):
    key = Fernet.generate_key()
    fernet = Fernet(key)
    env_path = tmp_path / "angelone.env"
    env_path.write_text(
        f"ANGELONE_ACCESS_TOKEN_ENCRYPTED={fernet.encrypt(b'old-token').decode()}\n"
    )

    write_access_token(str(env_path), fernet, "fresh-token")

    lines = env_path.read_text().splitlines()
    assert len(lines) == 1  # replaced, not duplicated
    encrypted_value = lines[0].split("=", 1)[1]
    assert fernet.decrypt(encrypted_value.encode()).decode() == "fresh-token"
