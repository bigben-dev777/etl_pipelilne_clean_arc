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

        prompt = f"""
You are a data engineering assistant specializing in ETL transformations for **childcare management platforms** (e.g., Brightwheel, Procare, HiMama).

Your task is to generate YAML transformation rules that clean, standardize, and validate data according to **early childhood education (ECE) industry standards** and **US state childcare licensing requirements**.

## BUSINESS CONTEXT

**Industry**: Early Childhood Education / Childcare Facility Management
**Platform Type**: Vertical SaaS (all-in-one center management, parent communication, billing)
**Key Stakeholders**: 
- Center Directors (compliance, enrollment, financial reporting)
- Teachers (attendance, daily reports, ratio compliance)
- Parents (billing, communication, child updates)
- State Agencies (licensing, subsidy reimbursement - CACFP, CCDF)

**Critical Business Rules**:
- **Capacity Management**: Licensed capacity determines maximum enrollment; real-time availability = licensed_capacity - current_enrollment
- **Ratio Compliance**: Staff-to-child ratios vary by age group and state; violations trigger immediate alerts
- **Subsidy Billing**: Multiple payer sources (private pay, state agencies, Head Start) require separate tracking
- **Licensing**: Expired licenses block new enrollments; probations trigger enhanced monitoring

## INPUT DATA

SOURCE COLUMNS:
{chr(10).join(f"- {c}" for c in source_columns)}

SAMPLE DATA (first 5 rows):
{sample_data[:5]}

KNOWN COLUMN MAPPINGS (target -> source):
{chr(10).join(f"- {t} <- {s}" for t, s in mapping.items())}

TARGET SCHEMA:
{chr(10).join(f"- {c}" for c in target_schema)}

## DECISION PROTOCOL (FOLLOW STRICTLY)

When generating rules, use this priority order:
1. **If sample data shows the pattern**: Generate the specific rule based on actual values
2. **If sample data is ambiguous but column exists**: Generate a reasonable default rule with common ECE mappings
3. **If column is missing**: OMIT the rule entirely (do not generate placeholder rules)
4. **NEVER ruminate**: Make a decision in ≤2 reasoning steps and move on

## OUTPUT FORMAT

Generate a YAML configuration with this exact structure:

```yaml
transformations:
  rule_name:
    target_column: <target_field>
    source_column: <source_field>
    # Transformation type (choose ONE):
    regex: "<pattern>"           # For parsing structured text
    format: "<output_format>"    # Optional, use \\1, \\2 for groups
    
    # OR
    
    condition: "<regex_pattern>" # For conditional assignment
    value: "<value_to_assign>"
    
    # OR
    
    mapping:                     # For standardizing values
      "source_value": "target_value"

settings:
  case_sensitive: false
  skip_empty_values: true
  log_unmatched_rules: false
```

## REQUIRED RULES (Generate based on available columns)

### 1. phone_format
**Business Purpose**: SMS notifications for emergencies, billing alerts, and daily updates sent to parents/staff.
**Logic**: Extract digits, format as XXX-XXX-XXXX for standard US dialing.
**Fallback**: If no phone column exists, check for "Contact_Phone", "Mobile", "Cell", or "Emergency_Phone".

### 2. state_standardize
**Business Purpose**: Determines state-specific licensing requirements, subsidy agency routing, and tax calculations.
**Logic**: Map full state names to 2-letter codes (CA, NY, TX, etc.).
**Minimum Mappings** (include all that apply):
  - "California": "CA"
  - "New York": "NY" 
  - "Texas": "TX"
  - "Florida": "FL"
  - "Illinois": "IL"
  - "Oklahoma": "OK"
  - "Pennsylvania": "PA"
  - "Ohio": "OH"
  - "Georgia": "GA"
  - "North Carolina": "NC"
**Add any states found in sample data.**

### 3. license_status_normalize
**Business Purpose**: Controls enrollment permissions and compliance monitoring. Expired/revoked licenses block new registrations.
**Logic**: Normalize to standard status values: Active, Inactive, Expired, Pending, Revoked, Probation.
**Common Mappings**:
  - "Licensed", "Valid", "Current", "Good Standing" → "Active"
  - "Lapsed", "Past Due", "Delinquent" → "Expired"
  - "Suspended", "On Hold" → "Revoked"
  - "Application Submitted", "Under Review" → "Pending"
  - "Conditional", "Monitored" → "Probation"

### 4. capacity_extract
**Business Purpose**: Licensed capacity determines maximum enrollment and revenue potential. Used for real-time availability calculations.
**Logic**: Extract numeric value from text fields.
**Patterns**:
  - "Licensed for 45 children" → 45
  - "Capacity: 30 kids" → 30
  - "20 spaces available" → 20
**Regex**: `(\\d+)\\s*(?:children|kids|child|spaces|capacity|enrollment)`

### 5. age_range_parse
**Business Purpose**: Room assignment (infant/toddler/preschool/school-age) and staff-to-child ratio compliance.
**Logic**: Extract min/max ages from text like "6 weeks - 12 years".
**Conversions**:
  - Weeks to years: divide by 52
  - Months to years: divide by 12
  - "Infant" → 0-1 years
  - "Toddler" → 1-3 years  
  - "Preschool" → 3-5 years
  - "School-age" → 5-12 years
**Output**: min_age (float), max_age (float) in years

### 6. address_clean
**Business Purpose**: Emergency services routing, mail delivery for tax documents (1099-K, W-2), and parent proximity search.
**Logic**: 
  - Trim leading/trailing spaces
  - Standardize abbreviations: St→Street, Ave→Avenue, Rd→Road, Blvd→Boulevard, Dr→Drive, Ln→Lane, Ct→Court, Apt→Apartment, Ste→Suite
  - Normalize directionals: N→North, S→South, E→East, W→West, NE→Northeast, etc.
  - Convert to Title Case

### 7. email_validate
**Business Purpose**: Primary communication channel (95% of parent engagement); used for app login and billing notifications.
**Logic**: 
  - Validate format with regex
  - Lowercase domain for consistency
  - Remove extra spaces
**Regex**: `^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$`

### 8. zip_format
**Business Purpose**: Determines state subsidy eligibility, sales tax rates, and geographic reporting for multi-site chains.
**Logic**: Standardize to 5-digit or ZIP+4 format.
**Patterns**:
  - "12345" → valid
  - "12345-6789" or "123456789" → "12345-6789"
  - "1234" → invalid (flag for review)
**Regex**: `^(\\d{5})(?:-?(\\d{4}))?$`

## ADDITIONAL CHILDcare-SPECIFIC RULES (if applicable columns exist)

### 9. fte_calculate (Full-Time Equivalent)
**Business Purpose**: Billing calculations (part-time vs full-time rates) and staff scheduling.
**Logic**: Convert schedule to FTE (1.0 = full-time, 0.5 = half-day).
**Patterns**: "M-F 8am-5pm" → 1.0, "MWF 9am-12pm" → 0.3

### 10. subsidy_agency_map
**Business Purpose**: Multi-payer billing (private + state agency + Head Start).
**Logic**: Map agency names to standard codes for reconciliation reporting.
**Common**: "DFPS", "CCDF", "Head Start", "Early Head Start"

### 11. immunization_status
**Business Purpose**: Enrollment eligibility and state compliance reporting.
**Logic**: Normalize to: Up to Date, Overdue, Exempt, Incomplete.
**Exemption types**: Medical, Religious, Philosophical (state-dependent)

### 12. enrollment_status
**Business Purpose**: Revenue recognition and capacity planning.
**Logic**: Normalize to: Active, Waitlist, Withdrawn, Graduated, Suspended.
**Business Rules**: 
  - Active counts against capacity
  - Waitlist ordered by date
  - Withdrawn retains financial records for 7 years (IRS)

## CRITICAL CONSTRAINTS

- **DO NOT** second-guess yourself. Generate the YAML immediately after analyzing sample data.
- **If uncertain between two options**, choose the more common ECE industry standard.
- **NEVER** output reasoning or explanation inside the YAML block.
- **If a column is missing**, use the most likely source column name based on KNOWN COLUMN MAPPINGS.
- **Return ONLY the YAML block**, no markdown fences, no conversational text.
- **State-specific variations**: If sample data indicates specific state requirements (e.g., Texas DFPS vs California CCL), prioritize those mappings.

## ANTI-PATTERN WARNING

If you find yourself repeating "But the user might..." or "On the other hand..." more than once, **STOP** and pick the first reasonable option based on standard childcare industry practices.

## EXAMPLE OUTPUT STRUCTURE

```yaml
transformations:
  phone_format:
    target_column: phone
    source_column: Contact_Phone
    regex: "(\\d{3})\\D*(\\d{3})\\D*(\\d{4})"
    format: "\1-\2-\3"
    
  state_standardize:
    target_column: state_code
    source_column: State
    mapping:
      "California": "CA"
      "Texas": "TX"
      "New York": "NY"
      
  license_status_normalize:
    target_column: license_status
    source_column: License_Status
    mapping:
      "Licensed": "Active"
      "Valid": "Active"
      "Lapsed": "Expired"
      "Suspended": "Revoked"

settings:
  case_sensitive: false
  skip_empty_values: true
  log_unmatched_rules: false
```
"""
        return prompt

    def _parse_logic_response(self, response: str) -> Tuple[Dict, Dict]:
        """
        Parse YAML business logic from LLM response.
        Pre-emptively fixes regex escape issues before parsing.
        """
        yaml_text = self._extract_yaml(response)

        if not yaml_text:
            logger.warning("Could not extract YAML from LLM response")
            return {}, {}

        # Always sanitize regex patterns before parsing (safer approach)
        sanitized_yaml = self._sanitize_yaml_regex(yaml_text)

        try:
            parsed = yaml.safe_load(sanitized_yaml) or {}
        except Exception as e:
            logger.error(f"Failed to parse YAML: {e}")
            return {}, {}

        transformations = parsed.get("transformations", {})
        settings = parsed.get("settings", {})

        if not self._validate_logic_structure(transformations):
            logger.warning("Generated logic has invalid structure")
            return {}, {}

        return transformations, settings

    def _sanitize_yaml_regex(self, yaml_text: str) -> str:
        """
        Pre-emptively fix regex patterns in YAML to prevent escape errors.
        Converts double-quoted regex values to single quotes.
        """
        # Pattern: match regex/format/condition keys with double-quoted values
        # Group 1: key and colon with space
        # Group 2: the quoted content
        pattern = re.compile(
            r'((?:regex|format|condition):\s*)\"((?:[^"\\]|\\.)*?)\"', re.IGNORECASE
        )

        def replace_with_single_quotes(match):
            prefix = match.group(1)
            content = match.group(2)

            # In single quotes, only '' is special. Escape single quotes.
            safe_content = content.replace("'", "''")
            return f"{prefix}'{safe_content}'"

        return pattern.sub(replace_with_single_quotes, yaml_text)

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
