import os
import sys
from cryptography.fernet import Fernet
sys.path.append("/home/ubuntu/.local/lib/python3.10/site-packages")

from SmartApi import SmartConnect

# 1. Apply Class-Level overrides to the SmartConnect class
SmartConnect.clientPublicIp = "140.245.219.29"
SmartConnect.clientPublicIP = "140.245.219.29"

client_code = "P67975"
mpin = "2389"
totp = "929800"
api_key = "PkyX6yKG"

print(f"Generating session for {client_code} with class-level IP patches...")
client = SmartConnect(api_key=api_key)

# 2. Apply Instance-Level overrides to the instance
client.clientPublicIp = "140.245.219.29"
client.clientPublicIP = "140.245.219.29"

session = client.generateSession(client_code, mpin, totp)
print("Session response:", session)

if not session.get("status"):
    print("Login Failed")
    sys.exit(1)

raw_token = session.get("data", {}).get("jwtToken")
# Strip Bearer if present
clean_token = raw_token.replace("Bearer ", "").strip()
client.setAccessToken(clean_token)

# Write the new cleaned token to the env file
env_file_path = "/etc/angelone-oi-poller.env"
with open(env_file_path, "r") as f:
    lines = f.readlines()
    
enc_key = None
for line in lines:
    if line.startswith("ANGELONE_TOKEN_ENC_KEY="):
        enc_key = line.split("=", 1)[1].strip().strip('"').strip("'")
        break

if enc_key:
    fernet = Fernet(enc_key.encode())
    encrypted = fernet.encrypt(clean_token.encode()).decode()
    
    # Replace access token line
    new_lines = []
    for line in lines:
        if line.startswith("ANGELONE_ACCESS_TOKEN_ENCRYPTED="):
            new_lines.append(f'ANGELONE_ACCESS_TOKEN_ENCRYPTED="{encrypted}"\n')
        else:
            new_lines.append(line)
            
    with open(env_file_path, "w") as f:
        f.writelines(new_lines)
    print("Cleaned token encrypted and written to env file successfully.")

# 3. Test market data query
symbols = ["58130", "58405", "58161"] # NFO tokens for BEL, TRENT, DIXON
print("Fetching market data...")
resp = client.getMarketData(mode="FULL", exchangeTokens={"NFO": symbols})
print("Market Data Response:")
print(resp)
