import glob
import pandas as pd
import subprocess

print("=== SYSTEMCTL STATUS: angelone-oi-poller ===")
res1 = subprocess.run(["systemctl", "status", "angelone-oi-poller.service"], capture_output=True, text=True)
print(res1.stdout)
print(res1.stderr)

print("=== SYSTEMCTL STATUS: angelone-oi-health-check ===")
res2 = subprocess.run(["systemctl", "status", "angelone-oi-health-check.timer"], capture_output=True, text=True)
print(res2.stdout)
print(res2.stderr)

print("=== ENV FILE PERMISSIONS ===")
res3 = subprocess.run(["ls", "-la", "/etc/angelone-oi-poller.env"], capture_output=True, text=True)
print(res3.stdout)
print(res3.stderr)

print("=== PARQUET DATA ROWS ===")
parquet_files = glob.glob("/home/ubuntu/CPRNDMPQuantscanner/data/oi_history_angelone/*.parquet")
if not parquet_files:
    print("No parquet files found yet!")
else:
    for f in parquet_files:
        df = pd.read_parquet(f)
        print(f"\nFile: {f}")
        print(f"Total Rows: {len(df)}")
        print(df.tail())
