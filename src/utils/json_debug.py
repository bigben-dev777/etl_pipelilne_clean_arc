"""utils/json_debug.py - Utilities for debugging JSON parsing issues."""

import json
from typing import Optional

from src.utils.logging_config import get_logger

logger = get_logger(__name__)


def debug_json_error(json_text: str, error: json.JSONDecodeError) -> None:
    """
    Provide detailed debugging information for JSON parsing errors.

    Args:
        json_text: The JSON text that failed to parse
        error: The JSONDecodeError exception
    """
    lines = json_text.split("\n")

    # Calculate line and column
    pos = error.pos
    line_num = json_text[:pos].count("\n")
    col_num = pos - json_text[:pos].rfind("\n") - 1

    logger.error("=" * 80)
    logger.error("JSON PARSING ERROR DETAILS")
    logger.error("=" * 80)
    logger.error(f"Error: {error.msg}")
    logger.error(f"Position: {pos} (Line {line_num + 1}, Column {col_num + 1})")
    logger.error("")

    # Show context (3 lines before and after)
    start_line = max(0, line_num - 3)
    end_line = min(len(lines), line_num + 4)

    logger.error("Context:")
    for i in range(start_line, end_line):
        marker = ">>> " if i == line_num else "    "
        logger.error(f"{marker}{i+1:4d} | {lines[i]}")
        if i == line_num:
            # Show pointer to exact position
            logger.error(f"         {' ' * col_num}^")

    logger.error("")
    logger.error("Common issues:")
    logger.error("  - Trailing comma before } or ]")
    logger.error("  - Single backslash in regex (use \\\\)")
    logger.error("  - Unescaped quotes in strings")
    logger.error("  - Missing comma between elements")
    logger.error("=" * 80)


def validate_json_structure(data: dict) -> list[str]:
    """
    Validate JSON structure and return list of issues.

    Args:
        data: Parsed JSON data

    Returns:
        List of validation issues (empty if valid)
    """
    issues = []

    # Check required keys
    required_keys = {"mappings", "transformations", "settings", "confidence"}
    missing_keys = required_keys - set(data.keys())
    if missing_keys:
        issues.append(f"Missing required keys: {missing_keys}")

    # Check mappings
    if "mappings" in data:
        if not isinstance(data["mappings"], dict):
            issues.append("'mappings' must be a dictionary")
        elif not data["mappings"]:
            issues.append("'mappings' is empty")

    # Check transformations
    if "transformations" in data:
        if not isinstance(data["transformations"], dict):
            issues.append("'transformations' must be a dictionary")
        else:
            for rule_name, rule in data["transformations"].items():
                if not isinstance(rule, dict):
                    issues.append(f"Transformation '{rule_name}' must be a dictionary")
                    continue

                # Check required fields
                if "target_column" not in rule:
                    issues.append(
                        f"Transformation '{rule_name}' missing 'target_column'"
                    )
                if "source_column" not in rule:
                    issues.append(
                        f"Transformation '{rule_name}' missing 'source_column'"
                    )

                # Check that at least one transformation type exists
                has_type = any(k in rule for k in ["regex", "mapping", "condition"])
                if not has_type:
                    issues.append(
                        f"Transformation '{rule_name}' missing transformation type"
                    )

    # Check confidence
    if "confidence" in data:
        conf = data["confidence"]
        if not isinstance(conf, (int, float)):
            issues.append("'confidence' must be a number")
        elif not 0.0 <= conf <= 1.0:
            issues.append(f"'confidence' must be between 0.0 and 1.0 (got {conf})")

    return issues
