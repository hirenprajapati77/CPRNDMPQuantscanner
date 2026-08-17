import os
import sys
sys.path.append("/home/ubuntu/.local/lib/python3.10/site-packages")

# Load environment file manually
env_file = "/etc/fyers-oi-poller.env"
with open(env_file, "r") as f:
    for line in f:
        if "=" in line:
            k, v = line.split("=", 1)
            os.environ[k.strip()] = v.strip().strip('"').strip("'")

from fyers_apiv3 import fyersModel
from ndmp_core.src.fyers_auth import FyersTokenManager

token_mgr = FyersTokenManager()
access_token = token_mgr.get_access_token()
client_id = os.environ.get("FYERS_CLIENT_ID")

fyers = fyersModel.FyersModel(client_id=client_id, is_async=False, token=access_token, log_path="/tmp")
symbols = ["NSE:BEL26AUGFUT", "NSE:TRENT26AUGFUT", "NSE:DIXON26AUGFUT"]
data = {"symbols": ",".join(symbols)}
res = fyers.quotes(data=data)
print(res)
