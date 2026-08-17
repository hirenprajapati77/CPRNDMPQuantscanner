import os

env_path = "/etc/angelone-oi-poller.env"
content = """ANGELONE_CLIENT_CODE="YOUR_CLIENT_CODE_HERE"
ANGELONE_API_KEY="PkyX6yKG"
ANGELONE_TOKEN_ENC_KEY="pxsSkeQLMg809_RoWmfaLKuknG5Y2fU_irS2VCP79Rk="
ANGELONE_ACCESS_TOKEN_ENCRYPTED=""
"""

with open(env_path, "w") as f:
    f.write(content)

os.chmod(env_path, 0o600)
os.system(f"chown ubuntu:ubuntu {env_path}")
print("Created /etc/angelone-oi-poller.env successfully.")
