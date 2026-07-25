"""
NDMP OS v6.0 - Tests for fyers_token_refresh.py and fyers_oi_health_check.py.
All HTTP calls and filesystem/time dependencies are mocked/injected.
"""

import os
import time as time_module
from datetime import datetime, date

import pytest
from cryptography.fernet import Fernet

from ndmp_core.src.fyers_token_refresh import (
    refresh_access_token,
    write_new_access_token,
)
from ndmp_core.src.fyers_oi_health_check import check_poller_health, most_recent_mtime
from ndmp_core.src.trading_calendar import NSETradingCalendar
from ndmp_core.src.exceptions import FyersAuthError, FyersTokenRefreshError


# ---------------------------------------------------------------------------
# refresh_access_token
# ---------------------------------------------------------------------------

def test_refresh_missing_env_vars():
    with pytest.raises(FyersAuthError, match="Missing required env var"):
        refresh_access_token({})


def test_refresh_success(monkeypatch):
    key = Fernet.generate_key()
    fernet = Fernet(key)
    env = {
        "FYERS_CLIENT_ID": "ABC123-100",
        "FYERS_TOKEN_ENC_KEY": key.decode(),
        "FYERS_SECRET_KEY": fernet.encrypt(b"my-secret").decode(),
        "FYERS_REFRESH_TOKEN_ENCRYPTED": fernet.encrypt(b"my-refresh-token").decode(),
        "FYERS_PIN_ENCRYPTED": fernet.encrypt(b"1234").decode(),
    }

    class _FakeResponse:
        status_code = 200
        def json(self):
            return {"s": "ok", "access_token": "brand-new-access-token"}

    def _fake_post(url, headers, json, timeout):
        assert json["grant_type"] == "refresh_token"
        assert json["refresh_token"] == "my-refresh-token"
        assert json["pin"] == "1234"
        return _FakeResponse()

    monkeypatch.setattr("ndmp_core.src.fyers_token_refresh.requests.post", _fake_post)

    token = refresh_access_token(env)
    assert token == "brand-new-access-token"


def test_refresh_expired_refresh_token(monkeypatch):
    key = Fernet.generate_key()
    fernet = Fernet(key)
    env = {
        "FYERS_CLIENT_ID": "ABC123-100",
        "FYERS_TOKEN_ENC_KEY": key.decode(),
        "FYERS_SECRET_KEY": fernet.encrypt(b"my-secret").decode(),
        "FYERS_REFRESH_TOKEN_ENCRYPTED": fernet.encrypt(b"expired-token").decode(),
        "FYERS_PIN_ENCRYPTED": fernet.encrypt(b"1234").decode(),
    }

    class _FakeResponse:
        status_code = 400
        def json(self):
            return {"s": "error", "code": -371, "message": "refresh_token expired"}

    monkeypatch.setattr(
        "ndmp_core.src.fyers_token_refresh.requests.post",
        lambda *a, **k: _FakeResponse(),
    )

    with pytest.raises(FyersTokenRefreshError, match="15-day limit"):
        refresh_access_token(env)


def test_refresh_network_error(monkeypatch):
    import requests

    key = Fernet.generate_key()
    fernet = Fernet(key)
    env = {
        "FYERS_CLIENT_ID": "ABC123-100",
        "FYERS_TOKEN_ENC_KEY": key.decode(),
        "FYERS_SECRET_KEY": fernet.encrypt(b"my-secret").decode(),
        "FYERS_REFRESH_TOKEN_ENCRYPTED": fernet.encrypt(b"my-refresh-token").decode(),
        "FYERS_PIN_ENCRYPTED": fernet.encrypt(b"1234").decode(),
    }

    def _raise(*a, **k):
        raise requests.exceptions.ConnectionError("boom")

    monkeypatch.setattr("ndmp_core.src.fyers_token_refresh.requests.post", _raise)

    with pytest.raises(FyersTokenRefreshError, match="Network error"):
        refresh_access_token(env)


# ---------------------------------------------------------------------------
# write_new_access_token
# ---------------------------------------------------------------------------

