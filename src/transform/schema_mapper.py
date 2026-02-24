"""schema_mapper.py - Main schema mapping orchestrator (refactored)."""

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from src.extract.source_registry import SourceConfig, SourceRegistry
from src.transform.schema_cache import SchemaCacheManager
from src.transform.schema_generator import SchemaGenerator
from src.transform.transformation_engine import TransformationEngine
from src.utils.hashing import compute_schema_fingerprint
from src.utils.logging_config import get_logger

logger = get_logger(__name__)


class SchemaMapper:
    """
    Orchestrates schema mapping with caching and AI-assisted logic generation.

    This refactored version combines mapping and logic generation into a single
    LLM call to ensure consistency and reduce costs.
    """

    TARGET_COLUMNS = [
        "company",
        "facility_type",
        "address1",
        "address2",
        "city",
        "state",
        "zip",
        "county",
        "phone",
        "phone2",
        "email",
        "website_address",
        "first_name",
        "last_name",
        "capacity",
        "min_age",
        "max_age",
        "ages_served",
        "license_status",
        "license_number",
        "license_type",
    ]

    def __init__(
        self,
        source_registry: Optional[SourceRegistry] = None,
        llm_client: Optional[Any] = None,
        use_ai: bool = True,
        cache_dir: Path = Path("cache/schemas"),
        logic_file: Optional[Path] = Path("config/logic.yaml"),
    ):
        """
        Initialize the schema mapper.

        Args:
            source_registry: Registry of known source configurations
            llm_client: LLM client for AI-assisted operations
            use_ai: Whether to use AI for mapping and logic generation
            cache_dir: Directory for persistent caching
            logic_file: Path to default business logic YAML
        """
        self.source_registry = source_registry or SourceRegistry()
        self.llm_client = llm_client
        self.use_ai = use_ai

        # Initialize modular components
        self.cache_manager = SchemaCacheManager(cache_dir=cache_dir)

        self.schema_generator = SchemaGenerator(
            llm_client=llm_client if use_ai else None,
            default_patterns=self._get_default_patterns(),
        )

        self.transformation_engine = TransformationEngine(logic_file=logic_file)

        logger.info("SchemaMapper initialized with generation architecture")

    def map_dataframe(
        self,
        df: pd.DataFrame,
        source_file: Path,
        source_config: Optional[SourceConfig] = None,
    ) -> pd.DataFrame:
        """
        Map a source DataFrame to the target schema.

        Workflow:
        1. Compute schema fingerprint
        2. Check cache for existing mapping and logic
        3. If not cached, generate both mapping and logic in one LLM call
        4. Apply transformations
        5. Cache results for future use

        Args:
            df: Source DataFrame
            source_file: Path to source file
            source_config: Optional pre-determined source configuration

        Returns:
            DataFrame mapped to target schema
        """
        logger.info(f"Mapping {len(df)} rows from {source_file.name}")

        # Step 1: Compute schema fingerprint
        schema_fingerprint = compute_schema_fingerprint(list(df.columns))
        logger.info(f"Schema fingerprint: {schema_fingerprint[:16]}...")

        # Step 2: Get or determine source configuration
        if source_config is None:
            source_config = self.source_registry.get_source_for_file(source_file)

        # Step 3: Get or generate schema (mapping + logic)
        column_mapping, transformations, settings = self._get_or_generate_schema(
            df, schema_fingerprint, source_config
        )

        logger.info(f"Column mapping: {len(column_mapping)} columns mapped")
        logger.info(f"Business logic: {len(transformations)} transformation rules")

        # Step 4: Apply transformations
        result = self.transformation_engine.transform_dataframe(
            df=df,
            column_mapping=column_mapping,
            target_columns=self.TARGET_COLUMNS,
            schema_transformations=transformations,
            schema_settings=settings,
            source_config=source_config,
        )

        # Step 5: Add metadata
        result["source_file"] = source_file.name
        result["record_id"] = self._generate_record_ids(df, source_file)

        logger.info(f"Successfully mapped to {len(result)} rows")

        return result

    def _get_or_generate_schema(
        self,
        df: pd.DataFrame,
        schema_fingerprint: str,
        source_config: Optional[SourceConfig],
    ) -> Tuple[Dict[str, str], Dict, Dict]:
        """
        Get cached schema or generate new  schema (mapping + logic).

        Returns:
            Tuple of (column_mapping, transformations, settings)
        """
        # Check cache first
        cached_data = self.cache_manager.get_schema(schema_fingerprint)
        if cached_data:
            logger.info("Using cached  schema (mapping + logic)")
            return (
                cached_data.get("mapping", {}),
                cached_data.get("transformations", {}),
                cached_data.get("settings", {}),
            )

        # Generate new  schema
        logger.info("Generating  schema (mapping + logic) via LLM...")

        sample_data = df.sample(min(5, len(df))).to_dict(orient="records")

        mapping, transformations, settings, confidence = (
            self.schema_generator.generate_schema(
                source_columns=list(df.columns),
                target_columns=self.TARGET_COLUMNS,
                sample_data=sample_data,
            )
        )

        # Cache the result
        self.cache_manager.save_schema(
            schema_fingerprint=schema_fingerprint,
            mapping=mapping,
            transformations=transformations,
            settings=settings,
            source_columns=list(df.columns),
            confidence=confidence,
        )

        return mapping, transformations, settings

    def _get_default_patterns(self) -> Dict[str, List[str]]:
        """Get default column name patterns from registry."""
        default_config = self.source_registry.default_config
        if not default_config or not default_config.column_map:
            return {}

        # Extract patterns (filter out non-list values)
        patterns = {}
        for key, value in default_config.column_map.items():
            if isinstance(value, list):
                patterns[key] = value

        return patterns

    def _generate_record_ids(self, df: pd.DataFrame, source_file: Path) -> pd.Series:
        """Generate deterministic record IDs."""
        return pd.Series([f"{source_file.stem}_{i:08d}" for i in range(len(df))])

    def invalidate_schema_cache(self, schema_fingerprint: str):
        """Invalidate cached data for a specific schema."""
        self.cache_manager.invalidate_schema(schema_fingerprint)

    def clear_all_caches(self):
        """Clear all cached mappings and logic."""
        self.cache_manager.clear_all()

    def get_cache_stats(self) -> Dict:
        """Get statistics about cached data."""
        return self.cache_manager.get_cache_stats()
