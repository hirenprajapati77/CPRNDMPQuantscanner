import os
from cryptography.fernet import Fernet

with open('/etc/fyers-oi-poller.env', 'r') as f:
    env_content = f.read()

# Extract FYERS_TOKEN_ENC_KEY
enc_key = None
for line in env_content.splitlines():
    if line.startswith('FYERS_TOKEN_ENC_KEY='):
        enc_key = line.split('=', 1)[1].strip('"')
        break

if not enc_key:
    print('Error: FYERS_TOKEN_ENC_KEY not found in env file')
    exit(1)

f = Fernet(enc_key.encode())

secret_key = '9XUXQH7KVY'
refresh_token = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhdWQiOlsiZDoxIiwiZDoyIiwieDowIiwieDoxIl0sImF0X2hhc2giOiJnQUFBQUFCcVpHV2FHUGg0RU5mSk1jWVR0aHpmYlRhU1cybUltZlJTZWRjYXotUi1XenhuTGpja0d0OWtWN2ZFRnRXZXZfaEJjNVoxX19kV1lSMkR2NVJ0dGE5TGZ5cEVtekZ2cUJNTkZCOVVCMGpPd3BEdzZ4Yz0iLCJkaXNwbGF5X25hbWUiOiIiLCJvbXMiOiJLMSIsImhzbV9rZXkiOiJmZDRmODMyZjVhZDFiNTQ4NzhiNjBiNWQ5NDEwYjYxYzQ1YThkN2MwYWQ3NGJhMzZmNzFhMTI2MSIsImlzRGRwaUVuYWJsZWQiOiJOIiwiaXNNdGZFbmFibGVkIjoiTiIsImZ5X2lkIjoiWFAwODMxOCIsImFwcFR5cGUiOjEwMCwiZXhwIjoxNzg2MjM1NDAwLCJpYXQiOjE3ODQ5NjQ1MDYsImlzcyI6ImFwaS5meWVycy5pbiIsIm5iZiI6MTc4NDk2NDUwNiwic3ViIjoicmVmcmVzaF90b2tlbiJ9.BsLTjtgrCGFqaIjOVC76r1b-cBOIQ09jzjhSmE6bfU0'

encrypted_secret = f.encrypt(secret_key.encode()).decode()
encrypted_refresh = f.encrypt(refresh_token.encode()).decode()

print('FYERS_SECRET_KEY="' + encrypted_secret + '"')
print('FYERS_REFRESH_TOKEN_ENCRYPTED="' + encrypted_refresh + '"')
