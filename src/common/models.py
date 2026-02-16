from typing import Any, Dict, Optional, Union

from pydantic import BaseModel, Field, field_validator, model_validator


class TransformationRule(BaseModel):
    """Schema for a single transformation rule."""

    target_column: str
    source_column: Optional[str] = None
    regex: Optional[str] = None
    format: Optional[str] = None
    condition: Optional[str] = None
    value: Optional[Union[str, int, float, bool]] = None
    mapping: Optional[Dict[str, Union[str, int, float, bool]]] = None
    description: Optional[str] = None

    @field_validator("regex", "format", "condition")
    @classmethod
    def validate_strings(cls, v):
        """Ensure string fields are actually strings."""
        if v is not None and not isinstance(v, str):
            raise ValueError("Must be a string")
        return v

    @field_validator("target_column")
    @classmethod
    def validate_target_column(cls, v):
        """Ensure target_column is non-empty."""
        if not v or not isinstance(v, str):
            raise ValueError("target_column must be a non-empty string")
        return v

    @field_validator("source_column")
    @classmethod
    def validate_source_column(cls, v):
        """Ensure source_column is valid if provided."""
        if v is not None and (not isinstance(v, str) or not v.strip()):
            raise ValueError("source_column must be a non-empty string if provided")
        return v

    @field_validator("mapping")
    @classmethod
    def validate_mapping(cls, v):
        """Ensure mapping is a non-empty dict if provided."""
        if v is not None:
            if not isinstance(v, dict):
                raise ValueError("mapping must be a dictionary")
            if len(v) == 0:
                raise ValueError("mapping must not be empty")
        return v

    @model_validator(mode="after")
    def validate_rule_completeness(self):
        """Ensure at least one transformation method is specified."""
        has_regex = self.regex is not None
        has_condition = self.condition is not None
        has_mapping = self.mapping is not None
        has_value = self.value is not None

        # At least one transformation method must be present
        if not (has_regex or has_condition or has_mapping or has_value):
            raise ValueError(
                "Rule must specify at least one of: regex, condition, mapping, or value"
            )

        # Validate regex format compatibility
        if self.format is not None and self.regex is None:
            raise ValueError("format can only be used with regex")

        # Note: condition + value + mapping IS valid
        # Execution order: condition filters → value assigns → mapping transforms

        return self


class SchemaOutput(BaseModel):
    """Schema for the complete output."""

    mappings: Dict[str, str] = Field(description="Column mappings (target: source)")
    transformations: Dict[str, TransformationRule] = Field(
        default_factory=dict, description="Transformation rules"
    )
    settings: Dict[str, Any] = Field(
        default_factory=dict, description="Processing settings"
    )
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence score")

    @field_validator("confidence")
    @classmethod
    def validate_confidence(cls, v):
        """Ensure confidence is between 0 and 1."""
        if not 0.0 <= v <= 1.0:
            raise ValueError("Confidence must be between 0.0 and 1.0")
        return v

    @field_validator("mappings")
    @classmethod
    def validate_mappings(cls, v):
        """Ensure mappings is a non-empty dict."""
        if not isinstance(v, dict):
            raise ValueError("Mappings must be a dictionary")
        if len(v) == 0:
            raise ValueError("Mappings must not be empty")
        return v

    @field_validator("transformations")
    @classmethod
    def validate_transformations(cls, v):
        """Ensure transformations is a dict if provided."""
        if v is not None and not isinstance(v, dict):
            raise ValueError("Transformations must be a dictionary")
        return v

    @field_validator("settings")
    @classmethod
    def validate_settings(cls, v):
        """Ensure settings is a dict and contains valid keys."""
        if not isinstance(v, dict):
            raise ValueError("Settings must be a dictionary")

        # Validate known settings
        valid_settings = {
            "case_sensitive",
            "skip_empty_values",
            "log_unmatched_rules",
            "trim_whitespace",
            "normalize_case",
        }

        for key in v.keys():
            if key not in valid_settings:
                raise ValueError(
                    f"Unknown setting '{key}'. Valid settings: {valid_settings}"
                )

        # Validate boolean settings
        boolean_settings = {
            "case_sensitive",
            "skip_empty_values",
            "log_unmatched_rules",
            "trim_whitespace",
            "normalize_case",
        }

        for key, value in v.items():
            if key in boolean_settings and not isinstance(value, bool):
                raise ValueError(f"Setting '{key}' must be a boolean")

        return v

    @model_validator(mode="after")
    def validate_transformation_references(self):
        """Ensure transformation rules reference valid target columns from mappings."""
        if not self.transformations:
            return self

        # Get all target columns from mappings
        target_columns = set(self.mappings.keys())

        # Check if transformation target_columns are in mappings or have source_column
        for rule_name, rule in self.transformations.items():
            if rule.target_column not in target_columns and rule.source_column is None:
                raise ValueError(
                    f"Transformation rule '{rule_name}' targets column '{rule.target_column}' "
                    f"which is not in mappings and has no source_column specified"
                )

        return self
