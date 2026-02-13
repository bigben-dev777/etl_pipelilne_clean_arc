"""schema_cache.py - Persistent caching for schema mappings and business logic."""

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Tuple

from src.utils.logging_config import get_logger

logger = get_logger(__name__)


class SchemaCacheManager:
    """Manages persistent file-based caching for schema mappings and logic rules.

    Uses disk-based caching to preserve mappings across runs, reducing the need
    for repeated LLM calls and improving performance for long-running processes.
    """

    def __init__(self, cache_dir: Path = Path("cache/schemas")):
        """
        Initialize the cache manager.

        Args:
            cache_dir: Directory to store cache files
        """
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Separate cache files for different data types
        self.mapping_cache_file = self.cache_dir / "column_mappings.json"
        self.logic_cache_file = self.cache_dir / "business_logic.json"
        self.metadata_file = self.cache_dir / "cache_metadata.json"

        # In-memory caches for fast access during runtime
        self._mapping_cache: Dict[str, Dict[str, str]] = {}
        self._logic_cache: Dict[str, Dict] = {}
        self._settings_cache: Dict[str, Dict] = {}
        self._metadata: Dict[str, Dict] = {}

        # Load existing caches from disk
        self._load_caches()

    def _load_caches(self):
        """Load all cache files from disk into memory."""
        try:
            if self.mapping_cache_file.exists():
                with open(self.mapping_cache_file, "r") as f:
                    self._mapping_cache = json.load(f)
                logger.info(
                    f"Loaded {len(self._mapping_cache)} schema mappings from cache"
                )

            if self.logic_cache_file.exists():
                with open(self.logic_cache_file, "r") as f:
                    data = json.load(f)
                    self._logic_cache = data.get("transformations", {})
                    self._settings_cache = data.get("settings", {})
                logger.info(
                    f"Loaded {len(self._logic_cache)} schema logic rules from cache"
                )

            if self.metadata_file.exists():
                with open(self.metadata_file, "r") as f:
                    self._metadata = json.load(f)

        except Exception as e:
            logger.error(f"Failed to load caches: {e}")
            # Initialize empty caches on error
            self._mapping_cache = {}
            self._logic_cache = {}
            self._settings_cache = {}
            self._metadata = {}

    def _save_mapping_cache(self):
        """Persist mapping cache to disk."""
        try:
            with open(self.mapping_cache_file, "w") as f:
                json.dump(self._mapping_cache, f, indent=2)
            logger.debug(f"Saved mapping cache to {self.mapping_cache_file}")
        except Exception as e:
            logger.error(f"Failed to save mapping cache: {e}")

    def _save_logic_cache(self):
        """Persist logic cache to disk."""
        try:
            data = {
                "transformations": self._logic_cache,
                "settings": self._settings_cache,
            }
            with open(self.logic_cache_file, "w") as f:
                json.dump(data, f, indent=2)
            logger.debug(f"Saved logic cache to {self.logic_cache_file}")
        except Exception as e:
            logger.error(f"Failed to save logic cache: {e}")

    def _save_metadata(self):
        """Persist metadata to disk."""
        try:
            with open(self.metadata_file, "w") as f:
                json.dump(self._metadata, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save metadata: {e}")

    def get_mapping(self, schema_fingerprint: str) -> Optional[Dict[str, str]]:
        """
        Retrieve cached column mapping for a schema.

        Args:
            schema_fingerprint: Unique identifier for the schema

        Returns:
            Column mapping dict or None if not cached
        """
        return self._mapping_cache.get(schema_fingerprint)

    def save_mapping(
        self,
        schema_fingerprint: str,
        mapping: Dict[str, str],
        source_columns: list,
        confidence: float = 1.0,
    ):
        """
        Save column mapping to cache with metadata.

        Args:
            schema_fingerprint: Unique identifier for the schema
            mapping: Column mapping dictionary
            source_columns: List of source column names
            confidence: Confidence score for the mapping (0.0-1.0)
        """
        self._mapping_cache[schema_fingerprint] = mapping

        # Update metadata
        self._metadata[schema_fingerprint] = {
            "created_at": datetime.now().isoformat(),
            "source_columns": source_columns,
            "target_columns": list(mapping.keys()),
            "confidence": confidence,
            "mapping_count": len(mapping),
        }

        self._save_mapping_cache()
        self._save_metadata()
        logger.info(f"Cached mapping for schema {schema_fingerprint[:8]}...")

    def get_logic(
        self, schema_fingerprint: str
    ) -> Tuple[Optional[Dict], Optional[Dict]]:
        """
        Retrieve cached business logic for a schema.

        Args:
            schema_fingerprint: Unique identifier for the schema

        Returns:
            Tuple of (transformations dict, settings dict) or (None, None)
        """
        transformations = self._logic_cache.get(schema_fingerprint)
        settings = self._settings_cache.get(schema_fingerprint)

        if transformations is None:
            return None, None
        return transformations, settings

    def save_logic(
        self,
        schema_fingerprint: str,
        transformations: Dict,
        settings: Optional[Dict] = None,
    ):
        """
        Save business logic rules to cache.

        Args:
            schema_fingerprint: Unique identifier for the schema
            transformations: Transformation rules dictionary
            settings: Optional settings dictionary
        """
        self._logic_cache[schema_fingerprint] = transformations
        if settings:
            self._settings_cache[schema_fingerprint] = settings

        self._save_logic_cache()
        logger.info(
            f"Cached {len(transformations)} logic rules for schema {schema_fingerprint[:8]}..."
        )

    def invalidate_schema(self, schema_fingerprint: str):
        """Remove a schema from all caches."""
        self._mapping_cache.pop(schema_fingerprint, None)
        self._logic_cache.pop(schema_fingerprint, None)
        self._settings_cache.pop(schema_fingerprint, None)
        self._metadata.pop(schema_fingerprint, None)

        self._save_mapping_cache()
        self._save_logic_cache()
        self._save_metadata()
        logger.info(f"Invalidated cache for schema {schema_fingerprint[:8]}...")

    def clear_all(self):
        """Clear all caches (both memory and disk)."""
        self._mapping_cache.clear()
        self._logic_cache.clear()
        self._settings_cache.clear()
        self._metadata.clear()

        for cache_file in [
            self.mapping_cache_file,
            self.logic_cache_file,
            self.metadata_file,
        ]:
            if cache_file.exists():
                cache_file.unlink()

        logger.info("Cleared all schema caches")

    def get_cache_stats(self) -> Dict:
        """Get statistics about cached data."""
        return {
            "total_schemas": len(self._mapping_cache),
            "total_logic_rules": sum(
                len(rules) for rules in self._logic_cache.values()
            ),
            "cache_dir": str(self.cache_dir),
            "cache_size_mb": sum(
                f.stat().st_size for f in self.cache_dir.glob("*.json")
            )
            / (1024 * 1024),
        }
