"""Hashing utilities for record identification and change detection."""

import hashlib
import json
from typing import Any, Dict


def compute_record_hash(record: Dict[str, Any]) -> str:
    """
    Compute a SHA-256 hash of a record for change detection.
    
    Args:
        record: Dictionary containing record data
        
    Returns:
        Hexadecimal hash string
    """
    # Normalize the record by sorting keys and converting to JSON
    normalized = json.dumps(record, sort_keys=True, default=str, ensure_ascii=False)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def compute_string_hash(text: str) -> str:
    """
    Compute a SHA-256 hash of a string.
    
    Args:
        text: Input string
        
    Returns:
        Hexadecimal hash string
    """
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def compute_schema_fingerprint(column_names: list) -> str:
    """
    Compute a fingerprint for a schema based on column names.
    Used for caching LLM schema inference results.
    
    Args:
        column_names: List of column names
        
    Returns:
        Hexadecimal hash string
    """
    normalized = "|".join(sorted(col.lower().strip() for col in column_names))
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]
