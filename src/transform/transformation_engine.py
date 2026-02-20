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
    BooleanNormalizer,
    CapacityNormalizer,
    CountyNormalizer,
    EmailValidator,
    FacilityTypeNormalizer,
    LicenseStatusNormalizer,
    LicenseTypeNormalizer,
    MinMaxAgeNormalizer,
    NameNormalizer,
    PhoneNormalizer,
    StateNormalizer,
    WebsiteNormalizer,
    ZipNormalizer,
)
from src.utils.logging_config import get_logger

logger = get_logger(__name__)


class TransformationEngine:
    """
    Applies transformations and normalizations to data.

    Combines YAML-defined business logic with built-in normalizers to
    transform source data into the target schema format.
    """

    def __init__(self, logic_file: Optional[Path] = None):
        """
        Initialize the transformation engine.

        Args:
            logic_file: Path to default business logic YAML file
        """
        # Initialize normalizers (aligned with canonical ETL format)
        self.normalizers = {
            "phone": PhoneNormalizer(),
            "phone2": PhoneNormalizer(),
            "state": StateNormalizer(),
            "zip": ZipNormalizer(),
            "address": AddressNormalizer(),
            "address1": AddressNormalizer(),
            "address2": AddressNormalizer(),
            "name": NameNormalizer(),
            "first_name": NameNormalizer(),
            "last_name": NameNormalizer(),
            "ages_served": AgeParser(),
            "min_age": MinMaxAgeNormalizer(),
            "max_age": MinMaxAgeNormalizer(),
            "capacity": CapacityNormalizer(),
            "license_status": LicenseStatusNormalizer(),
            "license_type": LicenseTypeNormalizer(),
            "facility_type": FacilityTypeNormalizer(),
            "email": EmailValidator(),
            "website": WebsiteNormalizer(),
            "website_address": WebsiteNormalizer(),
            "county": CountyNormalizer(),
            "is_duplicate": BooleanNormalizer(),
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

        # Log available columns for debugging
        logger.info(f"Source DataFrame columns: {df.columns.tolist()}")
        logger.info(f"Column mapping: {column_mapping}")
        logger.info(f"Target columns: {target_columns}")

        # Transform each target column
        for target_col in target_columns:
            # Get the mapped source column (if any)
            mapped_source_col = column_mapping.get(target_col)

            result[target_col] = self._transform_column(
                df=df,
                source_col=mapped_source_col,
                target_col=target_col,
                transformations=all_transformations,
                settings=all_settings,
                source_config=source_config,
            )

        return result

    def _transform_column(
        self,
        df: pd.DataFrame,
        source_col: Optional[str],
        target_col: str,
        transformations: Dict,
        settings: Dict,
        source_config: Optional[SourceConfig],
    ) -> pd.Series:
        """Transform a single column with all applicable rules."""

        # Initialize with None values
        values = pd.Series([None] * len(df), index=df.index)

        # Step 1: Copy source column if it exists and is mapped
        if source_col and source_col in df.columns:
            values = df[source_col].copy()

        # Step 2: Apply YAML business logic rules (this is the main transformation)
        values = self._apply_yaml_rules(
            df=df,
            source_col=source_col,
            target_col=target_col,
            transformations=transformations,
            settings=settings,
            values=values,
        )

        # Step 3: Handle special parsing cases for composite fields
        # These handle cases where one source column maps to multiple target columns
        has_yaml_rules = any(
            rule.get("target_column") == target_col for rule in transformations.values()
        )

        if not has_yaml_rules:
            # Name parsing: Extract first_name/last_name from full name field
            if target_col in ["first_name", "last_name"] and source_col:
                if source_col in df.columns:
                    values = df[source_col].apply(
                        lambda x: self._extract_name_part(x, target_col)
                    )

            # Age parsing: Extract min_age/max_age/ages_served from age range field
            elif target_col in ["min_age", "max_age", "ages_served"] and source_col:
                if source_col in df.columns:
                    values = df[source_col].apply(
                        lambda x: self._extract_age_part(x, target_col)
                    )

            # License field extraction: Extract from 'Type License' composite field
            elif target_col in ["license_type", "facility_type"] and source_col:
                if source_col in df.columns:
                    values = df[source_col].apply(
                        lambda x: self._extract_license_field(x, target_col)
                    )

            # Address parsing: Parse combined address into components
            elif (
                target_col in ["address1", "address2", "city"]
                and source_config
                and source_col
            ):
                values = self._parse_address_column(
                    df, source_col, target_col, source_config
                )
                print("💥" * 10)

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
            values = pd.Series([None] * len(df), index=df.index)

        # Get settings
        case_sensitive = settings.get("case_sensitive", False)
        skip_empty = settings.get("skip_empty_values", True)
        log_unmatched = settings.get(
            "log_unmatched_rules", True
        )  # Changed default to True

        # Find all rules for this target column
        matching_rules = {
            name: rule
            for name, rule in transformations.items()
            if rule.get("target_column") == target_col
        }

        # Apply each matching rule
        for rule_name, rule in matching_rules.items():

            # Get source data - try multiple strategies
            rule_source = rule.get("source_column")
            source_data = None

            # Strategy 1: Use rule's specified source column
            if rule_source:
                source_data = self._find_source_column(df, rule_source, case_sensitive)

            # Strategy 2: Use mapped source column
            if source_data is None and source_col:
                source_data = self._find_source_column(df, source_col, case_sensitive)

            # Strategy 3: Use current values (for chained transformations)
            if source_data is None and values is not None and not values.isna().all():
                source_data = values.copy()

            # If we still don't have source data, skip this rule
            if source_data is None:
                if log_unmatched:
                    logger.warning(
                        f"Rule '{rule_name}' skipped: source column '{rule_source or source_col}' "
                        f"not found in DataFrame columns: {df.columns.tolist()}"
                    )
                continue

            # Apply the rule
            try:
                transformed = self._apply_combined_rule(
                    source_data,
                    rule,
                    case_sensitive,
                    skip_empty,
                    log_unmatched,
                    rule_name,
                )

                # Update values with non-null results from this rule
                # This allows multiple rules to contribute to the same column
                mask = transformed.notna()
                if mask.any():
                    values.loc[mask] = transformed.loc[mask]
                    logger.debug(
                        f"Rule '{rule_name}': Transformed {mask.sum()} values for '{target_col}'"
                    )

            except Exception as e:
                logger.error(f"Rule '{rule_name}' failed: {e}", exc_info=True)

        return values

    def _find_source_column(
        self, df: pd.DataFrame, column_name: str, case_sensitive: bool = False
    ) -> Optional[pd.Series]:
        """
        Find a column in the DataFrame, with optional case-insensitive matching.

        Args:
            df: DataFrame to search
            column_name: Column name to find
            case_sensitive: Whether to match case-sensitively

        Returns:
            Series if found, None otherwise
        """
        # Exact match
        if column_name in df.columns:
            return df[column_name].copy()

        # Case-insensitive match
        if not case_sensitive:
            for col in df.columns:
                if col.lower() == column_name.lower():
                    return df[col].copy()

        return None

    def _apply_combined_rule(
        self,
        source_data: pd.Series,
        rule: Dict,
        case_sensitive: bool,
        skip_empty: bool,
        log_unmatched: bool,
        rule_name: str,
    ) -> pd.Series:
        """
        Apply combined transformation rules in sequence.

        Supports combinations like:
        - regex + mapping
        - mapping + condition
        - regex + condition
        - regex + mapping + condition (all three)

        Rules are applied in this order:
        1. regex (extraction/transformation)
        2. condition (filtering)
        3. mapping (value substitution)
        """

        # Track intermediate results
        intermediate = source_data.copy()
        steps_applied = []

        # Step 1: Apply regex if present
        if "regex" in rule:
            intermediate = self._apply_regex_extraction(
                intermediate, rule, case_sensitive, skip_empty
            )
            after_count = intermediate.notna().sum()
            steps_applied.append(f"regex ({after_count} values)")

        # Step 2: Apply condition if present
        if "condition" in rule:
            intermediate = self._apply_condition_filter(
                intermediate, rule, case_sensitive, skip_empty
            )
            after_count = intermediate.notna().sum()
            steps_applied.append(f"condition ({after_count} values)")

        # Step 3: Apply mapping if present
        if "mapping" in rule:
            intermediate = self._apply_mapping_substitution(
                intermediate, rule, case_sensitive, skip_empty
            )
            after_count = intermediate.notna().sum()
            steps_applied.append(f"mapping ({after_count} values)")

        # Step 4: Apply value assignment if present (standalone or after condition)
        if "value" in rule and "condition" not in rule:
            # Direct value assignment (no condition)
            intermediate = pd.Series(
                [rule["value"]] * len(intermediate), index=intermediate.index
            )
            steps_applied.append(f"value assignment")

        if steps_applied and log_unmatched:
            logger.debug(
                f"Rule '{rule_name}': Applied steps: {' → '.join(steps_applied)}"
            )

        # Return the transformed values (don't merge here, let caller decide)
        return intermediate

    def _apply_regex_extraction(
        self,
        source_data: pd.Series,
        rule: Dict,
        case_sensitive: bool,
        skip_empty: bool,
    ) -> pd.Series:
        """Apply regex extraction/transformation."""
        pattern = re.compile(
            rule["regex"], flags=0 if case_sensitive else re.IGNORECASE
        )

        def extract(x):
            if pd.isna(x) or (skip_empty and str(x).strip() == ""):
                return ""
            match = pattern.search(str(x))
            if match:
                if "format" in rule:
                    try:
                        result = match.expand(rule["format"])
                        return result.strip() if result else None
                    except Exception as e:
                        logger.warning(f"Regex format expansion failed for '{x}': {e}")
                        return match.group(0).strip() if match.group(0) else None
                # Return first group if exists, otherwise full match
                result = match.group(1) if match.groups() else match.group(0)
                return result.strip() if result else None
            return ""

        return source_data.apply(extract)

    def _apply_condition_filter(
        self,
        source_data: pd.Series,
        rule: Dict,
        case_sensitive: bool,
        skip_empty: bool,
    ) -> pd.Series:
        """
        Apply conditional filtering.

        If 'value' is present in rule, assigns that value when condition matches.
        Otherwise, passes through the source value only if condition matches.
        """
        condition_pattern = re.compile(
            rule["condition"], flags=0 if case_sensitive else re.IGNORECASE
        )

        def apply_cond(x):
            if pd.isna(x) or (skip_empty and str(x).strip() == ""):
                return None
            if condition_pattern.search(str(x)):
                # If value is specified, use it; otherwise pass through the original
                return rule.get("value", x)
            return None

        return source_data.apply(apply_cond)

    def _apply_mapping_substitution(
        self,
        source_data: pd.Series,
        rule: Dict,
        case_sensitive: bool,
        skip_empty: bool,
    ) -> pd.Series:
        """Apply value mapping/substitution."""
        mapping_dict = rule["mapping"]

        # Pre-process mapping for case-insensitive matching
        if not case_sensitive:
            mapping_lower = {str(k).strip().lower(): v for k, v in mapping_dict.items()}
        else:
            mapping_normalized = {str(k).strip(): v for k, v in mapping_dict.items()}

        def apply_map(x):
            if pd.isna(x) or (skip_empty and str(x).strip() == ""):
                return None

            key = str(x).strip()
            if not case_sensitive:
                return mapping_lower.get(key.lower())
            return mapping_normalized.get(key)

        result = source_data.apply(apply_map)

        # Log mapping statistics
        mapped_count = result.notna().sum()
        total_count = source_data.notna().sum()
        if total_count > 0:
            logger.info(
                f"Mapping matched {mapped_count}/{total_count} values ({100*mapped_count/total_count:.1f}%)"
            )

        return result

    def _extract_name_part(self, value: Any, part: str) -> Optional[str]:
        """
        Extract first or last name from full name.
        Returns Title Case format.
        """
        if not value or pd.isna(value):
            return None

        result, _ = self.normalizers["name"].normalize(value)

        # result is a dict with 'first_name' and 'last_name' keys
        return result.get(part)

    def _extract_age_part(self, value: Any, part: str) -> Any:
        """
        Extract age-related field in canonical format.

        - ages_served: Returns AGE_BUCKET_ENUM (e.g., 'INFANT', 'TODDLER', 'BIRTH_TO_5')
        - min_age/max_age: Returns INTEGER_YEARS
        """
        if not value or pd.isna(value):
            return None

        if part == "ages_served":
            # Use AgeParser for canonical age bucket
            result, metadata = self.normalizers["ages_served"].normalize(value)
            return result  # Returns canonical enum like 'INFANT', 'TODDLER', etc.

        elif part in ["min_age", "max_age"]:
            # Use MinMaxAgeNormalizer for integer years
            result, metadata = self.normalizers[part].normalize(value)
            return result  # Returns integer years

        return None

    def _extract_license_field(self, value: Any, field_type: str) -> Optional[str]:
        """
        Extract license-related fields from 'Type License' column.

        Args:
            value: Source value (e.g., 'CHILD CARE FAMILY - K820015716')
            field_type: One of 'license_type',  'facility_type'

        Returns:
            Canonical formatted value or None
        """
        if not value or pd.isna(value):
            return None

        normalizer_map = {
            "license_type": self.normalizers.get("license_type"),
            "facility_type": self.normalizers.get("facility_type"),
        }

        normalizer = normalizer_map.get(field_type)
        if normalizer:
            result, metadata = normalizer.normalize(value)
            return result

        return None

    def _parse_address_column(
        self,
        df: pd.DataFrame,
        source_col: str,
        target_part: str,
        source_config: SourceConfig,
    ) -> pd.Series:
        """
        Parse combined address field into components.
        Returns Title Case format for address fields.
        """
        if source_col not in df.columns:
            return pd.Series([None] * len(df), index=df.index)

        if source_col in source_config.column_map:
            target_action = source_config.column_map[source_col]
            if target_action == "_parse_full_address":
                # Use AddressNormalizer for standardization
                # Note: AddressNormalizer currently returns normalized single address
                # For full address parsing, you might need a separate parser
                if target_part == "address1":
                    return df[source_col].apply(
                        lambda x: self.normalizers["address"].normalize(x)[0]
                    )
                # For address2, city, state, zip - would need enhanced parser
                return pd.Series([None] * len(df), index=df.index)

        # Default behavior - just normalize the address
        if target_part == "address1":
            return df[source_col].apply(
                lambda x: self.normalizers["address"].normalize(x)[0] if x else None
            )

        return pd.Series([None] * len(df), index=df.index)
