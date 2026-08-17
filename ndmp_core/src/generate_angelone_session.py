"""
NDMP OS v6.0 - Angel One Daily Session Generator

Run this BY HAND each trading morning before 9:15 AM IST. Per project
decision, NDMP OS does not automate Angel One's daily 2FA login (that would
require storing a TOTP secret, which is materially more sensitive than a
token — it effectively bypasses your second factor). You enter the current
TOTP code from your authenticator app each time; nothing about the TOTP
itself is ever stored.

What IS stored (encrypted, in the same env file the poller reads): the
resulting access_token, so the poller can run unattended for the rest of
the day using this morning's session.

Usage:
    python3 -m ndmp_core.src.generate_angelone_session
    (prompts for MPIN and today's TOTP code interactively)
"""

import os
import getpass

from cryptography.fernet import Fernet

from ndmp_core.src.exceptions import AngelOneAuthError


def generate_session(client_code: str, mpin: str, totp: str):
    try:
        from SmartApi import SmartConnect
    except ImportError as e:
        raise AngelOneAuthError(
            "smartapi-python is not installed. Add it to pyproject.toml dependencies."
        ) from e

    api_key = os.environ.get("ANGELONE_API_KEY")
    if not api_key:
        raise AngelOneAuthError("Missing required env var: ANGELONE_API_KEY")

    # Fetch public IP dynamically to bypass SmartAPI's hardcoded 'finally' block IP bug
    import requests
    try:
        public_ip = requests.get("https://api.ipify.org", timeout=5).text.strip()
    except Exception:
        public_ip = "127.0.0.1"

    client = SmartConnect(api_key=api_key)
    
    # Instance-Level override
    client.clientPublicIp = public_ip
    client.clientPublicIP = public_ip

    session = client.generateSession(client_code, mpin, totp)

    if not isinstance(session, dict) or not session.get("status"):
        raise AngelOneAuthError(f"Angel One generateSession() failed: {session}")

    access_token = session.get("data", {}).get("jwtToken")
    if not access_token:
        raise AngelOneAuthError(
            f"Angel One generateSession() succeeded but response had no jwtToken: {session}"
        )

    # Clean prefix "Bearer " since the API client's setAccessToken adds it manually
    if access_token.startswith("Bearer "):
        access_token = access_token.replace("Bearer ", "").strip()

    return access_token



def write_access_token(env_file_path: str, fernet: Fernet, access_token: str) -> None:
    """Same atomic replace-one-line pattern as the Fyers refresh script."""
    encrypted = fernet.encrypt(access_token.encode()).decode()

    with open(env_file_path, "r") as f:
        lines = f.readlines()

    found = False
    new_lines = []
    for line in lines:
        if line.startswith("ANGELONE_ACCESS_TOKEN_ENCRYPTED="):
            new_lines.append(f"ANGELONE_ACCESS_TOKEN_ENCRYPTED={encrypted}\n")
            found = True
        else:
            new_lines.append(line)

    if not found:
        new_lines.append(f"ANGELONE_ACCESS_TOKEN_ENCRYPTED={encrypted}\n")

    import tempfile
    dir_name = os.path.dirname(env_file_path) or "."
    fd, tmp_path = tempfile.mkstemp(dir=dir_name)
    try:
        with os.fdopen(fd, "w") as f:
            f.writelines(new_lines)
        os.chmod(tmp_path, 0o600)
        os.replace(tmp_path, env_file_path)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def main():
    env_file_path = os.environ.get("ANGELONE_ENV_FILE_PATH", "/etc/angelone-oi-poller.env")
    client_code = os.environ.get("ANGELONE_CLIENT_CODE")
    enc_key = os.environ.get("ANGELONE_TOKEN_ENC_KEY")
    if not client_code:
        raise AngelOneAuthError("Missing required env var: ANGELONE_CLIENT_CODE")
    if not enc_key:
        raise AngelOneAuthError("Missing required env var: ANGELONE_TOKEN_ENC_KEY")

    mpin = getpass.getpass("Angel One MPIN: ")
    totp = input("Today's TOTP code (from your authenticator app): ").strip()

    access_token = generate_session(client_code, mpin, totp)
    fernet = Fernet(enc_key.encode())
    write_access_token(env_file_path, fernet, access_token)
    print("[ANGEL ONE SESSION] access_token generated and stored successfully.", flush=True)


if __name__ == "__main__":
    main()
