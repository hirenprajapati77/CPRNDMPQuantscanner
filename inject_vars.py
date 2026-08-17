import os
import sys
from cryptography.fernet import Fernet

def main():
    env_file = '/etc/fyers-oi-poller.env'
    try:
        with open(env_file, 'r') as f:
            env_content = f.read()
    except Exception as e:
        print(f"Error reading {env_file}: {e}")
        sys.exit(1)

    enc_key = None
    for line in env_content.splitlines():
        if line.startswith('FYERS_TOKEN_ENC_KEY='):
            enc_key = line.split('=', 1)[1].strip('"')
            break

    if not enc_key:
        print('Error: FYERS_TOKEN_ENC_KEY not found in env file')
        sys.exit(1)

    fernet = Fernet(enc_key.encode())

    secret_key = '9XUXQH7KVY'
    refresh_token = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhdWQiOlsiZDoxIiwiZDoyIiwieDowIiwieDoxIl0sImF0X2hhc2giOiJnQUFBQUFCcVpHV2FHUGg0RU5mSk1jWVR0aHpmYlRhU1cybUltZlJTZWRjYXotUi1XenhuTGpja0d0OWtWN2ZFRnRXZXZfaEJjNVoxX19kV1lSMkR2NVJ0dGE5TGZ5cEVtekZ2cUJNTkZCOVVCMGpPd3BEdzZ4Yz0iLCJkaXNwbGF5X25hbWUiOiIiLCJvbXMiOiJLMSIsImhzbV9rZXkiOiJmZDRmODMyZjVhZDFiNTQ4NzhiNjBiNWQ5NDEwYjYxYzQ1YThkN2MwYWQ3NGJhMzZmNzFhMTI2MSIsImlzRGRwaUVuYWJsZWQiOiJOIiwiaXNNdGZFbmFibGVkIjoiTiIsImZ5X2lkIjoiWFAwODMxOCIsImFwcFR5cGUiOjEwMCwiZXhwIjoxNzg2MjM1NDAwLCJpYXQiOjE3ODQ5NjQ1MDYsImlzcyI6ImFwaS5meWVycy5pbiIsIm5iZiI6MTc4NDk2NDUwNiwic3ViIjoicmVmcmVzaF90b2tlbiJ9.BsLTjtgrCGFqaIjOVC76r1b-cBOIQ09jzjhSmE6bfU0'
    pin = '4589'

    enc_secret = fernet.encrypt(secret_key.encode()).decode()
    enc_refresh = fernet.encrypt(refresh_token.encode()).decode()
    enc_pin = fernet.encrypt(pin.encode()).decode()

    # Append to env file
    with open(env_file, 'a') as f:
        f.write(f'\nFYERS_SECRET_KEY="{enc_secret}"\n')
        f.write(f'FYERS_REFRESH_TOKEN_ENCRYPTED="{enc_refresh}"\n')
        f.write(f'FYERS_PIN_ENCRYPTED="{enc_pin}"\n')

    print("Successfully injected all three variables into /etc/fyers-oi-poller.env")

if __name__ == "__main__":
    main()
