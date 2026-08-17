import os
import sys
import hashlib
import tempfile
import requests
from cryptography.fernet import Fernet

def main():
    env_file = "/etc/fyers-oi-poller.env"
    try:
        with open(env_file, "r") as f:
            lines = f.readlines()
    except Exception as e:
        print(f"Error reading {env_file}: {e}")
        sys.exit(1)

    # Extract required vars
    env_vars = {}
    for line in lines:
        if "=" in line:
            k, v = line.split("=", 1)
            env_vars[k.strip()] = v.strip().strip('"').strip("'")

    client_id = env_vars.get("FYERS_CLIENT_ID")
    enc_key = env_vars.get("FYERS_TOKEN_ENC_KEY")
    enc_secret = env_vars.get("FYERS_SECRET_KEY")

    if not all([client_id, enc_key, enc_secret]):
        print("Missing FYERS_CLIENT_ID, FYERS_TOKEN_ENC_KEY, or FYERS_SECRET_KEY in env file.")
        sys.exit(1)

    fernet = Fernet(enc_key.encode())
    try:
        secret_key = fernet.decrypt(enc_secret.encode()).decode()
    except Exception as e:
        print(f"Failed to decrypt secret key: {e}")
        sys.exit(1)

    # 1. Provide the URL
    redirect_uri = "https://trade.fyers.in/api-login/redirect-uri/index.html"
    auth_url = f"https://api-t1.fyers.in/api/v3/generate-authcode?client_id={client_id}&redirect_uri={redirect_uri}&response_type=code&state=daily_login"
    
    print("\n" + "="*60)
    print("FYERS DAILY LOGIN SCRIPT")
    print("="*60)
    print("1. Click this link to log in and authorize the app:")
    print(f"\n{auth_url}\n")
    print("2. After you log in, you will be redirected to a blank page.")
    print("3. Look at the URL in your browser's address bar.")
    print("   It will look like: .../?auth_code=YOUR_AUTH_CODE&state=daily_login")
    
    # 2. Get auth code from user
    auth_code_input = input("\nPaste the YOUR_AUTH_CODE here (or the full URL): ").strip()
    
    if not auth_code_input:
        print("No auth code provided. Exiting.")
        sys.exit(1)
        
    # Extract just the code if they pasted the full URL
    if "auth_code=" in auth_code_input:
        try:
            auth_code = auth_code_input.split("auth_code=")[1].split("&")[0]
        except IndexError:
            auth_code = auth_code_input
    else:
        auth_code = auth_code_input

    # 3. Exchange auth code for access token
    print("\nExchanging auth_code for access_token...")
    app_id_hash = hashlib.sha256(f"{client_id}:{secret_key}".encode()).hexdigest()

    resp = requests.post(
        "https://api-t1.fyers.in/api/v3/validate-authcode",
        headers={"Content-Type": "application/json"},
        json={
            "grant_type": "authorization_code",
            "appIdHash": app_id_hash,
            "code": auth_code
        }
    )
    
    try:
        data = resp.json()
    except Exception:
        print(f"Failed to parse response: {resp.text}")
        sys.exit(1)

    if data.get("s") != "ok" or "access_token" not in data:
        print(f"Failed to get token: {data}")
        sys.exit(1)

    access_token = data["access_token"]
    print("Successfully retrieved new access_token!")

    # 4. Encrypt and save
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

    # Atomic write
    fd, tmp_path = tempfile.mkstemp(dir="/etc")
    try:
        with os.fdopen(fd, "w") as f:
            f.writelines(new_lines)
        os.chmod(tmp_path, 0o600)
        os.replace(tmp_path, env_file)
    except PermissionError:
        print("\nERROR: You must run this script with sudo to update /etc/fyers-oi-poller.env!")
        os.remove(tmp_path)
        sys.exit(1)
    except Exception as e:
        print(f"\nERROR saving file: {e}")
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        sys.exit(1)

    print("\nSuccess! /etc/fyers-oi-poller.env has been updated with the new token.")
    print("Restarting the poller service...")
    os.system("systemctl restart fyers-oi-poller.service")
    print("Done! Poller is ready for the day.")

if __name__ == "__main__":
    main()
