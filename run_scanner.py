"""
NDMP OS v6.0 - Local End-to-End Scanner CLI Runner
Loads data, validates quality, runs features, ranks candidates, and writes decision journals.
"""

import glob
import os
import time
import pandas as pd
from typing import List

from ndmp_core.src.symbol_master import SymbolMasterRegistry, SymbolMetadata
from ndmp_core.src.data_quality import DataQualityAuditor
from ndmp_core.src.scanner_engine import ScannerEngine, StockSignals
from ndmp_core.src.ranking_engine import RankingEngine
from ndmp_core.src.decision_journal import DecisionJournalLogger
from ndmp_core.src.observation_journal import ObservationJournal
from ndmp_core.src.config import DEFAULT_CONFIG
from ndmp_core.src.exceptions import NDMPError, DataValidationError, DataSourceIntegrityError


SCANNER_EXPECTED_COLUMNS = [
    "open", "high", "low", "close", "vwap", "benchmark_close", "open_interest",
]


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
    start_time = time.perf_counter()

    print("=" * 80)
    print("NDMP OS v6.0 - LOCAL SCANNER RUNNER")
    print("=" * 80)

    config = DEFAULT_CONFIG
    symbol_master = SymbolMasterRegistry()
    populate_symbol_master(symbol_master)

    scanner = ScannerEngine()
    ranker = RankingEngine()
    auditor = DataQualityAuditor()
    logger = DecisionJournalLogger(journal_dir="ndmp_knowledge/journal")

    parquet_files = glob.glob(os.path.join(config.engine.data_dir, "*.parquet"))
    valid_signals: List[StockSignals] = []
    symbols_processed = 0
    symbols_skipped = 0

    for fpath in parquet_files:
        filename = os.path.basename(fpath)
        symbol = os.path.splitext(filename)[0]

        if symbol == "NIFTY":
            continue

        symbols_processed += 1
        print(f"\nProcessing symbol: {symbol}")
        print(f"Reading dataset: {fpath}")

        df = pd.read_parquet(fpath)

        checksum = auditor.compute_sha256(df)
        score_report = auditor.audit_dataframe(
            df, dataset_name=symbol, expected_columns=SCANNER_EXPECTED_COLUMNS
        )

        print(f"  Checksum: {checksum}")
        print(f"  Quality Score: {score_report.quality_score:.1f}%")

        if score_report.status != "ACCEPTED":
            reason = []
            if not score_report.schema_passed:
                reason.append("schema")
            if not score_report.oi_integrity_passed:
                reason.append("OI integrity")
            if not score_report.calendar_passed:
                reason.append("calendar")
            if score_report.quality_score < auditor.QUALITY_THRESHOLD:
                reason.append("low score")
            print(f"  [SKIP] Skipping '{symbol}' ({', '.join(reason) or 'audit failed'}).")
            symbols_skipped += 1
            continue

        try:
            signals = scanner.scan_symbol(symbol, df)
            valid_signals.append(signals)
            print("  [SUCCESS] Calculated features successfully.")
        except (DataValidationError, DataSourceIntegrityError, NDMPError) as e:
            print(f"  [ERROR] Scanning '{symbol}' failed: {e}")
            symbols_skipped += 1

    if not valid_signals:
        print("\n[ABORT] No symbols scanned successfully.")
        return

    print("\nRanking candidates...")
    ranked_list = ranker.rank_candidates(valid_signals)

    print("\n" + "=" * 80)
    print("NDMP OS v6.0 REAL-TIME CANDIDATES RANKING")
    print("=" * 80)
    for rc in ranked_list:
        print(f"Rank {rc.rank}: {rc.symbol:<8} | Score: {rc.score:<5} | Close: {rc.signals.close:.2f}")
        safe_reasons = [r.replace("✔", "[OK]").replace("⚠", "[WARN]").replace("⚡", "[BREAKOUT]") for r in rc.reasons]
        print(f"  Reasons: {safe_reasons}")
        print("-" * 80)

    runtime_ms = (time.perf_counter() - start_time) * 1000.0
    manifest_p, journal_p = logger.log_scan_session(
        ranked_candidates=ranked_list,
        runtime_ms=runtime_ms,
        symbols_processed=symbols_processed,
        symbols_skipped=symbols_skipped,
    )
    print("\n[JOURNAL SUCCESS] Decision logs successfully archived:")
    print(f"  Manifest: {manifest_p}")
    print(f"  Journal: {journal_p}")
    print(f"  Runtime: {runtime_ms:.1f} ms")
    print("=" * 80 + "\n")

    obs_journal = ObservationJournal(journal_dir="data/observation_journal")
    scan_date = ranked_list[0].signals.timestamp.split(" ")[0] if ranked_list else None
    if scan_date:
        obs_journal.log_signals(ranked_list, scan_date=scan_date)
        for rc in ranked_list:
            fpath = os.path.join(config.engine.data_dir, f"{rc.symbol}.parquet")
            if os.path.exists(fpath):
                ohlcv_df = pd.read_parquet(fpath)
                obs_journal.resolve_outcomes(rc.symbol, ohlcv_df)
        print(f"[OBSERVATION JOURNAL] Logged signals and resolved available outcomes for {len(ranked_list)} candidates.")


if __name__ == "__main__":
    main()
