"""
NDMP OS v6.0 - Fyers Token Manager

Loads and decrypts a Fyers access token for NDMP OS's own read-only market-data
calls. This is intentionally separate from CPR Pro's existing Fyers auth/token
infrastructure (per project decision to keep the two platforms' credentials
independent).

SCOPE NOTE: This class does NOT implement the Fyers OAuth login flow
(client_id + secret_key + redirect_uri + TOTP -> access token). It only
consumes an already-valid, already-encrypted token supplied via environment
variables. Generating and refreshing that token daily is a separate, explicit
follow-up task — do not assume it's covered here.
"""

import os
from cryptography.fernet import Fernet, InvalidToken

from ndmp_core.src.exceptions import FyersAuthError


class FyersTokenManager:
    """Decrypts a Fyers access token from environment variables.

    Expects two env vars (populated by a separate, manual or scheduled
    token-generation step outside this class):
      - FYERS_TOKEN_ENC_KEY: a Fernet key (base64-encoded, 32 bytes)
      - FYERS_ACCESS_TOKEN_ENCRYPTED: the access token, encrypted with that key
    """

    def __init__(
        self,
        enc_key_env: str = "FYERS_TOKEN_ENC_KEY",
        token_env: str = "FYERS_ACCESS_TOKEN_ENCRYPTED",
    ):
        self._enc_key_env = enc_key_env
        self._token_env = token_env

    def get_access_token(self) -> str:
        """Return the decrypted, plaintext Fyers access token."""
        enc_key = os.environ.get(self._enc_key_env)
        encrypted_token = os.environ.get(self._token_env)

        if not enc_key:
            raise FyersAuthError(f"Missing required env var: {self._enc_key_env}")
        if not encrypted_token:
            raise FyersAuthError(f"Missing required env var: {self._token_env}")

        try:
            fernet = Fernet(enc_key.encode())
            return fernet.decrypt(encrypted_token.encode()).decode()
        except InvalidToken as e:
            raise FyersAuthError(
                "Failed to decrypt Fyers access token: the encryption key and "
                "encrypted token do not match (wrong key, or token expired/rotated "
                "and re-encrypted with a different key)."
            ) from e
        except Exception as e:
            raise FyersAuthError(f"Unexpected error decrypting Fyers access token: {e}") from e
