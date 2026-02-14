"""Data extraction modules for the ETL pipeline."""

from .base_extractor import BaseExtractor
from .source_registry import SourceRegistry, get_source_config

__all__ = [
    "BaseExtractor",
    "CSVExtractor",
    "SourceRegistry",
    "get_source_config",
]
