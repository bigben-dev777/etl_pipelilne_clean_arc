"""schema_logic_generator.py - LLM-based business logic generation."""

import re
from typing import Any, Dict, List, Optional, Tuple

import yaml

from src.utils.logging_config import get_logger

logger = get_logger(__name__)


class SchemaLogicGenerator:
    """Generates schema-specific business logic rules using LLM.

    This module handles the generation of transformation rules tailored to
    specific data schemas, improving data quality and consistency.[1]
    """

    def __init__(self, llm_client: Optional[Any] = None):
        """
        Initialize the logic generator.

        Args:
            llm_client: LLM client for generating logic rules
        """
        self.llm_client = llm_client

    def generate_logic(
        self,
        source_columns: List[str],
        sample_data: List[Dict],
        mapping: Dict[str, str],
        target_schema: List[str],
    ) -> Tuple[Dict, Dict]:
        """
        Generate business logic rules for a specific schema.

        Args:
            source_columns: List of source column names
            sample_data: Sample rows from the source data
            mapping: Current column mapping (target -> source)
            target_schema: List of target column names

        Returns:
            Tuple of (transformations dict, settings dict)
        """
        if not self.llm_client:
            logger.warning("No LLM client available for logic generation")
            return {}, {}

        try:
            prompt = self._build_logic_prompt(
                source_columns, sample_data, mapping, target_schema
            )
            response = self.llm_client.complete(prompt)
            transformations, settings = self._parse_logic_response(response)

            logger.info(f"Generated {len(transformations)} transformation rules")
            return transformations, settings

        except Exception as e:
            logger.error(f"Failed to generate schema logic: {e}")
            return {}, {}

    def _build_logic_prompt(
        self,
        source_columns: List[str],
        sample_data: List[Dict],
        mapping: Dict[str, str],
        target_schema: List[str],
    ) -> str:
        """Build prompt for LLM to generate business logic rules."""

        prompt = f"""You are a data engineering assistant specializing in ETL transformations.

Given the following source CSV schema and sample data, generate YAML transformation rules to clean, standardize, and validate the data according to best practices.[2]

SOURCE COLUMNS:
{chr(10).join(f"- {c}" for c in source_columns)}

SAMPLE DATA (first 5 rows):
{sample_data[:5]}

KNOWN COLUMN MAPPINGS (target -> source):
{chr(10).join(f"- {t} <- {s}" for t, s in mapping.items())}

TARGET SCHEMA:
{chr(10).join(f"- {c}" for c in target_schema)}

Generate a YAML configuration with the following structure:

yaml sample file
transformations:
  rule_name:
    target_column: <target_field>
    source_column: <source_field>
    # Choose ONE of the following transformation types:
    
    # 1. REGEX extraction (for parsing structured text)
    regex: "<pattern>"
    format: "<output_format>"  # optional, use \\1, \\2 for groups
    
    # 2. CONDITIONAL assignment (for business rules)
    condition: "<regex_pattern>"
    value: "<value_to_assign>"
    
    # 3. MAPPING table (for standardizing values)
    mapping:
      "source_value": "target_value"
      "another_source": "another_target"

settings:
  case_sensitive: false
  skip_empty_values: true
  log_unmatched_rules: false

RULES TO GENERATE:
1. Phone number formatting (extract digits, format as XXX-XXX-XXXX)
2. State code standardization (map full names to 2-letter codes)
3. License status normalization (Active, Inactive, Expired, etc.)
4. Capacity extraction (extract numeric values from text)
5. Age range parsing (extract min/max ages from text like "6 weeks - 12 years")
6. Address cleaning (remove extra spaces, standardize abbreviations)
7. Email validation patterns
8. ZIP code formatting (5-digit or ZIP+4)

Focus on rules that are SPECIFIC to this data schema based on the sample data patterns you observe.
Return ONLY the YAML block, no additional explanation.[3]
"""
        return prompt

    def _parse_logic_response(self, response: str) -> Tuple[Dict, Dict]:
        """
        Parse YAML business logic from LLM response.

        Args:
            response: Raw LLM response text

        Returns:
            Tuple of (transformations dict, settings dict)
        """
        # Extract YAML from code fence if present
        yaml_text = self._extract_yaml(response)

        if not yaml_text:
            logger.warning("Could not extract YAML from LLM response")
            return {}, {}

        try:
            parsed = yaml.safe_load(yaml_text) or {}
            transformations = parsed.get("transformations", {})
            settings = parsed.get("settings", {})

            # Validate the structure
            if not self._validate_logic_structure(transformations):
                logger.warning("Generated logic has invalid structure")
                return {}, {}

            return transformations, settings

        except yaml.YAMLError as e:
            logger.error(f"Failed to parse YAML: {e}")
            return {}, {}

    def _extract_yaml(self, response: str) -> Optional[str]:
        """Extract YAML content from LLM response."""
        # Try fenced code block first
        fenced = re.search(
            r"```(?:yaml|yml)?\s*\n(.*?)```", response, re.DOTALL | re.IGNORECASE
        )
        if fenced:
            return fenced.group(1).strip()

        # Try to find 'transformations:' start
        match = re.search(r"(transformations:\s.*)", response, re.DOTALL)
        if match:
            return match.group(1).strip()

        # Last resort: try entire response
        if "transformations:" in response:
            return response.strip()

        return None

    def _validate_logic_structure(self, transformations: Dict) -> bool:
        """Validate that transformation rules have correct structure."""
        required_fields = {"target_column", "source_column"}
        transformation_types = {"regex", "condition", "mapping"}

        for rule_name, rule in transformations.items():
            # Check required fields
            if not all(field in rule for field in required_fields):
                logger.warning(f"Rule '{rule_name}' missing required fields")
                return False

            # Check that at least one transformation type is present
            if not any(t_type in rule for t_type in transformation_types):
                logger.warning(f"Rule '{rule_name}' missing transformation type")
                return False

        return True
