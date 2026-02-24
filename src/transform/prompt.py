"""prompt.py - Prompt templates for  schema generation."""

import json
from typing import Dict, List, Optional


class SchemaPromptBuilder:
    """Builds prompts for  schema generation with proper JSON handling."""

    def __init__(self): ...

    def build_prompt(
        self,
        source_columns: List[str],
        target_columns: List[str],
        sample_data: List[Dict],
        metadata: str,
        attempt: int = 1,
    ) -> str:
        """
        Build  prompt requesting JSON output.

        Args:
            source_columns: List of source column names
            target_columns: List of target column names
            sample_data: Sample rows (as list of dicts)
            metadata: Metadata analysis string
            attempt: Current attempt number (for retry emphasis)

        Returns:
            Complete prompt string
        """
        # Build retry emphasis if needed
        retry_section = self._build_retry_emphasis(attempt) if attempt > 1 else ""

        # Safely serialize sample data (handle datetime and other non-JSON types)
        sample_json = self._safe_json_dumps(sample_data[:10])

        # Build config hints section

        prompt = f"""{self.SYSTEM_CONTEXT}

{retry_section}

{self.TASK_DESCRIPTION}

{self.BUSINESS_CONTEXT}

## INPUT DATA

**SOURCE COLUMNS:**
{self._format_list(source_columns)}

**TARGET COLUMNS:**
{self.TARGET_COLUMN_DESCRIPTION}

**SAMPLE DATA (first 10 rows):**
```json
{sample_json}
```

**METADATA ANALYSIS:**
```
{metadata}
```

{self.PREPARE_WORK_CONTEXT}

{self.OUTPUT_FORMAT}

{self.TRANSFORMATION_RULES}

{self.CRITICAL_JSON_RULES}

{self.TRANSFORMATION_CRITICAL_RULES}

{self.DECISION_PROTOCOL}

{self.EXAMPLE_REGEX_PATTERNS}

{self.FINAL_INSTRUCTION}
"""
        return prompt

    def _build_retry_emphasis(self, attempt: int) -> str:
        """Build retry emphasis section for failed attempts."""
        return f"""
⚠️ PREVIOUS ATTEMPT {attempt - 1} FAILED - CRITICAL INSTRUCTIONS:

**Your previous response had parsing errors. Follow these rules EXACTLY:**

1. ❌ DO NOT include any text before the opening `{{`
2. ❌ DO NOT include any text after the closing `}}`
3. ❌ DO NOT use markdown code fences (no ``` markers)
4. ❌ DO NOT add explanations or comments outside the JSON
5. ✅ ENSURE all strings are properly double-quoted: `"value"`
6. ✅ ENSURE all regex patterns use double backslashes: `\\\\d` not `\\d`
7. ✅ ENSURE no trailing commas: `{{"key": "value"}}` not `{{"key": "value",}}`
8. ✅ VALIDATE your JSON is parseable before responding

**Example of CORRECT format:**
```
{{"mappings": {{"company": "Facility_Name"}}, "transformations": {{}}, "settings": {{}}, "confidence": 0.9}}
```

**Example of WRONG format:**
Here's the JSON:
```json
{{"mappings": ...}}
```
"""

    def _safe_json_dumps(self, data: List[Dict], indent: int = 2) -> str:
        """
        Safely serialize data to JSON, handling non-serializable types.

        Common issues:
        - datetime objects
        - Pandas Timestamp objects
        - NaN values
        - Custom objects
        """

        def json_serializer(obj):
            """Custom serializer for non-standard types."""
            # Handle datetime objects
            if hasattr(obj, "isoformat"):
                return obj.isoformat()

            # Handle NaN/Infinity
            if isinstance(obj, float):
                if obj != obj:  # NaN check
                    return None
                if obj == float("inf"):
                    return "Infinity"
                if obj == float("-inf"):
                    return "-Infinity"

            # Handle bytes
            if isinstance(obj, bytes):
                return obj.decode("utf-8", errors="ignore")

            # Fallback: convert to string
            return str(obj)

        try:
            return json.dumps(
                data, indent=indent, default=json_serializer, ensure_ascii=False
            )
        except Exception as e:
            # Last resort: convert everything to strings
            sanitized = self._sanitize_data(data)
            return json.dumps(sanitized, indent=indent, ensure_ascii=False)

    def _sanitize_data(self, data: List[Dict]) -> List[Dict]:
        """Recursively sanitize data by converting problematic types to strings."""
        if isinstance(data, list):
            return [self._sanitize_data(item) for item in data]
        elif isinstance(data, dict):
            return {key: self._sanitize_data(value) for key, value in data.items()}
        elif hasattr(data, "isoformat"):
            return data.isoformat()
        elif isinstance(data, float) and (data != data or abs(data) == float("inf")):
            return None
        elif isinstance(data, (str, int, float, bool, type(None))):
            return data
        else:
            return str(data)

    def _format_list(self, items: List[str]) -> str:
        """Format list as JSON array for consistency."""
        return json.dumps(items, indent=2)

    # ==================== PROMPT SECTIONS ====================

    SYSTEM_CONTEXT = """You are a data engineering assistant specializing in ETL transformations for childcare management platforms (Brightwheel, Procare, HiMama)."""

    TASK_DESCRIPTION = """## TASK

Generate a **STRICT JSON** configuration that includes:
1. **Column Mappings**: Map source columns to target columns
2. **Transformation Rules**: Data cleaning and standardization rules

You MUST return ONLY valid JSON. No markdown, no explanations, no code fences."""

    BUSINESS_CONTEXT = """## BUSINESS CONTEXT

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
- **Licensing**: Expired licenses block new enrollments; probations trigger enhanced monitoring"""

    PREPARE_WORK_CONTEXT = """
## PREPARE WORK

Follow these steps to analyze the source data and plan transformations:

1. **Understand Source Columns**  
   - Look at each source column and decide which target column it corresponds to.  
   - Example: A column with values like "Licensed", "Lapsed", "Suspended" likely maps to "license_status".

2. **Infer Target Values from Source Data**  
   - Check the actual values in the source column to figure out the type of transformation needed.  
   - Example: If a column has full state names ("California", "Texas"), map them to 2-letter codes ("CA", "TX").

3. **Use Metadata for Extra Context**  
   - Look at metadata like data types, unique values, missing counts, and top values.  
   - Example: If the "Phone" column has different formats, plan a rule to normalize all numbers to XXX-XXX-XXXX.  

4. **Plan Transformations**  
   - Decide the transformations needed for each target column: cleaning, normalization, formatting, or extracting numeric values. 
   - Include regex, mappings, and conditional rules where appropriate."""

    OUTPUT_FORMAT = """## OUTPUT FORMAT (STRICT JSON)

Return ONLY a valid JSON object with this EXACT structure:

```json
{
  "mappings": {
    "company": "Facility_Name",
    "facility_type": "Type",
    "address1": "Street_Address",
    "city": "City",
    "state": "State",
    "zip": "Zip_Code",
    "phone": "Contact_Phone",
    "email": "Email_Address"
  },
  "transformations": {
    "phone_format": {
      "target_column": "phone",
      "source_column": "Contact_Phone",
      "regex": "(\\\\d{3})\\\\D*(\\\\d{3})\\\\D*(\\\\d{4})",
      "format": "\\\\1-\\\\2-\\\\3"
    },
    "state_standardize": {
      "target_column": "state",
      "source_column": "State",
      "mapping": {
        "California": "CA",
        "New York": "NY",
        "Texas": "TX",
        "Florida": "FL"
      }
    },
    "license_status_normalize": {
      "target_column": "license_status",
      "source_column": "License_Status",
      "mapping": {
        "Licensed": "Active",
        "Valid": "Active",
        "Lapsed": "Expired",
        "Suspended": "Revoked"
      }
    }
  },
  "settings": {
    "case_sensitive": false,
    "skip_empty_values": true,
    "log_unmatched_rules": false
  },
  "confidence": 0.95
}
```"""

    TRANSFORMATION_RULES = """## REQUIRED TRANSFORMATION RULES

Generate rules for these fields (if source columns exist):
**HAVE TO MAKE TRANSFORMATION FOR TARGET COLUMNS IF THAT MAPPING IS NOT DIRECT MAPPING.**

### 1. phone_format
**Purpose**: SMS notifications for emergencies, billing alerts, and daily updates
**Logic**: Extract digits, format as XXX-XXX-XXXX for standard US dialing
**Regex**: `"(\\\\d{3})\\\\D*(\\\\d{3})\\\\D*(\\\\d{4})"`
**Format**: `"\\\\1-\\\\2-\\\\3"`

### 2. state_standardize
**Purpose**: Determines state-specific licensing requirements, subsidy agency routing, and tax calculations
**Logic**: Map full state names to 2-letter codes
**Required States**: CA, NY, TX, FL, IL, OK, PA, OH, GA, NC (add any states found in sample data)

### 3. license_status_normalize
**Purpose**: Controls enrollment permissions and compliance monitoring
**Logic**: Normalize to standard status values: Active, Inactive, Expired, Pending, Revoked, Probation
**Common Mappings**:
  - "Licensed", "Valid", "Current", "Good Standing" → "Active"
  - "Lapsed", "Past Due", "Delinquent" → "Expired"
  - "Suspended", "On Hold" → "Revoked"
  - "Application Submitted", "Under Review" → "Pending"
  - "Conditional", "Monitored" → "Probation"

### 4. capacity_extract
**Purpose**: Licensed capacity determines maximum enrollment and revenue potential
**Logic**: Extract numeric value from text fields
**Regex**: `"(\\\\d+)\\\\s*(?:children|kids|child|spaces|capacity|enrollment)"`

### 5. email_validate
**Purpose**: Primary communication channel (95% of parent engagement)
**Logic**: Validate format with regex, lowercase domain for consistency
**Regex**: `"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\\\.[a-zA-Z]{2,}$"`

### 6. zip_format
**Purpose**: Determines state subsidy eligibility, sales tax rates, and geographic reporting
**Logic**: Standardize to 5-digit or ZIP+4 format
**Regex**: `"^(\\\\d{5})(?:-?(\\\\d{4}))?$"`

### 7. address_clean
**Purpose**: Emergency services routing, mail delivery for tax documents
**Logic**: Trim spaces, standardize abbreviations (St→Street, Ave→Avenue, Rd→Road, Blvd→Boulevard)"""

    CRITICAL_JSON_RULES = """## CRITICAL JSON RULES

🚨 **MANDATORY REQUIREMENTS:**

1. **Return ONLY the JSON object** - no markdown, no explanations, no code fences
2. **All regex patterns MUST use double backslashes**: `\\\\d` not `\\d`
3. **All strings MUST be double-quoted**: `"value"` not `'value'`
4. **All keys MUST be double-quoted**: `{"key": "value"}`
5. **Confidence MUST be a number between 0.0 and 1.0**
6. **NO trailing commas**: `{"key": "value"}` not `{"key": "value",}`
7. **Ensure valid JSON syntax** - check commas, brackets, quotes
8. **Map ALL available source columns** to their best-matching target columns
9. **Generate transformation rules ONLY for columns that exist in source data**"""

    DECISION_PROTOCOL = """## DECISION PROTOCOL

1. **If sample data shows the pattern**: Generate the specific rule based on actual values
2. **If sample data is ambiguous but column exists**: Generate a reasonable default rule with common ECE mappings
3. **If column is missing**: OMIT the rule entirely (do not generate placeholder rules)
4. **NEVER ruminate**: Make a decision in ≤2 reasoning steps and move on"""

    EXAMPLE_REGEX_PATTERNS = """## EXAMPLE REGEX PATTERNS (COPY THESE EXACTLY)

**Phone Number:**
```json
"regex": "(\\\\d{3})\\\\D*(\\\\d{3})\\\\D*(\\\\d{4})",
"format": "\\\\1-\\\\2-\\\\3"
```

**Email:**
```json
"regex": "^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\\\.[a-zA-Z]{2,}$"
```

**ZIP Code:**
```json
"regex": "^(\\\\d{5})(?:-?(\\\\d{4}))?$",
"format": "\\\\1-\\\\2"
```

**Capacity:**
```json
"regex": "(\\\\d+)\\\\s*(?:children|kids|child|spaces|capacity)"
```

**Digits Only:**
```json
"regex": "\\\\d+"
```"""

    FINAL_INSTRUCTION = """## FINAL INSTRUCTION

Return ONLY the JSON object. Your response should start with `{` and end with `}`. Nothing else."""

    TRANSFORMATION_CRITICAL_RULES = """
## 🔒 TRANSFORMATION RULE SCHEMA (STRICT ENGINE COMPATIBILITY)

Each transformation rule MUST strictly follow the supported execution engine schema.

### ✅ Allowed Rule Types

A rule can use ONE or MULTIPLE of the following transformation methods in combination:

### 1️⃣ Regex Extraction/Formatting

Use when extracting or formatting text patterns.

**Required:**
* `"target_column"` (string)
* `"regex"` (string with regex pattern)

**Optional:**
* `"source_column"` (string)
* `"format"` (string with backreferences like \\1, \\2)

**Example:**

```json
"phone_format": {
  "target_column": "phone",
  "source_column": "Phone",
  "regex": "(\\d{3})\\D*(\\d{3})\\D*(\\d{4})",
  "format": "\\1-\\2-\\3"
}
```

**Rules:**
* If `"format"` exists, it MUST reference regex capture groups (\\1, \\2, etc.)
* Regex MUST use double backslashes for escape sequences
* Without `"format"`, returns first capture group or entire match

---

### 2️⃣ Mapping/Value Substitution

Use when normalizing categorical values or replacing specific values.

**Required:**
* `"target_column"` (string)
* `"mapping"` (dict with key-value pairs)

**Optional:**
* `"source_column"` (string)

**Example:**

```json
"license_status_normalize": {
  "target_column": "license_status",
  "source_column": "Status",
  "mapping": {
    "Licensed": "Active",
    "Valid": "Active",
    "Lapsed": "Expired",
    "Suspended": "Revoked"
  }
}
```

**Rules:**
* Mapping keys must match possible source values
* Output values must conform to controlled vocabulary
* Case sensitivity controlled by settings (default: case-insensitive)

---

### 3️⃣ Conditional Filtering

Use when filtering values based on pattern match, optionally assigning a value.

**Required:**
* `"target_column"` (string)
* `"condition"` (string with regex pattern)

**Optional:**
* `"source_column"` (string)
* `"value"` (string, int, float, or bool - assigns this when condition matches)

**Example:**

```json
"disciplinary_override": {
  "target_column": "license_status",
  "source_column": "Disciplinary Action",
  "condition": "^Y$",
  "value": "Revoked"
}
```

**Rules:**
* `"condition"` must be a valid regex pattern
* Without `"value"`, passes through original value if condition matches
* With `"value"`, assigns that value when condition matches

---

### 4️⃣ Direct Value Assignment

Use when setting a constant value for all rows.

**Required:**
* `"target_column"` (string)
* `"value"` (string, int, float, or bool)

**Example:**

```json
"set_country": {
  "target_column": "country",
  "value": "USA"
}
```

---

## 🔗 COMBINED RULES (Advanced)

The engine supports **combining multiple transformation methods in a single rule**.

### Execution Order (Fixed):
1. **Regex** (extraction/transformation)
2. **Condition** (filtering)
3. **Mapping** (value substitution)

### Valid Combinations:

#### ✅ Regex + Mapping
Extract a value, then map it to a standardized form.

```json
"facility_type_normalize": {
  "target_column": "facility_type",
  "source_column": "Type",
  "regex": "^([A-Z]+)",
  "format": "\\1",
  "mapping": {
    "CENTER": "Childcare Center",
    "GROUP": "Group Home",
    "FAMILY": "Family Childcare"
  }
}
```

**Use case:** Extract facility code, then map to full name.

---

#### ✅ Regex + Condition
Extract a value, then filter based on criteria.

```json
"large_capacity_only": {
  "target_column": "capacity",
  "source_column": "Capacity_Text",
  "regex": "(\\d+)",
  "condition": "\\d{2,}"
}
```

**Use case:** Extract numbers, keep only those with 2+ digits.

---

#### ✅ Condition + Mapping
Filter values, then map the filtered results.

```json
"active_status_map": {
  "target_column": "license_status",
  "source_column": "Status",
  "condition": "Active|Licensed|Valid",
  "mapping": {
    "Active": "Active",
    "Licensed": "Active",
    "Valid": "Active"
  }
}
```

**Use case:** Only process active statuses, then normalize them.

---

#### ✅ Regex + Condition + Mapping
Extract, filter, then map (all three steps).

```json
"facility_type_full_pipeline": {
  "target_column": "facility_type",
  "source_column": "Raw_Type",
  "regex": "([A-Z]+)",
  "condition": "CENTER|GROUP",
  "mapping": {
    "CENTER": "Licensed Childcare Center",
    "GROUP": "Licensed Group Home"
  }
}
```

**Use case:** Extract type code, filter to specific types, map to full names.

---

#### ✅ Condition + Value + Mapping
Filter, assign intermediate value, then map.

```json
"childcare_category": {
  "target_column": "facility_category",
  "source_column": "Type",
  "condition": "CENTER|GROUP|HOME",
  "value": "CHILDCARE",
  "mapping": {
    "CHILDCARE": "Licensed Childcare Provider"
  }
}
```

**Use case:** Standardize multiple types to one value, then map to final category.

---

## 🔄 CROSS-COLUMN DEPENDENCIES

The engine does NOT support multi-column evaluation in a single rule.

**Solution:** Create multiple rules targeting the same column.

**Example:** Combine Status + Disciplinary Action logic:

```json
"license_status_base": {
  "target_column": "license_status",
  "source_column": "Status",
  "mapping": {
    "Active": "Active",
    "Expired": "Expired",
    "Lapsed": "Expired"
  }
},
"disciplinary_override": {
  "target_column": "license_status",
  "source_column": "Disciplinary Action",
  "condition": "^Y$",
  "value": "Revoked"
}
```

**Execution:** Rules apply sequentially. Later rules use `fillna()`, so they only fill NULL values.

**Priority:** First rule takes precedence for non-null values.

---

## 🧠 ENGINE EXECUTION MODEL

### Rule Application Order:
1. Apply all rules in definition order
2. Within each rule, apply transformations in fixed order:
   - Regex → Condition → Mapping
3. Results merge using `fillna()` (preserves existing non-null values)

### Important Behaviors:
* **Earlier rules take priority** - they fill values first
* **Later rules only fill NULLs** - won't overwrite existing values
* **Combined rules execute in sequence** - regex → condition → mapping
* **Case sensitivity** controlled by settings (default: case-insensitive)
* **Empty values** skipped by default (configurable via settings)

---

## 🚨 STRICT CONSTRAINTS

### ✅ DO:
* Use one or more transformation methods per rule (regex, condition, mapping, value)
* Combine compatible methods (see valid combinations above)
* Specify `"source_column"` when rule targets different source than mapping
* Use double backslashes in regex patterns
* Create multiple rules for cross-column logic
* Use descriptive snake_case rule names

### ❌ DO NOT:
* Use SQL expressions
* Write Python code or lambda functions
* Use arithmetic operations or calculations
* Create nested JSON structures beyond the schema
* Use unsupported field names
* Reference multiple source columns in one rule
* Expect rules to overwrite non-null values from earlier rules
* Use single backslashes in regex patterns
* Create empty mappings or conditions

---

## 📋 FIELD REFERENCE

### Required in Every Rule:
* `"target_column"` (string) - The output column name

### Transformation Methods (at least ONE required):
* `"regex"` (string) - Regex pattern for extraction
* `"condition"` (string) - Regex pattern for filtering
* `"mapping"` (dict) - Key-value pairs for substitution
* `"value"` (string/int/float/bool) - Fixed value to assign

### Optional Fields:
* `"source_column"` (string) - Override default source column
* `"format"` (string) - Regex backreference format (requires `"regex"`)
* `"description"` (string) - Human-readable rule description

### Supported Value Types:
* Strings: `"Active"`, `"USA"`
* Integers: `100`, `0`
* Floats: `3.14`, `0.95`
* Booleans: `true`, `false`

---

## 📝 COMPLETE EXAMPLES

### Example 1: Simple Regex Extraction
```json
"extract_license_number": {
  "target_column": "license_number",
  "source_column": "License_ID",
  "regex": "LIC-(\\d+)",
  "format": "\\1",
  "description": "Extract numeric part from license ID"
}
```

### Example 2: Simple Mapping
```json
"normalize_state": {
  "target_column": "state",
  "source_column": "State",
  "mapping": {
    "California": "CA",
    "New York": "NY",
    "Texas": "TX"
  },
  "description": "Convert state names to abbreviations"
}
```

### Example 3: Condition with Value
```json
"flag_revoked": {
  "target_column": "license_status",
  "source_column": "Disciplinary_Action",
  "condition": "Revoked|Suspended|Terminated",
  "value": "Revoked",
  "description": "Mark disciplinary actions as revoked"
}
```

### Example 4: Direct Value Assignment
```json
"set_country": {
  "target_column": "country",
  "value": "USA",
  "description": "Set default country for all records"
}
```

### Example 5: Regex + Mapping
```json
"standardize_phone": {
  "target_column": "phone",
  "source_column": "Contact_Phone",
  "regex": "(\\d{3})\\D*(\\d{3})\\D*(\\d{4})",
  "format": "\\1\\2\\3",
  "mapping": {
    "0000000000": null,
    "1111111111": null
  },
  "description": "Format phone and remove invalid numbers"
}
```

### Example 6: Condition + Mapping
```json
"active_license_types": {
  "target_column": "license_type",
  "source_column": "Credential_Type",
  "condition": "Family|Center|Group",
  "mapping": {
    "Family": "Family Childcare",
    "Center": "Childcare Center",
    "Group": "Group Home"
  },
  "description": "Process only active license types"
}
```

### Example 7: Full Pipeline (Regex + Condition + Mapping)
```json
"capacity_categorization": {
  "target_column": "capacity_category",
  "source_column": "Max_Capacity",
  "regex": "(\\d+)",
  "condition": "^\\d+$",
  "mapping": {
    "1": "Small",
    "2": "Small",
    "3": "Small",
    "4": "Small",
    "5": "Small",
    "6": "Medium",
    "7": "Medium",
    "8": "Medium",
    "9": "Medium",
    "10": "Medium"
  },
  "description": "Extract capacity number, validate, categorize"
}
```

### Example 8: Multi-Rule Cross-Column Logic
```json
"base_license_status": {
  "target_column": "license_status",
  "source_column": "Status",
  "mapping": {
    "Active": "Active",
    "Licensed": "Active",
    "Valid": "Active",
    "Expired": "Expired",
    "Lapsed": "Expired",
    "Inactive": "Inactive"
  },
  "description": "Base status normalization"
},
"disciplinary_status_override": {
  "target_column": "license_status",
  "source_column": "Disciplinary_Action",
  "condition": "Y|Yes|True",
  "value": "Revoked",
  "description": "Override status if disciplinary action exists"
},
"probation_status_override": {
  "target_column": "license_status",
  "source_column": "Probation_Flag",
  "condition": "Y|Yes|True",
  "value": "Probation",
  "description": "Override status if on probation"
}
```

**Execution order:** Rules apply sequentially, but only fill NULL values.

---

## ⚙️ SETTINGS CONFIGURATION

Control transformation behavior with these settings:

```json
"settings": {
  "case_sensitive": false,
  "skip_empty_values": true,
  "log_unmatched_rules": false,
  "trim_whitespace": true,
  "normalize_case": false
}
```

### Setting Descriptions:

* **`case_sensitive`** (bool, default: `false`)
  - Controls regex and mapping matching
  - `false`: "active" matches "Active", "ACTIVE"
  - `true`: Exact case match required

* **`skip_empty_values`** (bool, default: `true`)
  - Skip processing of empty/null values
  - `true`: Empty strings and null values return null
  - `false`: Process all values including empty strings

* **`log_unmatched_rules`** (bool, default: `false`)
  - Log when rules don't match any values
  - Useful for debugging mapping coverage

* **`trim_whitespace`** (bool, default: `true`)
  - Remove leading/trailing whitespace before processing
  - Recommended for cleaner matching

* **`normalize_case`** (bool, default: `false`)
  - Convert all values to lowercase before processing
  - Use with `case_sensitive: false` for maximum flexibility

---

## 🎯 DECISION FLOWCHART

```
Need to transform a column?
│
├─ Fixed value for all rows?
│  └─ Use: value assignment
│
├─ Extract pattern from text?
│  ├─ Just extract?
│  │  └─ Use: regex
│  ├─ Extract then normalize?
│  │  └─ Use: regex + mapping
│  └─ Extract then filter?
│     └─ Use: regex + condition
│
├─ Normalize categorical values?
│  ├─ All values?
│  │  └─ Use: mapping
│  └─ Only specific values?
│     └─ Use: condition + mapping
│
├─ Filter based on pattern?
│  ├─ Keep original values?
│  │  └─ Use: condition (no value)
│  └─ Assign new value?
│     └─ Use: condition + value
│
└─ Complex multi-step?
   └─ Use: regex + condition + mapping
```

---

## ✅ VALIDATION CHECKLIST

Before submitting transformation rules, verify:

- [ ] Every rule has `"target_column"`
- [ ] At least one transformation method specified (regex/condition/mapping/value)
- [ ] `"format"` only used with `"regex"`
- [ ] Regex patterns use double backslashes (`\\d`)
- [ ] Mapping dictionaries are non-empty
- [ ] Source columns exist in the source data
- [ ] Target columns exist in target schema
- [ ] Rule names are descriptive and snake_case
- [ ] No SQL, Python code, or arithmetic expressions
- [ ] No multi-column references in single rule
- [ ] Settings use valid keys and boolean values
- [ ] Combined rules follow valid combination patterns

---

## 🚫 INVALID EXAMPLES (DO NOT USE)

### ❌ Multi-column expression
```json
// WRONG - Cannot reference multiple columns
"combined_address": {
  "target_column": "full_address",
  "expression": "address1 + ', ' + city + ', ' + state"
}
```

### ❌ Arithmetic operation
```json
// WRONG - No arithmetic support
"capacity_doubled": {
  "target_column": "capacity",
  "operation": "multiply",
  "factor": 2
}
```

### ❌ Python code
```json
// WRONG - No Python code execution
"custom_logic": {
  "target_column": "status",
  "function": "lambda x: 'Active' if x == 'Y' else 'Inactive'"
}
```

### ❌ Nested conditions
```json
// WRONG - No nested logic support
"complex_rule": {
  "target_column": "status",
  "if": {
    "condition": "Active",
    "then": {
      "if": {"condition": "Y", "value": "Revoked"}
    }
  }
}
```

### ❌ Empty mapping
```json
// WRONG - Mapping cannot be empty
"state_map": {
  "target_column": "state",
  "mapping": {}
}
```

### ❌ Format without regex
```json
// WRONG - Format requires regex
"format_only": {
  "target_column": "phone",
  "format": "\\1-\\2-\\3"
}
```

---

## 📚 SUMMARY

**Supported Rule Types:**
1. Regex extraction/formatting
2. Value mapping/substitution
3. Conditional filtering
4. Direct value assignment
5. Combined transformations (regex + condition + mapping)

**Key Principles:**
* One rule = one or more transformation methods
* Rules apply sequentially
* Later rules only fill NULL values (use `fillna()`)
* Cross-column logic requires multiple rules
* Fixed execution order: regex → condition → mapping

**Remember:** If transformation cannot be expressed within these constraints, omit it. The engine is designed for data normalization, not complex business logic.
"""
    TARGET_COLUMN_DESCRIPTION = """
# Target Column Descriptions - Detailed Specification

## company
**Description:** Facility or business legal operating name.

**Data Type:** VARCHAR

**Requirements:** Required field

**Validation Rules:**
- Must be a trimmed string with no leading or trailing whitespace
- Should contain only the legal business name as registered with the state
- Must NOT contain license status indicators such as "Licensed", "Active", "Registered", etc.
- Should not include business entity suffixes unless part of the official name (e.g., "ABC Daycare LLC" is acceptable if that's the legal name)
- Empty strings are not permitted
- Special characters are allowed if part of the legal name

**Examples:**
- Valid: "Sunshine Learning Center", "Little Stars Preschool", "ABC Child Development LLC"
- Invalid: "Sunshine Learning Center - Licensed", "  Little Stars Preschool  ", ""

---

## facility_type
**Description:** Categorical value describing the classification or type of childcare facility.

**Data Type:** VARCHAR

**Requirements:** Optional but strongly recommended

**Validation Rules:**
- Should use controlled vocabulary from a standardized list when possible
- Common values include: "Center", "Family Child Care", "Group Home", "Preschool", "Head Start", "School-Age Program", "Nursery School", "Montessori School"
- Case-insensitive but should be stored in title case
- If source data uses non-standard terminology, map to closest standard category

**Examples:**
- Valid: "Center", "Family Child Care", "Group Home"
- Acceptable variations: "Child Care Center" → "Center", "Family Day Care" → "Family Child Care"

---

## address1
**Description:** Primary street address line containing the physical location of the facility.

**Data Type:** VARCHAR

**Requirements:** Required field

**Validation Rules:**
- Should NOT contain ZIP code

**Examples:**
- Valid: "123 Main Street", "456 Oak Ave", "789 N Elm Blvd"
---

## address2
**Description:** Secondary address information for additional location details within a building or complex.

**Data Type:** VARCHAR

**Requirements:** Nullable (optional)

**Validation Rules:**
- ONLY If source data has secondary address information, it should be stored here

**Examples:**
- Valid: "Suite 200", "Unit B", "Apt 3", "Building 2", "Floor 3", "#205"
- Invalid: "123 Main Street"

---

## city
**Description:** City or municipality name derived from the facility's physical address.

**Data Type:** VARCHAR

**Requirements:** Required field

**Validation Rules:**
- Must be properly capitalized (title case preferred)
- Should NOT contain state abbreviations or ZIP codes
- Should NOT contain county information
- Multi-word cities should preserve spacing (e.g., "San Francisco", "New York")
- Hyphens should be preserved for hyphenated city names (e.g., "Winston-Salem")
- Must be trimmed of leading/trailing whitespace
- Empty strings are not permitted

**Examples:**
- Valid: "Boston", "San Francisco", "New York", "Winston-Salem"
- Invalid: "BOSTON", "boston", "Boston, MA", "Boston 02101", "Boston, Suffolk County"

---

## state
**Description:** Two-letter USPS state abbreviation identifying the state where the facility is located.

**Data Type:** VARCHAR(2)

**Requirements:** Required field

**Validation Rules:**
- Must be exactly 2 characters
- Must be uppercase
- Must be a valid USPS state abbreviation (includes 50 states + DC, PR, VI, GU, AS, MP)
- No periods or other punctuation
- Must be trimmed of leading/trailing whitespace

**Examples:**
- Valid: "CA", "TX", "NY", "DC", "PR"
- Invalid: "ca", "California", "Ca", "C.A.", "CAL"

---

## zip
**Description:** United States Postal Service ZIP code or ZIP+4 code.

**Data Type:** VARCHAR

**Requirements:** Required field

**Validation Rules:**
- Must match regex pattern: ^\\d{5}(-\\d{4})?$
- Can be either 5-digit format (e.g., "12345") or 9-digit ZIP+4 format (e.g., "12345-6789")
- If ZIP+4 format is used, must include hyphen separator
- No spaces allowed
- Must be numeric digits only (plus optional hyphen)
- Leading zeros must be preserved (e.g., "01234" not "1234")

**Examples:**
- Valid: "90210", "02134", "10001-1234"
- Invalid: "9021", "902101", "90210 1234", "90210-123"

---

## county
**Description:** County or parish name where the facility is located.

**Data Type:** VARCHAR

**Requirements:** Nullable (optional)

**Validation Rules:**
- Should contain only the county name WITHOUT suffix
- Do NOT include "County", "Parish", "Borough", or similar suffixes
- Should be properly capitalized (title case)
- Multi-word counties should preserve spacing (e.g., "Los Angeles", "San Diego")
- If source data includes suffix, it should be stripped during processing
- NULL is acceptable if county information is not available

**Examples:**
- Valid: "Orange", "Los Angeles", "Cook", "Miami-Dade"
- Invalid: "Orange County", "Los Angeles County", "Cook Co."

---

## phone
**Description:** Primary contact phone number for the facility.

**Data Type:** VARCHAR

**Requirements:** Optional but strongly recommended

**Validation Rules:**
- Should be normalized to one of two formats:
  - Digits only: "1234567890" or "11234567890" (with country code)
  - Standard format: "(123) 456-7890" or "123-456-7890"
- Must contain 10 digits (US) or 11 digits (with country code 1)
- Remove all non-numeric characters except those in standard format (parentheses, hyphens, spaces)
- Extensions should be stored separately or appended with "ext" or "x" (e.g., "(123) 456-7890 ext 123")
- International numbers should include country code
- NULL is acceptable if phone number is not available

**Examples:**
- Valid: "1234567890", "(123) 456-7890", "123-456-7890", "(123) 456-7890 ext 123"
- Invalid: "123-4567" (incomplete), "abc-defg-hijk" (non-numeric)

---

## phone2
**Description:** Secondary or alternative contact phone number for the facility.

**Data Type:** VARCHAR

**Requirements:** Nullable (optional)

**Validation Rules:**
- YOU DON'T HAVE TO USE THIS FIELD UNLESS SOURCE DATA INCLUDES A SECONDARY PHONE NUMBER
- YOU HAVE TO USE **DIFFERENT COLUMN MAPPING** WITH phone COLUMN IN SOURCE DATA
- Same normalization rules as phone field
- Should be used for alternate contact numbers (e.g., director's cell, fax, emergency line)
- Must be different from phone field value
- NULL is acceptable and expected when no secondary number exists

**Examples:**
- Valid: "9876543210", "(987) 654-3210", NULL
- Invalid: Same value as phone field

---

## email
**Description:** Primary contact email address for the facility.

**Data Type:** VARCHAR

**Requirements:** Nullable (optional)

**Validation Rules:**
- Must match basic email regex validation pattern: ^[^\\s@]+@[^\\s@]+\\.[^\\s@]+$
- Should be stored in lowercase for consistency
- Must contain exactly one @ symbol
- Domain must contain at least one period
- No leading or trailing whitespace
- Should be a valid, deliverable email address when possible
- NULL is acceptable if email is not available

**Examples:**
- Valid: "info@sunshinelearning.com", "director@littlestars.org", "contact123@daycare.net"
- Invalid: "notanemail", "@example.com", "user@", "user @example.com"

---

## website_address
**Description:** Facility's official website URL.

**Data Type:** VARCHAR

**Requirements:** Nullable (optional)

**Validation Rules:**
- YOU DON'T HAVE TO USE THIS FIELD UNLESS SOURCE DATA INCLUDES A WEBSITE URL
- Should include URL scheme (protocol): http:// or https://
- If source data lacks scheme, prepend "https://" by default
- Should be a complete, valid URL
- Should not contain spaces
- Should be stored in lowercase for consistency
- Trailing slashes are optional but should be consistent
- NULL is acceptable if website does not exist

**Examples:**
- Valid: "https://www.sunshinelearning.com", "http://littlestars.org", "https://daycare.example.com/location1"
- Invalid: "www.example.com" (missing scheme), "https://example .com" (contains space)

---

## first_name
**Description:** First (given) name of the primary contact person at the facility.

**Data Type:** VARCHAR

**Requirements:** Nullable (optional)

**Validation Rules:**
- THIS FIELD CONTENT MUST LIKE HUMEN'S NAME, NOT COMPANY
- Should NOT include titles such as Mr., Mrs., Ms., Dr., Rev., etc.
- Should NOT include middle names or initials (unless culturally appropriate)
- Should be properly capitalized (title case)
- Hyphens and apostrophes are acceptable for names like "Mary-Jane" or "O'Brien"
- Should contain only alphabetic characters, hyphens, and apostrophes
- NULL is acceptable if contact name is not available

**Examples:**
- Valid: "John", "Mary", "Mary-Jane", "O'Brien"
- Invalid: "Dr. John", "JOHN", "John Smith" (includes last name), "John M." (includes middle initial)

---

## last_name
**Description:** Last (family/sur) name of the primary contact person at the facility.

**Data Type:** VARCHAR

**Requirements:** Nullable (optional)

**Validation Rules:**
- Should be properly capitalized (title case)
- Should NOT include titles or suffixes (Jr., Sr., III, etc.) unless they are legally part of the surname
- Hyphens, apostrophes, and spaces are acceptable for compound surnames
- Should contain only alphabetic characters, hyphens, apostrophes, and spaces
- NULL is acceptable if contact name is not available

**Examples:**
- Valid: "Smith", "O'Brien", "Van Der Berg", "Smith-Jones"
- Invalid: "SMITH", "Smith Jr." (suffix should be separate), "Dr. Smith" (includes title)

---

## capacity
**Description:** Maximum number of children the facility is licensed or authorized to serve at any given time.

**Data Type:** NUMERIC (INTEGER)

**Requirements:** Optional but strongly recommended

**Validation Rules:**
- Must be a non-negative integer (>= 0)
- Represents TOTAL facility capacity, not per-classroom or per-age-group capacity
- Should reflect the licensed capacity, not current enrollment
- Zero is acceptable for facilities that are licensed but not yet operational
- NULL is acceptable if capacity information is not available
- Should not include decimal values

**Examples:**
- Valid: 0, 12, 50, 150
- Invalid: -5, 12.5, "twelve"

---

## min_age
**Description:** Minimum age of children served by the facility.

**Data Type:** NUMERIC (DECIMAL or INTEGER)

**Requirements:** Nullable (optional)

**Validation Rules:**
- Must be a non-negative number (>= 0)
- Default unit is MONTHS unless otherwise standardized for the dataset
- Must be less than or equal to max_age if both are provided
- Zero is acceptable and indicates infants from birth
- Decimal values are acceptable for precise age ranges (e.g., 1.5 months = 6 weeks)
- NULL is acceptable if minimum age is not specified
- If using weeks or years, should be converted to months for consistency

**Examples:**
- Valid: 0 (birth), 1.5 (6 weeks), 6 (6 months), 12 (1 year)
- Invalid: -6, value greater than max_age

---

## max_age
**Description:** Maximum age of children served by the facility.

**Data Type:** NUMERIC (DECIMAL or INTEGER)

**Requirements:** Nullable (optional)

**Validation Rules:**
- Must be a non-negative number (>= 0)
- Default unit is MONTHS unless otherwise standardized for the dataset
- Must be greater than or equal to min_age if both are provided
- Decimal values are acceptable for precise age ranges
- NULL is acceptable if maximum age is not specified
- Common values: 60 (5 years), 72 (6 years), 156 (13 years for school-age programs)
- If using weeks or years, should be converted to months for consistency

**Examples:**
- Valid: 60 (5 years), 72 (6 years), 156 (13 years)
- Invalid: -12, value less than min_age

---

## ages_served
**Description:** Free-text description of the age range of children served by the facility.

**Data Type:** VARCHAR

**Requirements:** Nullable (optional)

**Validation Rules:**
- Used when structured min_age/max_age fields are not available or when source provides text description
- Should preserve original formatting and units from source data
- Common formats: "6 weeks to 5 years", "Infants through Pre-K", "Birth to 12 years"
- Should be trimmed of leading/trailing whitespace
- NULL is acceptable, especially if min_age and max_age are populated
- Can coexist with min_age/max_age fields for additional context

**Examples:**
- Valid: "6 weeks to 5 years", "Infants and Toddlers", "Birth through Pre-Kindergarten", "2-12 years"
- Acceptable: Any text description that conveys age range information

---

## license_status
**Description:** Current status of the facility's license or authorization to operate.

**Data Type:** VARCHAR

**Requirements:** Optional but strongly recommended

**Validation Rules:**
- SHOULD be NORMARLIZED to controlled vocabulary when possible
- Common standard values: "Licensed", "Active", "Registered", "Probationary", "Suspended", "Revoked", "Expired", "Closed", "Pending", "Exempt"
- Should be stored in title case for consistency
- Should reflect the most current status available from source data
- NULL is acceptable if status information is not available
- Map source-specific terminology to standard values when possible

**Examples:**
- Valid: "Licensed", "Active", "Probationary", "Suspended", "Revoked", "Closed"
- Map: "In Good Standing" → "Licensed", "Not Active" → "Closed"

---

## license_number
**Description:** Official state-issued license, permit, or credential identification number.

**Data Type:** VARCHAR(consistant with NUMBER AND SYMBOLS, OR SOMETIMES WITH CAPITAL LETTERS)

**Requirements:** Required if license_status indicates an active license (e.g., "Licensed", "Active", "Probationary")

**Validation Rules:**
- Should be stored exactly as issued by the regulatory authority
- May contain alphanumeric characters, hyphens, and other special characters
- Should be trimmed of leading/trailing whitespace
- Should NOT be reformatted or normalized unless required for consistency
- Preserve leading zeros if present
- NULL is acceptable only if license_status is "Exempt", "Pending", "Closed", or similar non-licensed status
- Should be unique within a state, though duplicates may exist across states

**Examples:**
- Valid: "123456", "ABC-123-456", "2024-FL-001234", "L123456789"
- Invalid: Empty string when license_status is "Licensed"

---

## license_type
**Description:** Type or category of license issued by the state regulatory authority.

**Data Type:** VARCHAR

**Requirements:** Nullable (optional)

**Validation Rules:**
- Should align with facility_type but may differ based on state-specific licensing categories
- Common values: "Child Care Center", "Family Child Care Home", "Group Child Care Home", "School-Age Program", "Preschool", "Exempt School"
- Should reflect the official license category from the regulatory authority
- Should be stored in title case for consistency
- NULL is acceptable if license type information is not available
- May be more specific than facility_type (e.g., facility_type="Center", license_type="Infant/Toddler Center")

**Examples:**
- Valid: "Child Care Center", "Family Child Care Home", "School-Age Program", "Infant/Toddler Center"
- Note: This may differ from facility_type based on state-specific terminology

---

# General Notes

**Data Quality Standards:**
- All VARCHAR fields should be trimmed of leading and trailing whitespace
- NULL should be used for missing data rather than empty strings (unless specified otherwise)
- Consistency in capitalization and formatting should be maintained across all records
- Source data should be validated against these specifications during ETL processing

**State-Specific Variations:**
- Some fields may have state-specific requirements or terminology
- Mapping tables should be maintained for state-specific values to standard vocabulary
- Documentation should note any state-specific deviations from these standards

**Data Lineage:**
- Original source values should be preserved in separate columns if significant transformation is required
- Transformation logic should be documented for audit purposes
"""
