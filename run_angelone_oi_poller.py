from ndmp_core.src.angelone_oi_poller import AngelOneOIPoller

symbols = [
    {"symbol": "BEL25AUG26FUT", "exch_seg": "NFO"},
    {"symbol": "TRENT25AUG26FUT", "exch_seg": "NFO"},
    {"symbol": "DIXON25AUG26FUT", "exch_seg": "NFO"},
]

poller = AngelOneOIPoller(symbols=symbols)
print(f"Starting Angel One OI Poller for symbols: {[s['symbol'] for s in symbols]}...", flush=True)
poller.run_forever()
