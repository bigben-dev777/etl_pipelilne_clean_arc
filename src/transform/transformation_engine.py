"""transformation_engine.py - Handles data transformation and normalization."""

import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import yaml

from src.extract.source_registry import SourceConfig
from src.transform.normalizers import (
    AddressNormalizer,
    AgeParser,
    CapacityNormalizer,
    LicenseStatusNormalizer,
    NameNormalizer,
    PhoneNormalizer,
    StateNormalizer,
    ZipNormalizer,
)
from src.utils.logging_config import get_logger

logger = get_logger(__name__)


class TransformationEngine:
    """
    Applies transformations and normalizations to data.

    Combines YAML-defined business logic with built-in normalizers to
    transform source data into the target schema format.[1]
    """

    def __init__(self, logic_file: Optional[Path] = None):
        """
        Initialize the transformation engine.

        Args:
            logic_file: Path to default business logic YAML file
        """
        # Initialize normalizers
        self.normalizers = {
            "phone": PhoneNormalizer(),
            "state": StateNormalizer(),
            "zip": ZipNormalizer(),
            "address": AddressNormalizer(),
            "name": NameNormalizer(),
            "age": AgeParser(),
            "capacity": CapacityNormalizer(),
            "license_status": LicenseStatusNormalizer(),
        }

        # Load default business logic
        self.default_transformations = {}
        self.default_settings = {}
        if logic_file and logic_file.exists():
            self._load_default_logic(logic_file)

    def _load_default_logic(self, yaml_file: Path):
        """Load default transformation rules from YAML."""
        try:
            with open(yaml_file, "r") as f:
                data = yaml.safe_load(f) or {}

            self.default_transformations = data.get("transformations", {})
            self.default_settings = data.get("settings", {})

            logger.info(f"Loaded {len(self.default_transformations)} default rules")
        except Exception as e:
            logger.error(f"Failed to load default logic: {e}")

    def transform_dataframe(
        self,
        df: pd.DataFrame,
        column_mapping: Dict[str, str],
        target_columns: List[str],
        schema_transformations: Optional[Dict] = None,
        schema_settings: Optional[Dict] = None,
        source_config: Optional[SourceConfig] = None,
    ) -> pd.DataFrame:
        """
        Transform source DataFrame to target schema.

        Args:
            df: Source DataFrame
            column_mapping: Mapping of target columns to source columns
            target_columns: List of target column names
            schema_transformations: Schema-specific transformation rules
            schema_settings: Schema-specific settings
            source_config: Optional source configuration

        Returns:
            Transformed DataFrame
        """
        result = pd.DataFrame()

        # Merge schema-specific and default transformations
        all_transformations = {**self.default_transformations}
        if schema_transformations:
            all_transformations.update(schema_transformations)

        all_settings = {**self.default_settings}
        if schema_settings:
            all_settings.update(schema_settings)

        # Transform each target column
        for target_col in target_columns:
            if target_col in column_mapping:
                source_col = column_mapping[target_col]
                result[target_col] = self._transform_column(
                    df=df,
                    source_col=source_col,
                    target_col=target_col,
                    transformations=all_transformations,
                    settings=all_settings,
                    source_config=source_config,
                )
            else:
                # Try to apply YAML rules even without explicit mapping
                result[target_col] = self._apply_yaml_rules(
                    df=df,
                    source_col=None,
                    target_col=target_col,
                    transformations=all_transformations,
                    settings=all_settings,
                )

        return result

    def _transform_column(
        self,
        df: pd.DataFrame,
        source_col: str,
        target_col: str,
        transformations: Dict,
        settings: Dict,
        source_config: Optional[SourceConfig],
    ) -> pd.Series:
        """Transform a single column with all applicable rules."""

        if source_col not in df.columns:
            return pd.Series([None] * len(df))

        values = df[source_col].copy()

        # Step 1: Apply YAML business logic rules
        values = self._apply_yaml_rules(
            df=df,
            source_col=source_col,
            target_col=target_col,
            transformations=transformations,
            settings=settings,
            values=values,
        )

        # Step 2: Apply built-in normalizers
        values = self._apply_normalizers(values, target_col)

        # Step 3: Handle special parsing cases
        if target_col in ["first_name", "last_name"]:
            values = values.apply(lambda x: self._extract_name_part(x, target_col))

        elif target_col in ["min_age", "max_age", "ages_served"]:
            values = values.apply(lambda x: self._extract_age_part(x, target_col))

        elif target_col in ["address1", "address2", "city"] and source_config:
            values = self._parse_address_column(
                df, source_col, target_col, source_config
            )

        return values

    def _apply_yaml_rules(
        self,
        df: pd.DataFrame,
        source_col: Optional[str],
        target_col: str,
        transformations: Dict,
        settings: Dict,
        values: Optional[pd.Series] = None,
    ) -> pd.Series:
        """Apply YAML-defined transformation rules."""

        if values is None:
            values = pd.Series([None] * len(df))

        # Get settings
        case_sensitive = settings.get("case_sensitive", False)
        skip_empty = settings.get("skip_empty_values", True)
        log_unmatched = settings.get("log_unmatched_rules", False)

        # Apply each matching rule
        for rule_name, rule in transformations.items():
            if rule.get("target_column") != target_col:
                continue

            # Get source data
            rule_source = rule.get("source_column")
            if rule_source and rule_source in df.columns:
                source_data = df[rule_source]
            elif source_col and source_col in df.columns:
                source_data = df[source_col]
            else:
                if log_unmatched:
                    logger.debug(f"Rule '{rule_name}' skipped: source not found")
                continue

            # Apply rule type
            if "regex" in rule:
                values = self._apply_regex_rule(
                    source_data, values, rule, case_sensitive, skip_empty
                )
            elif "condition" in rule and "value" in rule:
                values = self._apply_condition_rule(
                    source_data, values, rule, case_sensitive, skip_empty
                )
            elif "mapping" in rule:
                values = self._apply_mapping_rule(
                    source_data, values, rule, case_sensitive, skip_empty
                )

        return values

    def _apply_regex_rule(
        self,
        source_data: pd.Series,
        values: pd.Series,
        rule: Dict,
        case_sensitive: bool,
        skip_empty: bool,
    ) -> pd.Series:
        """Apply regex extraction rule."""
        pattern = re.compile(
            rule["regex"], flags=0 if case_sensitive else re.IGNORECASE
        )

        def extract(x):
            if pd.isna(x) or (skip_empty and str(x).strip() == ""):
                return None
            match = pattern.search(str(x))
            if match:
                if "format" in rule:
                    try:
                        return match.expand(rule["format"])
                    except:
                        return match.group(0)
                return match.group(1) if match.groups() else match.group(0)
            return None

        extracted = source_data.apply(extract)
        return values.fillna(extracted)

    def _apply_condition_rule(
        self,
        source_data: pd.Series,
        values: pd.Series,
        rule: Dict,
        case_sensitive: bool,
        skip_empty: bool,
    ) -> pd.Series:
        """Apply conditional assignment rule."""
        condition_pattern = re.compile(
            rule["condition"], flags=0 if case_sensitive else re.IGNORECASE
        )

        def apply_cond(x):
            if pd.isna(x) or (skip_empty and str(x).strip() == ""):
                return None
            if condition_pattern.search(str(x)):
                return rule["value"]
            return None

        conditional = source_data.apply(apply_cond)
        return values.fillna(conditional)

    def _apply_mapping_rule(
        self,
        source_data: pd.Series,
        values: pd.Series,
        rule: Dict,
        case_sensitive: bool,
        skip_empty: bool,
    ) -> pd.Series:
        """Apply value mapping rule."""
        mapping_dict = rule["mapping"]

        def apply_map(x):
            if pd.isna(x) or (skip_empty and str(x).strip() == ""):
                return None

            key = str(x).strip()
            if not case_sensitive:
                mapping_lower = {k.lower(): v for k, v in mapping_dict.items()}
                return mapping_lower.get(key.lower())
            return mapping_dict.get(key)

        mapped = source_data.apply(apply_map)
        return values.fillna(mapped)

    def _apply_normalizers(self, values: pd.Series, target_col: str) -> pd.Series:
        """Apply built-in normalizers based on target column type."""

        normalizer_map = {
            "phone": "phone",
            "phone2": "phone",
            "state": "state",
            "zip": "zip",
            "license_status": "license_status",
            "capacity": "capacity",
        }

        normalizer_key = normalizer_map.get(target_col)
        if normalizer_key and normalizer_key in self.normalizers:
            normalizer = self.normalizers[normalizer_key]
            values = values.apply(lambda x: normalizer.normalize(x)[0])

        return values

    def _extract_name_part(self, value: Any, part: str) -> Optional[str]:
        """Extract first or last name from full name."""
        result, _ = self.normalizers["name"].normalize(value)
        return result.get(part)

    def _extract_age_part(self, value: Any, part: str) -> Any:
        """Extract age-related field."""
        result, _ = self.normalizers["age"].normalize(value)
        return result.get(part)

    def _parse_address_column(
        self,
        df: pd.DataFrame,
        source_col: str,
        target_part: str,
        source_config: SourceConfig,
    ) -> pd.Series:
        """Parse combined address field into components."""
        if source_col in source_config.column_map:
            target_action = source_config.column_map[source_col]
            if target_action == "_parse_full_address":
                return df[source_col].apply(
                    lambda x: self.normalizers["address"]
                    .normalize(x)[0]
                    .get(target_part)
                )

        # Default behavior
        if target_part == "address1":
            return df[source_col].apply(self._basic_clean)
        return pd.Series([None] * len(df))

    def _basic_clean(self, value: Any) -> Any:
        """Basic string cleaning."""
        if pd.isna(value):
            return None
        if isinstance(value, str):
            cleaned = " ".join(value.split())
            return cleaned if cleaned else None
        return value
