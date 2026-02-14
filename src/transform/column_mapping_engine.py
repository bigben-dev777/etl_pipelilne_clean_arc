"""column_mapping_engine.py - Handles column mapping inference and matching."""

import re
from typing import Any, Dict, List, Optional

import pandas as pd
from rapidfuzz import fuzz

from config.settings import TAEGET_COLUMN_DESCRIPTION
from src.extract.source_registry import SourceConfig
from src.utils.logging_config import get_logger
from src.utils.statis import analyze_dataframe

logger = get_logger(__name__)


class ColumnMappingEngine:
    """Handles column mapping using rule-based, fuzzy, and AI-assisted methods.

    Implements a multi-tier approach: exact matching, fuzzy matching, and LLM-based
    inference for complex or ambiguous schemas.[4]
    """

    def __init__(
        self,
        default_patterns: Optional[Dict[str, List[str]]] = None,
        llm_client: Optional[Any] = None,
        fuzzy_threshold: float = 0.85,
    ):
        """
        Initialize the mapping engine.

        Args:
            default_patterns: Default column name patterns for matching
            llm_client: Optional LLM client for AI-assisted mapping
            fuzzy_threshold: Minimum similarity score for fuzzy matching
        """
        self.default_patterns = default_patterns or {}
        self.llm_client = llm_client
        self.fuzzy_threshold = fuzzy_threshold

    def infer_mapping(
        self,
        source_columns: List[str],
        target_columns: List[str],
        sample_data: Optional[pd.DataFrame] = None,
        source_config: Optional[SourceConfig] = None,
    ) -> Dict[str, str]:
        """
        Infer column mapping using multiple strategies.

        Args:
            source_columns: List of source column names
            target_columns: List of target column names
            sample_data: Optional sample data for context
            source_config: Optional source configuration with known mappings

        Returns:
            Dictionary mapping target columns to source columns
        """
        mapping = {}

        # Strategy 1: Apply rule-based mapping from config
        if source_config and source_config.column_map:
            mapping.update(self._apply_config_mapping(source_columns, source_config))
            logger.debug(f"Config mapping found {len(mapping)} columns")

        # Strategy 2: Exact matching (case-insensitive)
        exact_matches = self._exact_match(source_columns, target_columns)
        mapping.update({k: v for k, v in exact_matches.items() if k not in mapping})
        logger.debug(f"Exact matching found {len(exact_matches)} columns")
        logger.debug(f"Mapping columns: {mapping}")

        # Strategy 3: Fuzzy matching with patterns
        # fuzzy_matches = self._fuzzy_match(source_columns, target_columns)
        # mapping.update({k: v for k, v in fuzzy_matches.items() if k not in mapping})
        # logger.debug(f"Fuzzy matching found {len(fuzzy_matches)} columns")

        # Strategy 4: AI-assisted mapping for remaining columns
        if self.llm_client and len(mapping) < len(target_columns) * 0.7:
            unmapped_targets = [t for t in target_columns if t not in mapping]
            unmapped_sources = [s for s in source_columns if s not in mapping.values()]

            if unmapped_targets and unmapped_sources and sample_data is not None:
                ai_mapping = self._ai_assisted_mapping(
                    unmapped_sources, unmapped_targets, sample_data
                )
                mapping.update(ai_mapping)
                logger.info(f"AI mapping found {len(ai_mapping)} additional columns")

        return mapping

    def _apply_config_mapping(
        self, source_columns: List[str], source_config: SourceConfig
    ) -> Dict[str, str]:
        """Apply rule-based mapping from source configuration."""
        mapping = {}

        for key, value in source_config.column_map.items():
            if isinstance(value, str):
                # Direct mapping: source_col -> target_col
                source_col = key
                target_col = value

                # Skip transformation directives
                if target_col.startswith("_"):
                    continue

                # Find matching column (case-insensitive)
                for col in source_columns:
                    if col.lower().strip() == source_col.lower().strip():
                        mapping[target_col] = col
                        break

        return mapping

    def _exact_match(
        self, source_columns: List[str], target_columns: List[str]
    ) -> Dict[str, str]:
        """Perform exact case-insensitive matching."""
        mapping = {}

        source_lower = {col.lower().strip(): col for col in source_columns}

        for target_col in target_columns:
            target_lower = target_col.lower().strip()
            if target_lower in source_lower:
                mapping[target_col] = source_lower[target_lower]

        return mapping

    def _fuzzy_match(
        self, source_columns: List[str], target_columns: List[str]
    ) -> Dict[str, str]:
        """Perform fuzzy matching using patterns and similarity scores."""
        mapping = {}

        for target_col in target_columns:
            patterns = self.default_patterns.get(target_col, [target_col])
            best_match = None
            best_score = 0

            for source_col in source_columns:
                source_lower = source_col.lower().strip()

                # Check against all patterns
                for pattern in patterns:
                    pattern_lower = pattern.lower()

                    # Substring match
                    if pattern_lower in source_lower or source_lower in pattern_lower:
                        score = 0.95
                    else:
                        # Fuzzy similarity
                        score = fuzz.ratio(source_lower, pattern_lower) / 100

                    if score > best_score and score >= self.fuzzy_threshold:
                        best_match = source_col
                        best_score = score

            if best_match:
                mapping[target_col] = best_match

        return mapping

    def _ai_assisted_mapping(
        self,
        source_columns: List[str],
        target_columns: List[str],
        sample_data: pd.DataFrame,
    ) -> Dict[str, str]:
        """Use LLM to infer mappings for difficult cases."""
        if not self.llm_client:
            return {}

        try:
            # Get sample data for context
            sample_dict = sample_data[source_columns].head(5).to_dict(orient="records")
            # Get metadata analysis for better context
            metadata = analyze_dataframe(sample_data[source_columns], return_type="str")
            logger.debug(f"Sample data metadata:\n{metadata}")

            prompt = self._build_mapping_prompt(
                source_columns, target_columns, sample_dict
            )

            response = self.llm_client.complete(prompt)
            logger.debug(f"LLM response for mapping:\n{response}")

            mapping = self._parse_mapping_response(response)

            # Filter to only requested columns
            filtered = {
                t: s
                for t, s in mapping.items()
                if t in target_columns and s in source_columns
            }

            return filtered

        except Exception as e:
            logger.error(f"AI-assisted mapping failed: {e}")
            exit(1)
            return {}

    def _build_mapping_prompt(
        self,
        source_columns: List[str],
        target_columns: List[str],
        sample_data: List[Dict],
        metadata: str = "",
    ) -> str:
        """Build prompt for AI-assisted column mapping."""

        target_descriptions = TAEGET_COLUMN_DESCRIPTION

        prompt = f"""You are a data mapping specialist. Map source columns to target columns based on semantic meaning and sample data.

TARGET COLUMNS (what we need):
{chr(10).join(f"- {col}: {target_descriptions.get(col, 'N/A')}" for col in target_columns)}

SOURCE COLUMNS (what we have):
{chr(10).join(f"- {col}" for col in source_columns)}

SAMPLE DATA:
{sample_data}

METADATA ANALYSIS:
{metadata}

Return a JSON object with your mappings:
{{
  "mappings": {{
    "target_column": "source_column",
    ...
  }},
  "confidence": 0.85
}}

Only map columns you are confident about. Return ONLY the JSON, no explanation.
"""
        return prompt

    def _parse_mapping_response(self, response: str) -> Dict[str, str]:
        """Parse JSON mapping from LLM response."""
        import json

        try:
            # Extract JSON from response
            json_match = re.search(r"\{.*\}", response, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                return data.get("mappings", {})
        except json.JSONDecodeError as e:
            logger.warning(f"Could not parse LLM mapping response: {e}")

        return {}
