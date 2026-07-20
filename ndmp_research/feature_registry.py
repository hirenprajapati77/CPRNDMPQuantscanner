"""
NDMP OS v6.0 - Dynamic Feature Registry & Plugin Discovery Engine
Dynamically loads feature manifests (feature.yaml) and instantiates plugins automatically.
"""

import os
import glob
import pandas as pd
from typing import Dict, Any, List
from ndmp_research.features.base_feature import BaseFeature
from ndmp_core.src.exceptions import MissingDependencyError, NDMPError

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False


class FeatureRegistry:
    """Dynamic Feature Store Registry & Dependency Resolution Engine."""

    def __init__(self, registry_dir: str = "ndmp_research/registry"):
        self.registry_dir = registry_dir
        self.manifests: Dict[str, Dict[str, Any]] = {}
        self.feature_instances: Dict[str, BaseFeature] = {}
        self._registered_ids: Dict[str, str] = {}  # maps ID to Name

    def discover_manifests(self) -> Dict[str, Dict[str, Any]]:
        """Search, validate, and load all feature.yaml manifests in registry directory."""
        yaml_files = glob.glob(os.path.join(self.registry_dir, "*.yaml"))
        # Explicit sorting to ensure platform-independent loading order
        sorted_files = sorted(yaml_files)
        
        for yf in sorted_files:
            data = self._load_yaml_file(yf)
            if not data or "feature" not in data:
                raise NDMPError(f"Malformed manifest '{yf}': missing 'feature' root key.")
                
            feat_info = data["feature"]
            required_keys = ["id", "name", "version", "category", "dependencies"]
            for key in required_keys:
                if key not in feat_info:
                    raise NDMPError(f"Malformed manifest '{yf}': missing required field '{key}'.")
            
            feat_name = feat_info["name"]
            feat_id = feat_info["id"]

            # Duplicate Checks
            if feat_name in self.manifests:
                raise NDMPError(f"Duplicate feature name detected in manifests: '{feat_name}'")
            if feat_id in [info["id"] for info in self.manifests.values()]:
                raise NDMPError(f"Duplicate feature ID detected in manifests: '{feat_id}'")

            self.manifests[feat_name] = feat_info
            
        return self.manifests

    def _load_yaml_file(self, filepath: str) -> Dict[str, Any]:
        """Load YAML file with PyYAML if present, or zero-dependency simple parser fallback."""
        if HAS_YAML:
            with open(filepath, "r") as f:
                return yaml.safe_load(f) or {}
        
        # Simple zero-dependency YAML parser fallback for basic key-values
        res: Dict[str, Any] = {"feature": {}}
        with open(filepath, "r") as f:
            lines = f.readlines()
        
        current_section = None
        for line in lines:
            line_str = line.strip()
            if not line_str or line_str.startswith("#"):
                continue
            if line_str == "feature:":
                current_section = "feature"
                continue
            if line_str == "parameters:":
                current_section = "parameters"
                continue
            if ":" in line_str and current_section == "feature":
                parts = line_str.split(":", 1)
                k = parts[0].strip()
                v = parts[1].strip()
                if k == "dependencies":
                    res["feature"]["dependencies"] = []
                    current_section = "dependencies"
                    continue
                res["feature"][k] = v
            elif line_str.startswith("- ") and current_section == "dependencies":
                dep_name = line_str.replace("- ", "").strip()
                res["feature"].setdefault("dependencies", []).append(dep_name)
        return res

    def register_feature_instance(self, feature: BaseFeature) -> None:
        """Register a feature plugin instance with strict validation checks."""
        meta = feature.metadata()
        feat_name = meta["name"]
        feat_id = meta["id"]

        # 1. Manifest Matching Check
        if feat_name not in self.manifests:
            raise NDMPError(f"Feature '{feat_name}' cannot be registered: manifest not discovered.")

        manifest = self.manifests[feat_name]

        # 2. Version Matching Check
        if manifest["version"] != feature.version():
            raise NDMPError(
                f"Version mismatch for '{feat_name}': manifest specifies '{manifest['version']}' but plugin has '{feature.version()}'."
            )

        # 3. Dependency Matching Check
        if sorted(manifest["dependencies"]) != sorted(feature.dependencies()):
            raise NDMPError(
                f"Dependency list mismatch for '{feat_name}': manifest specifies {manifest['dependencies']} but plugin has {feature.dependencies()}."
            )

        # 4. Duplicate Check
        if feat_name in self.feature_instances:
            raise NDMPError(f"Feature name duplicate registration: '{feat_name}'")
        if feat_id in self._registered_ids:
            raise NDMPError(f"Feature ID duplicate registration: '{feat_id}' (registered by '{self._registered_ids[feat_id]}')")

        self.feature_instances[feat_name] = feature
        self._registered_ids[feat_id] = feat_name
        
        # 5. Graph Cycle check
        self._check_circular_dependencies()

    def _check_circular_dependencies(self) -> None:
        """Check for circular dependencies in registered features using DFS graph analysis."""
        graph: Dict[str, List[str]] = {}
        for name, feat in self.feature_instances.items():
            # Dependees are other features in the registry
            graph[name] = [dep for dep in feat.dependencies() if dep in self.feature_instances]

        visited: Dict[str, int] = {}  # 0 = unvisited, 1 = visiting, 2 = visited

        def dfs(node: str) -> bool:
            visited[node] = 1
            for neighbor in graph.get(node, []):
                if visited.get(neighbor, 0) == 1:
                    return True  # cycle detected
                if visited.get(neighbor, 0) == 0:
                    if dfs(neighbor):
                        return True
            visited[node] = 2
            return False

        for node in graph:
            if visited.get(node, 0) == 0:
                if dfs(node):
                    raise NDMPError("Circular dependency detected in feature registry graph!")

    def validate_dependencies(self, feature_name: str, available_columns: List[str]) -> bool:
        """Verify that all input data dependencies required by a feature exist."""
        if feature_name not in self.feature_instances:
            raise NDMPError(f"Feature '{feature_name}' not registered!")
        feature = self.feature_instances[feature_name]
        missing = [dep for dep in feature.dependencies() if dep not in available_columns]
        if missing:
            raise MissingDependencyError(f"Feature '{feature_name}' missing dependencies: {missing}")
        return True

    def calculate_all(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate all registered features against an input DataFrame."""
        result_df = pd.DataFrame(index=df.index)
        for feat_name, feature in self.feature_instances.items():
            self.validate_dependencies(feat_name, list(df.columns))
            feat_out = feature.calculate(df)
            if isinstance(feat_out, pd.DataFrame):
                for col in feat_out.columns:
                    result_df[col] = feat_out[col]
            else:
                result_df[feat_name] = feat_out
        return result_df
