import os
import sys
import hashlib
import tempfile
import requests
from cryptography.fernet import Fernet

env_file = "/etc/fyers-oi-poller.env"
auth_code = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhcHBfaWQiOiJGOUNCTjVERk5DIiwidXVpZCI6IjA3MzUyMDc1NmRiZTQzYmY4NGY4ZWQ4ZDE3MTc4MzgwIiwiaXBBZGRyIjoiIiwibm9uY2UiOiIiLCJzY29wZSI6IiIsImRpc3BsYXlfbmFtZSI6IlhQMDgzMTgiLCJvbXMiOiJLMSIsImhzbV9rZXkiOiJhZjNjZjQ0M2M3MjVjNDBkYmRmMTIxMTYwMTYxZTgzMzc2ZTJlMTkyNzFmMTY5ZjUyOTc4YmYyYiIsImlzRGRwaUVuYWJsZWQiOiJOIiwiaXNNdGZFbmFibGVkIjoiTiIsImF1ZCI6IltcImQ6MVwiLFwiZDoyXCIsXCJ4OjBcIixcIng6MVwiXSIsImV4cCI6MTc4NTI0NzY1MywiaWF0IjoxNzg1MjE3NjUzLCJpc3MiOiJhcGkubG9naW4uZnllcnMuaW4iLCJuYmYiOjE3ODUyMTc2NTMsInN1YiI6ImF1dGhfY29kZSJ9.4KySQNnlO4TxtMa_aQRogttd-aGAlVblaSjg6SbnXQM"

with open(env_file, "r") as f:
    lines = f.readlines()

env_vars = {}
for line in lines:
    if "=" in line:
        k, v = line.split("=", 1)
        env_vars[k.strip()] = v.strip().strip('"').strip("'")

client_id = env_vars["FYERS_CLIENT_ID"]
enc_key = env_vars["FYERS_TOKEN_ENC_KEY"]
enc_secret = env_vars["FYERS_SECRET_KEY"]

fernet = Fernet(enc_key.encode())
secret_key = fernet.decrypt(enc_secret.encode()).decode()

app_id_hash = hashlib.sha256(f"{client_id}:{secret_key}".encode()).hexdigest()

resp = requests.post(
    "https://api-t1.fyers.in/api/v3/validate-authcode",
    headers={"Content-Type": "application/json"},
    json={"grant_type": "authorization_code", "appIdHash": app_id_hash, "code": auth_code}
)
data = resp.json()
print("API response:", data)

if data.get("s") != "ok" or "access_token" not in data:
    print("FAILED to get access token")
    sys.exit(1)

access_token = data["access_token"]
encrypted_token = fernet.encrypt(access_token.encode()).decode()

new_lines = []
found = False
for line in lines:
    if line.startswith("FYERS_ACCESS_TOKEN_ENCRYPTED="):
        new_lines.append(f'FYERS_ACCESS_TOKEN_ENCRYPTED="{encrypted_token}"\n')
        found = True
    else:
        new_lines.append(line)

if not found:
    new_lines.append(f'FYERS_ACCESS_TOKEN_ENCRYPTED="{encrypted_token}"\n')

fd, tmp_path = tempfile.mkstemp(dir="/etc")
with os.fdopen(fd, "w") as f:
    f.writelines(new_lines)
os.chmod(tmp_path, 0o600)
os.replace(tmp_path, env_file)

print("Token updated successfully. Restarting poller...")
os.system("systemctl restart fyers-oi-poller.service")
print("Done.")
