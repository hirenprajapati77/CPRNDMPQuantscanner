import os
import sys
from cryptography.fernet import Fernet
sys.path.append("/home/ubuntu/.local/lib/python3.10/site-packages")

from ndmp_core.src.generate_angelone_session import generate_session, write_access_token

def main():
    if len(sys.argv) < 4:
        print("Usage: python3 do_angelone_login.py <client_code> <mpin> <totp>")
        sys.exit(1)
        
    client_code = sys.argv[1]
    mpin = sys.argv[2]
    totp = sys.argv[3]
    
    env_file_path = "/etc/angelone-oi-poller.env"
    
    # Read env file to get enc_key
    with open(env_file_path, "r") as f:
        lines = f.readlines()
        
    enc_key = None
    for line in lines:
        if line.startswith("ANGELONE_TOKEN_ENC_KEY="):
            enc_key = line.split("=", 1)[1].strip().strip('"').strip("'")
            break
            
    if not enc_key:
        print("Error: ANGELONE_TOKEN_ENC_KEY not found in env file")
        sys.exit(1)
        
    os.environ["ANGELONE_CLIENT_CODE"] = client_code
    os.environ["ANGELONE_API_KEY"] = "PkyX6yKG"
    
    print(f"Generating session for {client_code}...")
    try:
        access_token = generate_session(client_code, mpin, totp)
        fernet = Fernet(enc_key.encode())
        write_access_token(env_file_path, fernet, access_token)
        print("SUCCESS")
    except Exception as e:
        print(f"FAILED: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
