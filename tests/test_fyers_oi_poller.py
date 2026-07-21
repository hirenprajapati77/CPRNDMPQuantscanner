import os
import pytest
import pandas as pd
import numpy as np
from cryptography.fernet import Fernet

from ndmp_core.src.exceptions import FyersAuthError, FyersAPIError
from ndmp_core.src.fyers_auth import FyersTokenManager
from ndmp_core.src.fyers_oi_poller import FyersOIPoller


# Mock Client for Fyers depth() API
class MockFyersClient:
    def __init__(self, response_dict):
        self.response_dict = response_dict

    def depth(self, data):
        symbol = data["symbol"]
        if symbol in self.response_dict:
            return self.response_dict[symbol]
        raise Exception("Symbol not found in mock response dict")


def test_token_manager_missing_env(monkeypatch):
    """Test 1: FyersTokenManager raises FyersAuthError when required env vars are missing."""
    monkeypatch.delenv("FYERS_TOKEN_ENC_KEY", raising=False)
    monkeypatch.delenv("FYERS_ACCESS_TOKEN_ENCRYPTED", raising=False)
    
    manager = FyersTokenManager()
    with pytest.raises(FyersAuthError, match="Missing required env var"):
        manager.get_access_token()


def test_token_manager_decrypt_success(monkeypatch):
    """Test 2: FyersTokenManager successfully decrypts encrypted credentials using Fernet."""
    key = Fernet.generate_key()
    token = b"my-plain-fyers-access-token"
    fernet = Fernet(key)
    encrypted_token = fernet.encrypt(token)

    monkeypatch.setenv("FYERS_TOKEN_ENC_KEY", key.decode())
    monkeypatch.setenv("FYERS_ACCESS_TOKEN_ENCRYPTED", encrypted_token.decode())

    manager = FyersTokenManager()
    assert manager.get_access_token() == "my-plain-fyers-access-token"


def test_token_manager_decrypt_invalid(monkeypatch):
    """Test 3: FyersTokenManager raises FyersAuthError if key and token do not match (InvalidToken)."""
    wrong_key = Fernet.generate_key()
    fernet = Fernet(Fernet.generate_key())
    encrypted_token = fernet.encrypt(b"token")

    monkeypatch.setenv("FYERS_TOKEN_ENC_KEY", wrong_key.decode())
    monkeypatch.setenv("FYERS_ACCESS_TOKEN_ENCRYPTED", encrypted_token.decode())

    manager = FyersTokenManager()
    with pytest.raises(FyersAuthError, match="Failed to decrypt Fyers access token"):
        manager.get_access_token()


def test_poller_invalid_symbols_list():
    """Test 4: FyersOIPoller raises ValueError on empty symbol list."""
    with pytest.raises(ValueError, match="FyersOIPoller requires a non-empty symbol list"):
        FyersOIPoller(symbols=[])


def test_poller_missing_client_id(monkeypatch):
    """Test 5: FyersOIPoller raises FyersAuthError when FYERS_CLIENT_ID is missing from env."""
    monkeypatch.delenv("FYERS_CLIENT_ID", raising=False)
    # Mock TokenManager to prevent decryption failure
    class FakeTokenManager:
        def get_access_token(self):
            return "fake-token"

    # Mock fyers_apiv3 import to allow test execution without local module installation
    import sys
    from unittest.mock import MagicMock
    mock_module = MagicMock()
    monkeypatch.setitem(sys.modules, "fyers_apiv3", mock_module)
    monkeypatch.setitem(sys.modules, "fyers_apiv3.fyersModel", mock_module)

    poller = FyersOIPoller(symbols=["NSE:NIFTY26FEB24F"], token_manager=FakeTokenManager())
    with pytest.raises(FyersAuthError, match="Missing required env var: FYERS_CLIENT_ID"):
        poller._get_client()


def test_poller_depth_success(tmp_path):
    """Test 6: FyersOIPoller successfully fetches depth, parses 'oi' and persists to Parquet."""
    mock_responses = {
        "NSE:NIFTY26FEB24F": {
            "s": "ok",
            "d": {
                "NSE:NIFTY26FEB24F": {
                    "oi": 125000
                }
            }
        }
    }
    mock_client = MockFyersClient(mock_responses)
    poller = FyersOIPoller(
        symbols=["NSE:NIFTY26FEB24F"],
        data_dir=str(tmp_path),
        fyers_client=mock_client
    )

    df = poller.poll_once()
    assert len(df) == 1
    assert df.iloc[0]["symbol"] == "NSE:NIFTY26FEB24F"
    assert df.iloc[0]["open_interest"] == 125000

    # Verify persistence
    persisted_path = tmp_path / "NSE:NIFTY26FEB24F.parquet"
    assert persisted_path.exists()
    persisted_df = pd.read_parquet(str(persisted_path))
    assert len(persisted_df) == 1
    assert persisted_df.iloc[0]["open_interest"] == 125000


def test_poller_depth_append_cross_cycle(tmp_path):
    """Test 7: FyersOIPoller appends subsequent snapshots cleanly across polling cycles."""
    mock_responses_1 = {
        "NSE:NIFTY26FEB24F": {"s": "ok", "d": {"NSE:NIFTY26FEB24F": {"oi": 1000}}}
    }
    mock_responses_2 = {
        "NSE:NIFTY26FEB24F": {"s": "ok", "d": {"NSE:NIFTY26FEB24F": {"oi": 1500}}}
    }

    poller1 = FyersOIPoller(
        symbols=["NSE:NIFTY26FEB24F"],
        data_dir=str(tmp_path),
        fyers_client=MockFyersClient(mock_responses_1)
    )
    poller1.poll_once()

    poller2 = FyersOIPoller(
        symbols=["NSE:NIFTY26FEB24F"],
        data_dir=str(tmp_path),
        fyers_client=MockFyersClient(mock_responses_2)
    )
    poller2.poll_once()

    persisted_path = tmp_path / "NSE:NIFTY26FEB24F.parquet"
    df = pd.read_parquet(str(persisted_path))
    assert len(df) == 2
    assert list(df["open_interest"]) == [1000, 1500]


def test_poller_depth_malformed_response(tmp_path):
    """Test 8: FyersOIPoller raises FyersAPIError when API response has non-ok status or missing 'oi' field."""
    # Scenario A: status not 'ok'
    mock_responses_bad_status = {
        "NSE:NIFTY26FEB24F": {"s": "error", "errmsg": "Invalid symbol"}
    }
    poller_bad = FyersOIPoller(
        symbols=["NSE:NIFTY26FEB24F"],
        data_dir=str(tmp_path),
        fyers_client=MockFyersClient(mock_responses_bad_status)
    )
    with pytest.raises(FyersAPIError, match="returned a non-ok response"):
        poller_bad.poll_once()

    # Scenario B: missing 'oi' field in data
    mock_responses_missing_oi = {
        "NSE:NIFTY26FEB24F": {"s": "ok", "d": {"NSE:NIFTY26FEB24F": {"not_oi": 1000}}}
    }
    poller_missing_oi = FyersOIPoller(
        symbols=["NSE:NIFTY26FEB24F"],
        data_dir=str(tmp_path),
        fyers_client=MockFyersClient(mock_responses_missing_oi)
    )
    with pytest.raises(FyersAPIError, match="has no 'oi' field"):
        poller_missing_oi.poll_once()