def test_write_new_access_token_replaces_line_only(tmp_path):
    key = Fernet.generate_key()
    fernet = Fernet(key)
    env_path = tmp_path / "fyers.env"
    env_path.write_text(
        "FYERS_CLIENT_ID=ABC123-100\n"
        f"FYERS_ACCESS_TOKEN_ENCRYPTED={fernet.encrypt(b'old-token').decode()}\n"
        "FYERS_TOKEN_ENC_KEY=" + key.decode() + "\n"
    )

    write_new_access_token(str(env_path), fernet, "new-token-value")

    lines = env_path.read_text().splitlines()
    assert lines[0] == "FYERS_CLIENT_ID=ABC123-100"
    assert lines[2] == f"FYERS_TOKEN_ENC_KEY={key.decode()}"
    new_encrypted_line = [l for l in lines if l.startswith("FYERS_ACCESS_TOKEN_ENCRYPTED=")][0]
    encrypted_value = new_encrypted_line.split("=", 1)[1]
    assert fernet.decrypt(encrypted_value.encode()).decode() == "new-token-value"


def test_write_new_access_token_missing_line_raises(tmp_path):
    key = Fernet.generate_key()
    fernet = Fernet(key)
    env_path = tmp_path / "fyers.env"
    env_path.write_text("FYERS_CLIENT_ID=ABC123-100\n")

    with pytest.raises(FyersAuthError, match="not found"):
        write_new_access_token(str(env_path), fernet, "new-token-value")


def test_write_new_access_token_preserves_permissions(tmp_path):
    key = Fernet.generate_key()
    fernet = Fernet(key)
    env_path = tmp_path / "fyers.env"
    env_path.write_text(
        f"FYERS_ACCESS_TOKEN_ENCRYPTED={fernet.encrypt(b'old').decode()}\n"
    )
    os.chmod(env_path, 0o600)

    write_new_access_token(str(env_path), fernet, "new-token")

    mode = oct(os.stat(env_path).st_mode)[-3:]
    assert mode == "600"


# ---------------------------------------------------------------------------
# check_poller_health
# ---------------------------------------------------------------------------

def test_health_check_market_closed_is_healthy(tmp_path):
    calendar = NSETradingCalendar(holidays=set())
    sunday_ist = datetime(2026, 7, 26, 12, 0)  # a Sunday
    alerts = []

    healthy = check_poller_health(
        str(tmp_path), sunday_ist, calendar, alert_fn=alerts.append
    )

    assert healthy is True
    assert alerts == []


def test_health_check_no_snapshots_during_market_hours_alerts(tmp_path):
    calendar = NSETradingCalendar(holidays=set())
    tuesday_market_hours = datetime(2026, 7, 21, 11, 0)  # a Tuesday, 11:00
    alerts = []

    healthy = check_poller_health(
        str(tmp_path), tuesday_market_hours, calendar, alert_fn=alerts.append
    )

    assert healthy is False
    assert len(alerts) == 1
    assert "No parquet snapshots found" in alerts[0]


def test_health_check_stale_snapshot_alerts(tmp_path):
    calendar = NSETradingCalendar(holidays=set())
    stale_file = tmp_path / "NSE:NIFTY26JULFUT.parquet"
    stale_file.write_bytes(b"fake parquet bytes")
    old_time = time_module.time() - 3600  # 1 hour old
    os.utime(stale_file, (old_time, old_time))

    tuesday_market_hours = datetime(2026, 7, 21, 11, 0)
    alerts = []

    healthy = check_poller_health(
        str(tmp_path),
        tuesday_market_hours,
        calendar,
        stale_threshold_seconds=600,
        alert_fn=alerts.append,
    )

    assert healthy is False
    assert "old" in alerts[0]


def test_health_check_fresh_snapshot_is_healthy(tmp_path):
    calendar = NSETradingCalendar(holidays=set())
    fresh_file = tmp_path / "NSE:NIFTY26JULFUT.parquet"
    fresh_file.write_bytes(b"fake parquet bytes")

    tuesday_market_hours = datetime(2026, 7, 21, 11, 0)
    alerts = []

    healthy = check_poller_health(
        str(tmp_path),
        tuesday_market_hours,
        calendar,
        stale_threshold_seconds=600,
        alert_fn=alerts.append,
    )

    assert healthy is True
    assert alerts == []


def test_most_recent_mtime_empty_dir(tmp_path):
    assert most_recent_mtime(str(tmp_path)) is None
