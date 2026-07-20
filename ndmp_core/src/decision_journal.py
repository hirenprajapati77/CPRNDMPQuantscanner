"""
NDMP OS v6.0 - Persistent Decision Journal & Scanner Manifest Logger
Stores JSON Decision Records and Scanner Manifests in ndmp_knowledge/journal/.
"""

import json
import os
import hashlib
from datetime import datetime, timezone
from pydantic import BaseModel
from typing import List, Dict, Any, Tuple
from ndmp_core.src.ranking_engine import RankedCandidate


class ScannerManifest(BaseModel):
    """Execution Manifest for reproducibility."""
    scanner_version: str = "1.0.0"
    build_id: str
    dataset_version: str
    scan_timestamp: str
    total_symbols_scanned: int
    top_candidates_count: int
    runtime_ms: float
    feature_versions: Dict[str, str]


class DecisionRecord(BaseModel):
    """Complete Decision Record per stock candidate."""
    symbol: str
    rank: int
    score: float
    scan_time: str
    feature_versions: Dict[str, str]
    signals: Dict[str, Any]
    reasons: List[str]


class DecisionJournalLogger:
    """Manages persistent logging of decision journals and scanner manifests."""

    def __init__(self, journal_dir: str = "ndmp_knowledge/journal"):
        self.journal_dir = journal_dir
        os.makedirs(self.journal_dir, exist_ok=True)

    def log_scan_session(
        self,
        ranked_candidates: List[RankedCandidate],
        runtime_ms: float,
        dataset_version: str = "NSE_FO_V1.0",
        feature_versions: Dict[str, str] | None = None
    ) -> Tuple[str, str]:
        """
        Log complete scan decision session and manifest to JSON files.
        Returns paths to created manifest and journal files.
        """
        if feature_versions is None:
            feature_versions = {
                "CPRFeature": "1.0.0",
                "VWAPFeature": "1.0.0",
                "IntradayOIFeature": "1.0.0",
                "RelativeStrengthFeature": "1.0.0"
            }

        scan_timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        build_id = hashlib.sha256(scan_timestamp.encode('utf-8')).hexdigest()[:12]

        manifest = ScannerManifest(
            scanner_version="1.0.0",
            build_id=build_id,
            dataset_version=dataset_version,
            scan_timestamp=scan_timestamp,
            total_symbols_scanned=len(ranked_candidates),
            top_candidates_count=min(10, len(ranked_candidates)),
            runtime_ms=round(runtime_ms, 2),
            feature_versions=feature_versions
        )

        decision_records = []
        for cand in ranked_candidates:
            record = DecisionRecord(
                symbol=cand.symbol,
                rank=cand.rank,
                score=cand.score,
                scan_time=cand.signals.timestamp,
                feature_versions=feature_versions,
                signals=cand.signals.model_dump() if hasattr(cand.signals, 'model_dump') else cand.signals.dict(),
                reasons=cand.reasons
            )
            decision_records.append(record.model_dump() if hasattr(record, 'model_dump') else record.dict())

        manifest_path = os.path.join(self.journal_dir, f"manifest_{scan_timestamp}.json")
        journal_path = os.path.join(self.journal_dir, f"decisions_{scan_timestamp}.json")

        with open(manifest_path, "w") as f:
            json.dump(manifest.model_dump() if hasattr(manifest, 'model_dump') else manifest.dict(), f, indent=2)

        with open(journal_path, "w") as f:
            json.dump(decision_records, f, indent=2)

        return manifest_path, journal_path
