"""schema_cache.py - Manages persistent caching of schema mappings and logic."""

from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

import yaml

from src.utils.logging_config import get_logger

logger = get_logger(__name__)


class SchemaCacheManager:
    """
    Manages file-based caching of schema mappings and business logic.

    Strategy:
    - LLM outputs JSON (strict, validated)
    - Cache stores YAML (human-readable, easy to edit)
    - Application uses Python dicts (format-agnostic)

    This gives us:
    - Reliability of JSON parsing from LLM
    - Readability of YAML for debugging
    - Flexibility of native Python data structures
    """

    def __init__(self, cache_dir: Path = Path("cache/schemas")):
        """
        Initialize the cache manager.

        Args:
            cache_dir: Directory for storing cache files
        """
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Cache directory: {self.cache_dir.absolute()}")

    def get_schema(self, schema_fingerprint: str) -> Optional[Dict]:
        """
        Retrieve cached  schema from YAML file.

        Args:
            schema_fingerprint: Unique hash of the schema

        Returns:
            Dictionary containing mapping, transformations, and settings, or None
        """
        cache_file = self._get_cache_file(schema_fingerprint)

        if not cache_file.exists():
            logger.debug(f"No cache found for schema {schema_fingerprint[:16]}")
            return None

        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)

            # Validate cache structure
            if not self._validate_cache_data(data):
                logger.warning(
                    f"Invalid cache structure in {cache_file.name}, ignoring"
                )
                return None

            logger.info(f"✓ Loaded cached schema from {cache_file.name}")
            return data

        except Exception as e:
            logger.error(f"Failed to load cache file {cache_file.name}: {e}")
            return None

    def save_schema(
        self,
        schema_fingerprint: str,
        mapping: Dict[str, str],
        transformations: Dict,
        settings: Dict,
        source_columns: list,
        confidence: float,
    ):
        """
        Save schema to YAML cache file.

        YAML is used for storage because:
        - Human-readable for debugging
        - Easy to manually edit if needed
        - Comments can be added
        - Diffs are cleaner in version control

        Args:
            schema_fingerprint: Unique hash of the schema
            mapping: Column mapping dictionary
            transformations: Transformation rules dictionary
            settings: Settings dictionary
            source_columns: List of source column names
            confidence: Confidence score (0.0 to 1.0)
        """
        cache_file = self._get_cache_file(schema_fingerprint)

        cache_data = {
            "metadata": {
                "schema_fingerprint": schema_fingerprint,
                "created_at": datetime.now().isoformat(),
                "source_columns": source_columns,
                "confidence": round(confidence, 4),
                "num_mappings": len(mapping),
                "num_transformations": len(transformations),
            },
            "mapping": mapping,
            "transformations": transformations,
            "settings": settings,
        }

        try:
            with open(cache_file, "w", encoding="utf-8") as f:
                # Write header comment
                f.write(f"# Schema Cache File\n")
                f.write(f"# Generated: {datetime.now().isoformat()}\n")
                f.write(f"# Fingerprint: {schema_fingerprint}\n")
                f.write(f"# Confidence: {confidence:.2%}\n")
                f.write(f"#\n")
                f.write(
                    f"# This file was generated from LLM JSON output and converted to YAML for readability.\n"
                )
                f.write(f"# You can manually edit this file if needed.\n\n")

                # Write YAML data
                yaml.dump(
                    cache_data,
                    f,
                    default_flow_style=False,
                    allow_unicode=True,
                    sort_keys=False,
                    indent=2,
                    width=120,
                )

            logger.info(f"✓ Saved schema to {cache_file.name}")

        except Exception as e:
            logger.error(f"Failed to save cache file {cache_file.name}: {e}")

    def invalidate_schema(self, schema_fingerprint: str):
        """
        Invalidate (delete) cached data for a specific schema.

        Args:
            schema_fingerprint: Unique hash of the schema
        """
        cache_file = self._get_cache_file(schema_fingerprint)

        if cache_file.exists():
            try:
                cache_file.unlink()
                logger.info(f"✓ Invalidated cache for schema {schema_fingerprint[:16]}")
            except Exception as e:
                logger.error(f"Failed to delete cache file: {e}")
        else:
            logger.debug(f"No cache file to invalidate for {schema_fingerprint[:16]}")

    def clear_all(self):
        """Clear all cached schema files."""
        try:
            count = 0
            for cache_file in self.cache_dir.glob("schema_*.yaml"):
                cache_file.unlink()
                count += 1

            logger.info(f"✓ Cleared {count} cache files")

        except Exception as e:
            logger.error(f"Failed to clear cache: {e}")

    def get_cache_stats(self) -> Dict:
        """
        Get statistics about cached data.

        Returns:
            Dictionary with cache statistics
        """
        cache_files = list(self.cache_dir.glob("schema_*.yaml"))

        total_size = sum(f.stat().st_size for f in cache_files)

        stats = {
            "total_schemas": len(cache_files),
            "cache_dir": str(self.cache_dir.absolute()),
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / 1024 / 1024, 2),
            "schemas": [],
        }

        for cache_file in cache_files:
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)

                metadata = data.get("metadata", {})
                stats["schemas"].append(
                    {
                        "fingerprint": metadata.get("schema_fingerprint", "unknown")[
                            :16
                        ],
                        "created_at": metadata.get("created_at"),
                        "confidence": metadata.get("confidence"),
                        "num_mappings": metadata.get("num_mappings"),
                        "num_transformations": metadata.get("num_transformations"),
                        "file_size_kb": round(cache_file.stat().st_size / 1024, 2),
                    }
                )

            except Exception as e:
                logger.warning(f"Could not read cache file {cache_file.name}: {e}")

        # Sort by creation date (newest first)
        stats["schemas"].sort(key=lambda x: x.get("created_at", ""), reverse=True)

        return stats

    def _get_cache_file(self, schema_fingerprint: str) -> Path:
        """Get cache file path for a schema fingerprint."""
        return self.cache_dir / f"schema_{schema_fingerprint}.yaml"

    def _validate_cache_data(self, data: Dict) -> bool:
        """Validate cache data structure."""
        if not isinstance(data, dict):
            return False

        required_keys = {"metadata", "mapping", "transformations", "settings"}
        if not all(key in data for key in required_keys):
            logger.warning(f"Missing required keys. Found: {data.keys()}")
            return False

        # Validate metadata
        metadata = data.get("metadata", {})
        if not isinstance(metadata, dict):
            return False

        # Validate mapping
        mapping = data.get("mapping", {})
        if not isinstance(mapping, dict):
            return False

        # Validate transformations
        transformations = data.get("transformations", {})
        if not isinstance(transformations, dict):
            return False

        return True
