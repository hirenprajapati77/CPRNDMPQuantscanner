import os

poller_service = """[Unit]
Description=Angel One Live Open Interest Snapshot Poller
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/CPRNDMPQuantscanner
Environment=PYTHONPATH=/home/ubuntu/CPRNDMPQuantscanner
EnvironmentFile=/etc/angelone-oi-poller.env
ExecStart=/usr/bin/python3 run_angelone_oi_poller.py
Restart=on-failure
RestartSec=30

[Install]
WantedBy=multi-user.target
"""

hc_service = """[Unit]
Description=Angel One OI Poller Health Check
After=network.target

[Service]
Type=oneshot
User=ubuntu
WorkingDirectory=/home/ubuntu/CPRNDMPQuantscanner
Environment=PYTHONPATH=/home/ubuntu/CPRNDMPQuantscanner
Environment=FYERS_OI_DATA_DIR=data/oi_history_angelone
ExecStart=/usr/bin/python3 -m ndmp_core.src.fyers_oi_health_check
"""

hc_timer = """[Unit]
Description=Check Angel One OI poller health every 15 min during market hours

[Timer]
OnBootSec=10min
OnUnitActiveSec=15min
AccuracySec=1min

[Install]
WantedBy=timers.target
"""

# Write configs
with open("/etc/systemd/system/angelone-oi-poller.service", "w") as f:
    f.write(poller_service)
    
with open("/etc/systemd/system/angelone-oi-health-check.service", "w") as f:
    f.write(hc_service)
    
with open("/etc/systemd/system/angelone-oi-health-check.timer", "w") as f:
    f.write(hc_timer)

# Fix permissions on env file
env_path = "/etc/angelone-oi-poller.env"
os.chmod(env_path, 0o600)
# Change owner to ubuntu (uid=1000, gid=1000)
os.chown(env_path, 1000, 1000)

print("Systemd configs written and permissions fixed.")
