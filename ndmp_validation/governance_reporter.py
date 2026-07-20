"""
NDMP OS v6.0 - Governance Reporter & Promotion Manifest Generator
Logs versioned validation reports and promotion manifests in ndmp_knowledge/experiments/.
"""

import json
import os
from datetime import datetime, timezone
from pydantic import BaseModel
from typing import Dict, Any, Tuple
from ndmp_validation.gates import GovernanceGateSuiteResult


class PromotionManifest(BaseModel):
    """Automated Promotion Record for feature/model passing all 5 gates."""
    feature_name: str
    feature_version: str
    status: str = "PROMOTED"
    promoted_at_utc: str
    validation_id: str
    dataset_version: str
    git_commit: str
    governance_summary: Dict[str, Any]


class GovernanceReporter:
    """Manages logging of validation reports and automated promotion manifests."""

    def __init__(self, experiments_dir: str = "ndmp_knowledge/experiments"):
        self.experiments_dir = experiments_dir
        os.makedirs(self.experiments_dir, exist_ok=True)

    def log_validation_suite(
        self,
        suite_result: GovernanceGateSuiteResult,
        feature_name: str = "RelativeStrengthFeature",
        feature_version: str = "1.0.0"
    ) -> Tuple[str, str | None]:
        """
        Log validation suite report to JSON. If passed, generate a Promotion Manifest.
        Returns tuple of (validation_report_path, promotion_manifest_path_or_none).
        """
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        report_filename = f"report_{suite_result.validation_id}_{timestamp}.json"
        report_path = os.path.join(self.experiments_dir, report_filename)

        with open(report_path, "w") as f:
            json.dump(suite_result.model_dump() if hasattr(suite_result, 'model_dump') else suite_result.dict(), f, indent=2)

        promotion_path = None
        if suite_result.overall_status == "PASS":
            manifest = PromotionManifest(
                feature_name=feature_name,
                feature_version=feature_version,
                status="PROMOTED",
                promoted_at_utc=datetime.now(timezone.utc).isoformat(),
                validation_id=suite_result.validation_id,
                dataset_version=suite_result.dataset_version,
                git_commit=suite_result.git_commit,
                governance_summary={
                    g.gate_name: {"realized": g.realized_value, "passed": g.passed}
                    for g in suite_result.gate_results
                }
            )
            promotion_filename = f"promotion_{feature_name}_{timestamp}.json"
            promotion_path = os.path.join(self.experiments_dir, promotion_filename)
            with open(promotion_path, "w") as f:
                json.dump(manifest.model_dump() if hasattr(manifest, 'model_dump') else manifest.dict(), f, indent=2)

        return report_path, promotion_path
