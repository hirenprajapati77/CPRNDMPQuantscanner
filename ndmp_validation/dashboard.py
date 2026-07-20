"""
NDMP OS v6.0 - Governance Dashboard Visualizer
Renders a visual terminal dashboard of the 5 Promotion Gates.
"""

from ndmp_validation.gates import GovernanceGateSuiteResult


class GovernanceDashboard:
    """Renders visual terminal dashboard summary of Governance Gate results."""

    @staticmethod
    def render(suite_result: GovernanceGateSuiteResult) -> str:
        lines = []
        lines.append("================================================================================")
        lines.append(f"NDMP OS GOVERNANCE AUDIT DASHBOARD - ID: {suite_result.validation_id}")
        lines.append(f"Dataset: {suite_result.dataset_version} | Status: {suite_result.overall_status}")
        lines.append("================================================================================")
        lines.append(f"{'Gate ID':<10} | {'Gate Name':<32} | {'Realized':<10} | {'Target':<22} | {'Status'}")
        lines.append("--------------------------------------------------------------------------------")

        for g in suite_result.gate_results:
            status_symbol = "🟢 PASS" if g.passed else "🔴 FAIL"
            lines.append(
                f"{g.gate_id:<10} | {g.gate_name:<32} | {g.realized_value:<10} | {g.target_threshold:<22} | {status_symbol}"
            )

        lines.append("================================================================================")
        if suite_result.overall_status == "PASS":
            lines.append("🏆 ALL GATES PASSED: Feature / Model is PROMOTED to Production ndmp-core.")
        else:
            lines.append("⛔ PROMOTION REJECTED: Candidate failed one or more quantitative gates.")
        lines.append("================================================================================")

        output_text = "\n".join(lines)
        print(output_text)
        return output_text
