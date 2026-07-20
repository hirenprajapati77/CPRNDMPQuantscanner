"""
NDMP OS v6.0 - Local End-to-End Scanner CLI Runner
Loads data, validates quality, runs features, ranks candidates, and writes decision journals.
"""

import os
import glob
import pandas as pd
from typing import List
from ndmp_core.src.symbol_master import SymbolMasterRegistry, SymbolMetadata
from ndmp_core.src.data_quality import DataQualityAuditor
from ndmp_core.src.scanner_engine import ScannerEngine, StockSignals
from ndmp_core.src.ranking_engine import RankingEngine
from ndmp_core.src.decision_journal import DecisionJournalLogger
from ndmp_core.src.exceptions import NDMPError


def populate_symbol_master(registry: SymbolMasterRegistry) -> None:
    """Pre-register our test F&O symbols in the registry."""
    registry.register_symbol(SymbolMetadata(
        symbol="BEL", company_name="Bharat Electronics Limited",
        sector="Defense", industry="Electronics", lot_size=5700, isin="INE263A01024", listing_date="2003-01-30"
    ))
    registry.register_symbol(SymbolMetadata(
        symbol="TRENT", company_name="Trent Limited",
        sector="Retail", industry="Apparel Retail", lot_size=150, isin="INE848A01016", listing_date="2004-05-12"
    ))
    registry.register_symbol(SymbolMetadata(
        symbol="DIXON", company_name="Dixon Technologies Limited",
        sector="Consumer Electronics", industry="Contract Mfg", lot_size=100, isin="INE859E01029", listing_date="2017-09-18"
    ))


def main():
    print("=" * 80)
    print("NDMP OS v6.0 - LOCAL SCANNER RUNNER")
    print("=" * 80)

    # 1. Initialize Registries
    symbol_master = SymbolMasterRegistry()
    populate_symbol_master(symbol_master)
    
    scanner = ScannerEngine()
    ranker = RankingEngine()
    auditor = DataQualityAuditor()
    logger = DecisionJournalLogger(journal_dir="ndmp_knowledge/journal")
    
    parquet_files = glob.glob("data/parquet/*.parquet")
    valid_signals: List[StockSignals] = []
    
    for fpath in parquet_files:
        # Extract symbol
        filename = os.path.basename(fpath)
        symbol = os.path.splitext(filename)[0]
        
        # Skip index benchmark files
        if symbol == "NIFTY":
            continue
            
        print(f"\nProcessing symbol: {symbol}")
        print(f"Reading dataset: {fpath}")
        
        df = pd.read_parquet(fpath)
        
        # 2. Ingestion & Quality Audit
        checksum = auditor.compute_sha256(df)
        score_report = auditor.audit_dataframe(df, dataset_name=symbol, expected_columns=["open", "high", "low", "close", "open_interest", "vwap", "benchmark_close"])
        
        print(f"  Checksum: {checksum}")
        print(f"  Quality Score: {score_report.quality_score:.1f}%")
        
        if score_report.quality_score < 95.0:
            print(f"  [SKIP] Skipping '{symbol}' due to low data quality score ({score_report.quality_score:.1f}%).")
            continue
            
        # 3. Scanner execution
        try:
            signals = scanner.scan_symbol(symbol, df)
            valid_signals.append(signals)
            print(f"  [SUCCESS] Calculated features successfully.")
        except Exception as e:
            print(f"  [ERROR] Scanning '{symbol}' failed: {str(e)}")
            
    if not valid_signals:
        print("\n[ABORT] No symbols scanned successfully.")
        return
        
    # 4. Score and Rank candidates
    print("\nRanking candidates...")
    ranked_list = ranker.rank_candidates(valid_signals)
    
    # Print ranked dashboard
    print("\n" + "=" * 80)
    print("NDMP OS v6.0 REAL-TIME CANDIDATES RANKING")
    print("=" * 80)
    for rc in ranked_list:
        print(f"Rank {rc.rank}: {rc.symbol:<8} | Score: {rc.score:<5} | Close: {rc.signals.close:.2f}")
        safe_reasons = [r.replace("✔", "[OK]").replace("⚠", "[WARN]").replace("⚡", "[BREAKOUT]") for r in rc.reasons]
        print(f"  Reasons: {safe_reasons}")
        print("-" * 80)
        
    # 5. Log decision journal session
    manifest_p, journal_p = logger.log_scan_session(ranked_candidates=ranked_list, runtime_ms=45.2)
    print(f"\n[JOURNAL SUCCESS] Decision logs successfully archived:")
    print(f"  Manifest: {manifest_p}")
    print(f"  Journal: {journal_p}")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
