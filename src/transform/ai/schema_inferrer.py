"""AI-powered schema inference for unknown data sources."""

import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from src.transform.ai.llm_client import LLMClient

logger = logging.getLogger(__name__)


class SchemaInferrer:
    """
    Infer schema mappings for unknown data sources using LLM.
    """

    # Target schema with descriptions
    TARGET_SCHEMA = {
        "company": "Facility/business name",
        "facility_type": "Type of facility (center, family care, etc.)",
        "address1": "Street address line 1",
        "address2": "Street address line 2 (apt, suite, etc.)",
        "city": "City name",
        "state": "State abbreviation (2-letter)",
        "zip": "ZIP code (5-digit)",
        "county": "County name",
        "phone": "Primary phone number",
        "phone2": "Secondary phone number",
        "email": "Email address",
        "website_address": "Website URL",
        "first_name": "Contact person first name",
        "last_name": "Contact person last name",
        "capacity": "Maximum number of children (numeric)",
        "min_age": "Minimum age served (in years, numeric)",
        "max_age": "Maximum age served (in years, numeric)",
        "ages_served": "Original age range description (text)",
        "license_status": "License status (Active/Inactive/Expired/etc.)",
        "license_number": "License/credential number",
        "license_type": "Type of license",
    }

    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
        use_llm: bool = True,
        confidence_threshold: float = 0.7,
    ):
        """
        Initialize the schema inferrer.

        Args:
            llm_client: LLM client for inference
            use_llm: Whether to use LLM (vs rule-based only)
            confidence_threshold: Minimum confidence for accepting LLM mappings
        """
        self.llm_client = llm_client
        self.use_llm = use_llm
        self.confidence_threshold = confidence_threshold
        self._inference_cache: Dict[str, Dict[str, Any]] = {}

    def infer_mapping(
        self,
        source_columns: List[str],
        sample_data: List[Dict[str, Any]],
        use_cache: bool = True,
    ) -> Dict[str, Any]:
        """
        Infer column mapping for unknown schema.

        Args:
            source_columns: List of source column names
            sample_data: Sample rows from the source
            use_cache: Whether to use caching

        Returns:
            Mapping result with mappings, confidence, and notes
        """
        if not source_columns:
            return {"mappings": {}, "confidence": 0.0, "error": "no_columns"}

        # Check cache
        cache_key = self._compute_cache_key(source_columns)
        if use_cache and cache_key in self._inference_cache:
            logger.debug("Using cached schema inference")
            return self._inference_cache[cache_key]

        # Try LLM inference
        if self.use_llm and self.llm_client:
            result = self._infer_with_llm(source_columns, sample_data)
        else:
            result = self._infer_with_rules(source_columns)

        # Cache result
        if use_cache:
            self._inference_cache[cache_key] = result

        return result

    def _infer_with_llm(
        self, source_columns: List[str], sample_data: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Infer mapping using LLM."""
        # Build prompt
        prompt = self._build_inference_prompt(source_columns, sample_data)

        try:
            response = self.llm_client.complete(prompt)

            # Parse response
            result = self._parse_inference_response(response)

            # Validate mappings
            result = self._validate_mappings(result, source_columns)

            logger.info(
                f"LLM schema inference confidence: {result.get('confidence', 0)}"
            )

            return result

        except Exception as e:
            logger.warning(f"LLM schema inference failed: {e}, falling back to rules")
            return self._infer_with_rules(source_columns)

    def _build_inference_prompt(
        self, source_columns: List[str], sample_data: List[Dict[str, Any]]
    ) -> str:
        """Build prompt for schema inference."""
        # Format target schema
        target_desc = "\n".join(
            f"- {col}: {desc}" for col, desc in self.TARGET_SCHEMA.items()
        )

        # Format sample data (limit to 3 rows)
        sample_rows = sample_data[:3] if sample_data else []
        sample_str = (
            json.dumps(sample_rows, indent=2, default=str)
            if sample_rows
            else "No sample data available"
        )

        prompt = f"""
You are a senior data engineer specializing in schema mapping, data normalization, and entity modeling.

Your task is to analyze the source dataset and map it into the standardized target schema.

You must reason about:
- Business meaning (not just column name similarity)
- Sample values and embedded semantics
- Combined or composite fields
- Derived fields (e.g., extracting license numbers from names)
- Data normalization requirements
- Entity relationships (license vs facility vs contact vs subsidy)
- Data quality risks
- Units (months vs years)
- Deterministic vs inferred mappings

TARGET SCHEMA (canonical facility table):
{target_desc}

SOURCE COLUMNS:
{chr(10).join(f"- {col}" for col in source_columns)}

SAMPLE DATA (first 3 rows):
{sample_str}

Instructions:

1. Map each target column to:
   - a single source column
   - OR multiple source columns (if combination required)
   - OR "DERIVED"
   - OR "NULL"
   - OR "NOT PRESENT"

2. If a source column contains multiple logical attributes 
   (e.g., "CHILD CARE FAMILY - K820055232"),
   explicitly describe how it should be parsed.

3. Identify:
   - Fields requiring string splitting
   - Fields requiring regex extraction
   - Fields requiring normalization
   - Fields requiring unit conversion
   - Fields requiring lookup/enrichment

4. If mapping requires assumptions, explicitly state them.

5. Detect if the source contains attributes that belong in a separate entity 
   (e.g., subsidy, monitoring, quality rating, operating hours).

6. Do NOT hallucinate missing data.

7. Prioritize semantic correctness over name similarity.

Return your answer strictly as valid JSON using the following structure:
{{ 
    "mappings": {{ "target_column": "source_column", ... }}, 
    "special_handling": {{ "source_column": "description of special handling needed" }}, 
    "confidence": 0.0-1.0, 
    "notes": "any important observations about the data" 
}}
"""

        # {{
        #   "target_mappings": {{
        #     "target_column": {{
        #       "source": "source_column | [list_of_columns] | DERIVED | NULL | NOT PRESENT",
        #       "transformation": "clear description of required transformation",
        #       "confidence": 0.0
        #     }}
        #   }},
        #   "excluded_source_columns": [
        #     {{
        #       "column": "source_column",
        #       "reason": "why it does not belong in this target schema"
        #     }}
        #   ],
        #   "parsing_rules": [
        #     "explicit deterministic transformation rules"
        #   ],
        #   "entity_model_observations": [
        #     "identify if source contains multiple entities mixed in one row"
        #   ],
        #   "data_quality_risks": [
        #     "possible inconsistencies or ambiguity"
        #   ],
        #   "overall_confidence": 0.0
        # }}
        print("💥" * 10)
        print("LLM Inference Prompt:", prompt)
        return prompt

    def _parse_inference_response(self, response: str) -> Dict[str, Any]:
        """Parse LLM inference response."""
        try:
            # Extract JSON
            json_match = re.search(r"\{.*\}", response, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())

                return {
                    "mappings": data.get("mappings", {}),
                    "special_handling": data.get("special_handling", {}),
                    "confidence": data.get("confidence", 0.5),
                    "notes": data.get("notes", ""),
                }

        except json.JSONDecodeError:
            logger.warning("Could not parse LLM inference response as JSON")

        return {"mappings": {}, "confidence": 0.0, "error": "parse_failed"}

    def _validate_mappings(
        self, result: Dict[str, Any], source_columns: List[str]
    ) -> Dict[str, Any]:
        """Validate and clean inferred mappings."""
        mappings = result.get("mappings", {})

        # Remove mappings to non-existent columns
        valid_mappings = {}
        source_lower = [col.lower() for col in source_columns]

        for target, source in mappings.items():
            if source.lower() in source_lower:
                # Find the actual case-sensitive column name
                for col in source_columns:
                    if col.lower() == source.lower():
                        valid_mappings[target] = col
                        break

        result["mappings"] = valid_mappings

        # Recalculate confidence based on coverage
        coverage = len(valid_mappings) / len(self.TARGET_SCHEMA)
        result["coverage"] = round(coverage, 2)

        return result

    def _infer_with_rules(self, source_columns: List[str]) -> Dict[str, Any]:
        """Infer mapping using rule-based fuzzy matching."""
        from rapidfuzz import fuzz

        mappings = {}

        # Common patterns
        patterns = {
            "company": [
                "name",
                "facility",
                "provider",
                "operation",
                "organization",
                "business",
            ],
            "phone": ["phone", "tel", "telephone", "contact", "mobile"],
            "email": ["email", "e-mail", "mail"],
            "address1": ["address", "street", "addr", "location"],
            "city": ["city", "town"],
            "state": ["state", "province", "st"],
            "zip": ["zip", "postal", "zipcode", "postcode"],
            "capacity": ["capacity", "cap", "max", "total", "size"],
            "license_number": ["license", "credential", "permit", "certification"],
            "license_status": ["status", "state"],
        }

        for target, possible_names in patterns.items():
            best_match = None
            best_score = 0

            for source_col in source_columns:
                source_lower = source_col.lower().strip()

                # Direct match
                if source_lower == target.lower():
                    best_match = source_col
                    best_score = 1.0
                    break

                # Check against patterns
                for pattern in possible_names:
                    score = fuzz.ratio(source_lower, pattern) / 100
                    if score > best_score and score >= 0.80:
                        best_match = source_col
                        best_score = score

            if best_match:
                mappings[target] = best_match

        coverage = len(mappings) / len(self.TARGET_SCHEMA)

        return {
            "mappings": mappings,
            "special_handling": {},
            "confidence": round(coverage, 2),
            "coverage": round(coverage, 2),
            "notes": "Rule-based inference",
            "source": "rules",
        }

    def _compute_cache_key(self, source_columns: List[str]) -> str:
        """Compute cache key for source columns."""
        normalized = "|".join(sorted(col.lower().strip() for col in source_columns))
        import hashlib

        return hashlib.sha256(normalized.encode()).hexdigest()[:16]

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get inference cache statistics."""
        return {
            "cache_size": len(self._inference_cache),
            "cached_schemas": list(self._inference_cache.keys()),
        }
