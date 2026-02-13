"""schema_mapper.py - Main schema mapping orchestrator (refactored)."""

from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from src.extract.source_registry import SourceConfig, SourceRegistry
from src.transform.column_mapping_engine import ColumnMappingEngine
from src.transform.schema_cache import SchemaCacheManager
from src.transform.schema_logic_generator import SchemaLogicGenerator
from src.transform.transformation_engine import TransformationEngine
from src.utils.hashing import compute_schema_fingerprint
from src.utils.logging_config import get_logger

logger = get_logger(__name__)


class SchemaMapper:
    """
    Orchestrates schema mapping with caching and AI-assisted logic generation.

    This refactored version separates concerns into specialized modules:
    - SchemaCacheManager: Persistent file-based caching
    - ColumnMappingEngine: Multi-strategy column mapping
    - SchemaLogicGenerator: LLM-based business logic generation
    - TransformationEngine: Data transformation and normalization
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
        use_ai_mapping: bool = True,
        use_ai_logic: bool = True,
        cache_dir: Path = Path("cache/schemas"),
        logic_file: Optional[Path] = Path("config/logic.yaml"),
    ):
        """
        Initialize the schema mapper.

        Args:
            source_registry: Registry of known source configurations
            llm_client: LLM client for AI-assisted operations
            use_ai_mapping: Whether to use AI for column mapping
            use_ai_logic: Whether to use AI for logic generation
            cache_dir: Directory for persistent caching
            logic_file: Path to default business logic YAML
        """
        self.source_registry = source_registry or SourceRegistry()
        self.llm_client = llm_client
        self.use_ai_mapping = use_ai_mapping
        self.use_ai_logic = use_ai_logic

        # Initialize modular components
        self.cache_manager = SchemaCacheManager(cache_dir=cache_dir)

        self.mapping_engine = ColumnMappingEngine(
            default_patterns=self._get_default_patterns(),
            llm_client=llm_client if use_ai_mapping else None,
            fuzzy_threshold=0.85,
        )

        self.logic_generator = SchemaLogicGenerator(
            llm_client=llm_client if use_ai_logic else None
        )

        self.transformation_engine = TransformationEngine(logic_file=logic_file)

        logger.info("SchemaMapper initialized with modular architecture")

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
        3. If not cached, infer mapping and generate logic
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
        logger.debug(f"Schema fingerprint: {schema_fingerprint[:16]}...")

        # Step 2: Get or determine source configuration
        if source_config is None:
            source_config = self.source_registry.get_source_for_file(source_file)

        # Step 3: Get or infer column mapping
        column_mapping = self._get_or_infer_mapping(
            df, schema_fingerprint, source_config
        )
        logger.info(f"Column mapping: {len(column_mapping)} columns mapped")

        # Step 4: Get or generate business logic
        transformations, settings = self._get_or_generate_logic(
            df, schema_fingerprint, column_mapping
        )
        logger.info(f"Business logic: {len(transformations)} transformation rules")

        # Step 5: Apply transformations
        result = self.transformation_engine.transform_dataframe(
            df=df,
            column_mapping=column_mapping,
            target_columns=self.TARGET_COLUMNS,
            schema_transformations=transformations,
            schema_settings=settings,
            source_config=source_config,
        )

        # Step 6: Add metadata
        result["source_file"] = source_file.name
        result["record_id"] = self._generate_record_ids(df, source_file)

        logger.info(f"Successfully mapped to {len(result)} rows")

        return result

    def _get_or_infer_mapping(
        self,
        df: pd.DataFrame,
        schema_fingerprint: str,
        source_config: Optional[SourceConfig],
    ) -> Dict[str, str]:
        """Get cached mapping or infer new mapping."""

        # Check cache first
        cached_mapping = self.cache_manager.get_mapping(schema_fingerprint)
        if cached_mapping:
            logger.info("Using cached column mapping")
            return cached_mapping

        # Infer new mapping
        logger.info("Inferring column mapping...")
        mapping = self.mapping_engine.infer_mapping(
            source_columns=list(df.columns),
            target_columns=self.TARGET_COLUMNS,
            sample_data=df,
            source_config=source_config,
        )

        # Calculate confidence
        confidence = len(mapping) / len(self.TARGET_COLUMNS)

        # Cache the result
        self.cache_manager.save_mapping(
            schema_fingerprint=schema_fingerprint,
            mapping=mapping,
            source_columns=list(df.columns),
            confidence=confidence,
        )

        return mapping

    def _get_or_generate_logic(
        self, df: pd.DataFrame, schema_fingerprint: str, column_mapping: Dict[str, str]
    ) -> tuple[Dict, Dict]:
        """Get cached logic or generate new logic rules."""

        # Check cache first
        cached_logic, cached_settings = self.cache_manager.get_logic(schema_fingerprint)
        if cached_logic:
            logger.info("Using cached business logic")
            return cached_logic, cached_settings or {}

        # Generate new logic if AI is enabled
        if self.use_ai_logic and self.llm_client:
            logger.info("Generating schema-specific business logic...")
            sample_data = df.sample(min(10, len(df))).to_dict(orient="records")

            transformations, settings = self.logic_generator.generate_logic(
                source_columns=list(df.columns),
                sample_data=sample_data,
                mapping=column_mapping,
                target_schema=self.TARGET_COLUMNS,
            )

            if transformations:
                # Cache the generated logic
                self.cache_manager.save_logic(
                    schema_fingerprint=schema_fingerprint,
                    transformations=transformations,
                    settings=settings,
                )

                return transformations, settings

        # Return empty if no logic generated
        return {}, {}

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
