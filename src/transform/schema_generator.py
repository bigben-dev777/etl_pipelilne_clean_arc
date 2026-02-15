"""schema_generator.py - LLM-based schema mapping and logic generation."""

import json
import re
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
from pydantic import ValidationError

from common import SchemaOutput, TransformationRule
from src.extract.source_registry import SourceConfig
from src.transform.prompt import SchemaPromptBuilder
from src.utils.logging_config import get_logger
from src.utils.statis import analyze_dataframe
from utils.json_debug import debug_json_error, validate_json_structure

logger = get_logger(__name__)


class SchemaGenerator:
    """
    Generates both column mapping and business logic in a single LLM call.

    Architecture:
    - LLM outputs JSON (strict, validated with Pydantic)
    - Prompt templates separated for maintainability
    - Robust error handling with retry logic
    - Graceful fallback to rule-based matching
    """

    def __init__(
        self,
        llm_client: Optional[Any] = None,
        default_patterns: Optional[Dict[str, List[str]]] = None,
        max_retries: int = 3,
    ):
        """
        Initialize the generator.

        Args:
            llm_client: LLM client for generating schema
            default_patterns: Default column name patterns for fallback
            max_retries: Maximum retry attempts for parsing failures
        """
        self.llm_client = llm_client
        self.default_patterns = default_patterns or {}
        self.max_retries = max_retries
        self.prompt_builder = SchemaPromptBuilder()

    def generate_schema(
        self,
        source_columns: List[str],
        target_columns: List[str],
        sample_data: List[Dict],
        source_config: Optional[SourceConfig] = None,
    ) -> Tuple[Dict[str, str], Dict, Dict, float]:
        """
        Generate schema including mapping and business logic.

        Args:
            source_columns: List of source column names
            target_columns: List of target column names
            sample_data: Sample rows from the source data
            source_config: Optional source configuration

        Returns:
            Tuple of (mapping, transformations, settings, confidence)
        """
        if not self.llm_client:
            logger.warning("No LLM client available, using fallback mapping")
            return self._fallback_mapping(source_columns, target_columns)

        # Get metadata analysis for better context
        try:
            sample_df = pd.DataFrame(sample_data)
            metadata = analyze_dataframe(sample_df, return_type="str")
        except Exception as e:
            logger.warning(f"Failed to analyze dataframe: {e}")
            metadata = "Metadata analysis unavailable"

        # Try generating with progressive error handling
        for attempt in range(1, self.max_retries + 1):
            try:
                logger.info(
                    f"Generating schema (attempt {attempt}/{self.max_retries})..."
                )

                # Build prompt
                config_hints = self._build_config_hints(source_config)
                prompt = self.prompt_builder.build_prompt(
                    source_columns=source_columns,
                    target_columns=target_columns,
                    sample_data=sample_data,
                    metadata=metadata,
                    config_hints=config_hints,
                    attempt=attempt,
                )

                # print("🚀" * 20)
                from pathlib import Path

                Path("output.txt").write_text(prompt, encoding="utf-8")
                # logger.debug(f"Generated prompt (attempt {attempt}):\n{prompt}")
                # print("🚀" * 20)
                # exit(1)
                # Get LLM response
                response = self.llm_client.complete(prompt)
                logger.debug("💥" * 20)
                logger.debug(f"LLM response (attempt {attempt}):\n{response}...")
                logger.debug("💥" * 20)

                # Parse and validate JSON response
                mapping, transformations, settings, confidence = (
                    self._parse_json_response(
                        response=response,
                        attempt=attempt,
                    )
                )

                # Validate results
                if not mapping and not transformations:
                    raise ValueError("Empty mapping and transformations returned")

                logger.info(
                    f"✓ Successfully generated schema: "
                    f"{len(mapping)} mappings, {len(transformations)} rules, "
                    f"confidence={confidence:.2f}"
                )
                return mapping, transformations, settings, confidence

            except (json.JSONDecodeError, ValidationError) as e:
                logger.warning(
                    f"Attempt {attempt} parsing failed: {type(e).__name__}: {e}"
                )

                if attempt < self.max_retries:
                    logger.info("Retrying with enhanced instructions...")
                else:
                    logger.error("All retry attempts exhausted, using fallback")
                    return self._fallback_mapping(source_columns, target_columns)

            except Exception as e:
                logger.error(f"Attempt {attempt} unexpected error: {e}", exc_info=True)

                if attempt == self.max_retries:
                    logger.error("All retry attempts exhausted, using fallback")
                    return self._fallback_mapping(source_columns, target_columns)

        # Should never reach here, but safety fallback
        return self._fallback_mapping(source_columns, target_columns)

    def _build_config_hints(
        self, source_config: Optional[SourceConfig]
    ) -> Optional[str]:
        """Build configuration hints section from source config."""
        if not source_config or not source_config.column_map:
            return None

        hints = {"known_mappings": {}}
        for key, value in source_config.column_map.items():
            if isinstance(value, str) and not value.startswith("_"):
                hints["known_mappings"][key] = value

        if hints["known_mappings"]:
            hints_json = json.dumps(hints, indent=2)
            return f"\n**KNOWN CONFIGURATION HINTS:**\n```json\n{hints_json}\n```"

        return None

    def _parse_json_response(
        self,
        response: str,
        attempt: int = 1,
    ) -> Tuple[Dict[str, str], Dict, Dict, float]:
        """Parse JSON response with robust error handling."""

        # Step 1: Extract JSON from response
        json_text = self._extract_json(response)

        if not json_text:
            raise ValueError("Could not extract JSON from LLM response")

        logger.debug(f"Extracted JSON length: {len(json_text)} characters")

        # Step 2: Try parsing JSON
        try:
            raw_data = json.loads(json_text)
            logger.debug("✓ JSON parsing successful")
        except json.JSONDecodeError as e:
            # Use debug utility for detailed error reporting
            debug_json_error(json_text, e)

            # Try to fix common issues
            if attempt < self.max_retries:
                logger.info("Attempting JSON sanitization...")
                json_text = self._sanitize_json(json_text)
                try:
                    raw_data = json.loads(json_text)
                    logger.info("✓ JSON sanitization successful")
                except json.JSONDecodeError as e2:
                    debug_json_error(json_text, e2)
                    raise ValueError(
                        f"JSON parsing failed even after sanitization: {e2}"
                    )
            else:
                raise ValueError(f"JSON parsing failed: {e}")

        # Step 2.5: Validate structure before Pydantic
        structure_issues = validate_json_structure(raw_data)
        if structure_issues:
            logger.warning("JSON structure validation issues:")
            for issue in structure_issues:
                logger.warning(f"  - {issue}")

        # Step 3: Validate with Pydantic
        try:
            validated = SchemaOutput(**raw_data)
            logger.debug("✓ Pydantic validation successful")
        except ValidationError as e:
            logger.error("Pydantic validation failed:")
            for error in e.errors():
                logger.error(f"  - {error['loc']}: {error['msg']}")
            raise ValueError(f"Schema validation failed: {e}")

        # Step 4: Convert to application format
        mapping = validated.mappings

        # Convert Pydantic models to dicts
        transformations = {}
        for rule_name, rule in validated.transformations.items():
            transformations[rule_name] = rule.model_dump(exclude_none=True)

        settings = validated.settings
        confidence = validated.confidence

        logger.info(
            f"✓ Parsed and validated: {len(mapping)} mappings, "
            f"{len(transformations)} rules, confidence={confidence:.2f}"
        )

        return mapping, transformations, settings, confidence

    def _extract_json(self, response: str) -> Optional[str]:
        """
        Extract JSON content from LLM response.

        Handles:
        - Markdown code fences
        - Extra text before/after JSON
        - Nested braces
        """
        # Remove markdown code fences if present
        cleaned = re.sub(r"```(?:json)?\s*\n?", "", response)
        cleaned = re.sub(r"```\s*$", "", cleaned)

        # Try to find JSON object boundaries using stack-based parsing
        stack = []
        start_idx = None

        for i, char in enumerate(cleaned):
            if char == "{":
                if not stack:
                    start_idx = i
                stack.append(char)
            elif char == "}":
                if stack:
                    stack.pop()
                    if not stack and start_idx is not None:
                        # Found complete JSON object
                        json_candidate = cleaned[start_idx : i + 1]
                        logger.debug(
                            f"Found JSON candidate at position {start_idx}-{i+1}"
                        )
                        return json_candidate

        # Fallback: try entire response if it looks like JSON
        stripped = cleaned.strip()
        if stripped.startswith("{") and stripped.endswith("}"):
            logger.debug("Using entire response as JSON")
            return stripped

        logger.warning("Could not extract JSON from response")
        return None

    def _sanitize_json(self, json_text: str) -> str:
        """
        Attempt to fix common JSON issues.

        Common LLM mistakes:
        1. Single backslashes in regex: \\\\d → \\d
        2. Trailing commas: {...,} → {...}
        3. Unescaped quotes in strings
        4. Comments (not valid in JSON)
        5. Single quotes instead of double quotes
        """
        sanitized = json_text

        # 1. Fix single backslashes (but not already doubled)
        # This is tricky - we want \d → \\d but not \\d → \\\\d
        # Use negative lookbehind and lookahead
        sanitized = re.sub(r'(?<!\\)\\(?![\\"/bfnrtu])', r"\\\\", sanitized)

        # 2. Remove trailing commas before closing braces/brackets
        sanitized = re.sub(r",(\s*[}\]])", r"\1", sanitized)

        # 3. Remove comments (// and /* */)
        sanitized = re.sub(r"//.*?$", "", sanitized, flags=re.MULTILINE)
        sanitized = re.sub(r"/\*.*?\*/", "", sanitized, flags=re.DOTALL)

        # 4. Try to fix single quotes (risky, only if no double quotes inside)
        # Only apply if there are single quotes but they seem to be used as string delimiters
        if "'" in sanitized and sanitized.count("'") > sanitized.count('"'):
            # Replace single quotes with double quotes, but be careful
            # This is a heuristic and may not always work
            sanitized = re.sub(r"'([^']*)'(\s*:)", r'"\1"\2', sanitized)  # Keys
            sanitized = re.sub(r":\s*'([^']*)'", r': "\1"', sanitized)  # Values

        # 5. Remove any text before first { or after last }
        match = re.search(r"\{.*\}", sanitized, re.DOTALL)
        if match:
            sanitized = match.group(0)

        logger.debug(f"Sanitization applied, new length: {len(sanitized)}")

        return sanitized

    def _fallback_mapping(
        self,
        source_columns: List[str],
        target_columns: List[str],
    ) -> Tuple[Dict[str, str], Dict, Dict, float]:
        """
        Fallback to simple exact matching when LLM fails.

        Strategy:
        1. Exact case-insensitive matching
        2. Pattern matching from default_patterns
        3. Substring matching (as last resort)

        Returns:
            Tuple of (mapping, transformations, settings, confidence)
        """
        logger.info("Using fallback exact matching")

        mapping = {}
        source_lower = {col.lower().strip(): col for col in source_columns}

        # Strategy 1: Exact matching
        for target_col in target_columns:
            target_lower = target_col.lower().strip()
            if target_lower in source_lower:
                mapping[target_col] = source_lower[target_lower]
                logger.debug(
                    f"Exact match: {target_col} → {source_lower[target_lower]}"
                )

        # Strategy 2: Pattern matching from defaults
        for target_col in target_columns:
            if target_col in mapping:
                continue

            patterns = self.default_patterns.get(target_col, [])
            for pattern in patterns:
                pattern_lower = pattern.lower()
                for source_col in source_columns:
                    source_lower_str = source_col.lower()
                    if (
                        pattern_lower in source_lower_str
                        or source_lower_str in pattern_lower
                    ):
                        mapping[target_col] = source_col
                        logger.debug(
                            f"Pattern match: {target_col} → {source_col} (via {pattern})"
                        )
                        break
                if target_col in mapping:
                    break

        # Strategy 3: Substring matching (conservative)
        for target_col in target_columns:
            if target_col in mapping:
                continue

            target_parts = target_col.lower().split("_")
            for source_col in source_columns:
                source_lower_str = source_col.lower()
                # Check if any significant part matches
                for part in target_parts:
                    if len(part) > 3 and part in source_lower_str:
                        mapping[target_col] = source_col
                        logger.debug(
                            f"Substring match: {target_col} → {source_col} (via '{part}')"
                        )
                        break
                if target_col in mapping:
                    break

        confidence = len(mapping) / len(target_columns) if target_columns else 0.0

        logger.info(
            f"Fallback mapping: {len(mapping)}/{len(target_columns)} columns, "
            f"confidence={confidence:.2f}"
        )

        return mapping, {}, {}, confidence
