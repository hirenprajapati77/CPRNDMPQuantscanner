import pandas as pd
import glob
import os

files = glob.glob('/home/ubuntu/CPRNDMPQuantscanner/data/oi_history/*.parquet')
for f in files:
    print(f"\n--- {os.path.basename(f)} ---")
    df = pd.read_parquet(f)
    print(df.info())
    print("Head:")
    print(df.head(5))
    print("Tail:")
    print(df.tail(5))
