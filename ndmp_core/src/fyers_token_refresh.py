"""
NDMP OS v6.0 - Fyers Daily Access-Token Refresh

STATUS AS OF APRIL 2026: NON-FUNCTIONAL. Fyers disabled the refresh_token API
entirely to comply with SEBI's new algo-trading framework (daily 2FA required,
continuous refresh-token sessions no longer permitted). This code is left in
place in case that policy changes, but is not currently wired into any
systemd timer. Daily token rotation is done manually — see the operator
runbook for the interactive login steps. Do not re-enable
fyers-token-refresh.timer without first confirming Fyers has restored this
endpoint.

Fyers access tokens expire every 24h, but the refresh_token issued alongside
them is valid for 15 days and can mint a fresh access_token without repeating
the full interactive OAuth login (no TOTP secret needs to be stored). This
script performs that daily exchange and rewrites the encrypted access token
in place, so FyersTokenManager and the OI poller keep working unattended.

HARD LIMIT: the refresh_token itself expires after 15 days and Fyers provides
no way to renew it programmatically — someone must redo the interactive login
by hand before then, or this script starts failing with FyersTokenRefreshError
and the poller resumes its (now-alerting) crash loop. Put a calendar reminder
on this; do not assume it can be fully unattended forever.

VERIFY BEFORE TRUSTING IN PRODUCTION: the appIdHash construction below
(sha256 of "{client_id}:{secret_key}") and the validate-refresh-token request
shape were built from published Fyers docs/community reports, not tested
against a live account. Confirm both against current Fyers API docs on first
real run.
"""

import os
import hashlib
import tempfile

import requests
from cryptography.fernet import Fernet, InvalidToken

from ndmp_core.src.exceptions import FyersAuthError, FyersTokenRefreshError

FYERS_REFRESH_URL = "https://api-t1.fyers.in/api/v3/validate-refresh-token"


def _decrypt(fernet: Fernet, encrypted_value: str, label: str) -> str:
    try:
        return fernet.decrypt(encrypted_value.encode()).decode()
    except InvalidToken as e:
        raise FyersAuthError(f"Failed to decrypt {label}: key/value mismatch.") from e


def refresh_access_token(env: dict) -> str:
    """Exchange a stored refresh_token + PIN for a fresh access_token.

    `env` is a plain dict (normally os.environ) containing:
      FYERS_CLIENT_ID, FYERS_SECRET_KEY, FYERS_TOKEN_ENC_KEY,
      FYERS_REFRESH_TOKEN_ENCRYPTED, FYERS_PIN_ENCRYPTED

    Returns the new plaintext access_token. Raises FyersTokenRefreshError on
    any failure — this must never fail silently, since it runs unattended.
    """
    required = [
        "FYERS_CLIENT_ID",
        "FYERS_SECRET_KEY",
        "FYERS_TOKEN_ENC_KEY",
        "FYERS_REFRESH_TOKEN_ENCRYPTED",
        "FYERS_PIN_ENCRYPTED",
    ]
    missing = [k for k in required if not env.get(k)]
    if missing:
        raise FyersAuthError(f"Missing required env var(s): {', '.join(missing)}")

    fernet = Fernet(env["FYERS_TOKEN_ENC_KEY"].encode())
    client_id = env["FYERS_CLIENT_ID"]
    secret_key = _decrypt(fernet, env["FYERS_SECRET_KEY"], "FYERS_SECRET_KEY")
    refresh_token = _decrypt(fernet, env["FYERS_REFRESH_TOKEN_ENCRYPTED"], "refresh_token")
    pin = _decrypt(fernet, env["FYERS_PIN_ENCRYPTED"], "pin")

    app_id_hash = hashlib.sha256(f"{client_id}:{secret_key}".encode()).hexdigest()

    try:
        resp = requests.post(
            FYERS_REFRESH_URL,
            headers={"Content-Type": "application/json; charset=utf-8"},
            json={
                "grant_type": "refresh_token",
                "appIdHash": app_id_hash,
                "refresh_token": refresh_token,
                "pin": pin,
            },
            timeout=15,
        )
    except requests.RequestException as e:
        raise FyersTokenRefreshError(f"Network error calling Fyers refresh endpoint: {e}") from e

    try:
        payload = resp.json()
    except ValueError as e:
        raise FyersTokenRefreshError(
            f"Fyers refresh endpoint returned non-JSON response (HTTP {resp.status_code})"
        ) from e

    if payload.get("s") != "ok" or "access_token" not in payload:
        raise FyersTokenRefreshError(
            f"Fyers refresh_token exchange failed: {payload}. "
            f"If this mentions the refresh_token being invalid/expired, it has hit "
            f"its 15-day limit — redo the interactive login manually to get a new one."
        )

    return payload["access_token"]


def write_new_access_token(env_file_path: str, fernet: Fernet, new_access_token: str) -> None:
    """Rewrite FYERS_ACCESS_TOKEN_ENCRYPTED in the env file in place, atomically,
    leaving every other line untouched. Fails loudly if the expected line isn't found."""
    encrypted = fernet.encrypt(new_access_token.encode()).decode()

    with open(env_file_path, "r") as f:
        lines = f.readlines()

    found = False
    new_lines = []
    for line in lines:
        if line.startswith("FYERS_ACCESS_TOKEN_ENCRYPTED="):
            new_lines.append(f"FYERS_ACCESS_TOKEN_ENCRYPTED={encrypted}\n")
            found = True
        else:
            new_lines.append(line)

    if not found:
        raise FyersAuthError(
            f"FYERS_ACCESS_TOKEN_ENCRYPTED not found in {env_file_path} — refusing to "
            f"append a new line blindly. Check the env file format."
        )

    dir_name = os.path.dirname(env_file_path) or "."
    fd, tmp_path = tempfile.mkstemp(dir=dir_name)
    try:
        with os.fdopen(fd, "w") as f:
            f.writelines(new_lines)
        os.chmod(tmp_path, 0o600)
        os.replace(tmp_path, env_file_path)  # atomic on same filesystem
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def main():
    env_file_path = os.environ.get("FYERS_ENV_FILE_PATH", "/etc/fyers-oi-poller.env")
    new_token = refresh_access_token(os.environ)
    fernet = Fernet(os.environ["FYERS_TOKEN_ENC_KEY"].encode())
    write_new_access_token(env_file_path, fernet, new_token)
    print("[FYERS TOKEN REFRESH] access_token rotated successfully.", flush=True)


if __name__ == "__main__":
    main()
