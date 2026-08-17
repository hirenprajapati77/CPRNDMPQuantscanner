"""
NDMP OS v6.0 - Angel One Session Token Manager

Angel One SmartAPI sessions expire daily at midnight IST and require a fresh
TOTP-based login — this is a SEBI-wide requirement (the same "Safer
Participation of Retail Users in Algorithmic Trading" framework that killed
Fyers' refresh_token API), not something specific to Angel One. Per project
decision, NDMP OS does this login manually each morning rather than storing
a TOTP secret for automated login.

SCOPE NOTE: This class only *consumes* an already-generated access_token. It
does not perform the generateSession() login call itself — that happens in
the separate generate_angelone_session.py script, run by hand each trading
morning before market open.
"""

import os
from cryptography.fernet import Fernet, InvalidToken

from ndmp_core.src.exceptions import AngelOneAuthError


class AngelOneSessionManager:
    """Decrypts an Angel One access_token from environment variables.

    Expects two env vars (populated by generate_angelone_session.py, run
    manually each morning):
      - ANGELONE_TOKEN_ENC_KEY: a Fernet key (base64-encoded, 32 bytes)
      - ANGELONE_ACCESS_TOKEN_ENCRYPTED: the access_token, encrypted with that key
    """

    def __init__(
        self,
        enc_key_env: str = "ANGELONE_TOKEN_ENC_KEY",
        token_env: str = "ANGELONE_ACCESS_TOKEN_ENCRYPTED",
    ):
        self._enc_key_env = enc_key_env
        self._token_env = token_env

    def get_access_token(self) -> str:
        """Return the decrypted, plaintext Angel One access_token."""
        enc_key = os.environ.get(self._enc_key_env)
        encrypted_token = os.environ.get(self._token_env)

        if not enc_key:
            raise AngelOneAuthError(f"Missing required env var: {self._enc_key_env}")
        if not encrypted_token:
            raise AngelOneAuthError(f"Missing required env var: {self._token_env}")

        try:
            fernet = Fernet(enc_key.encode())
            return fernet.decrypt(encrypted_token.encode()).decode()
        except InvalidToken as e:
            raise AngelOneAuthError(
                "Failed to decrypt Angel One access_token: key/value mismatch, or "
                "yesterday's session has expired and today's login hasn't been done yet."
            ) from e
        except Exception as e:
            raise AngelOneAuthError(f"Unexpected error decrypting Angel One access_token: {e}") from e
