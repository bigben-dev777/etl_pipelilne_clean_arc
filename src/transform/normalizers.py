import re
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple

# Try to import pandas, but handle if not available
try:
    import pandas as pd

    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False
    pd = None

from src.utils.logging_config import get_logger

logger = get_logger(__name__)


# US State abbreviations (USPS 2-letter codes)
STATE_ABBREVIATIONS = {
    "AL",
    "AK",
    "AZ",
    "AR",
    "CA",
    "CO",
    "CT",
    "DE",
    "FL",
    "GA",
    "HI",
    "ID",
    "IL",
    "IN",
    "IA",
    "KS",
    "KY",
    "LA",
    "ME",
    "MD",
    "MA",
    "MI",
    "MN",
    "MS",
    "MO",
    "MT",
    "NE",
    "NV",
    "NH",
    "NJ",
    "NM",
    "NY",
    "NC",
    "ND",
    "OH",
    "OK",
    "OR",
    "PA",
    "RI",
    "SC",
    "SD",
    "TN",
    "TX",
    "UT",
    "VT",
    "VA",
    "WA",
    "WV",
    "WI",
    "WY",
    "DC",
    "PR",
    "GU",
    "VI",
}

# State name to abbreviation mapping
STATE_NAME_TO_ABBR = {
    "ALABAMA": "AL",
    "ALASKA": "AK",
    "ARIZONA": "AZ",
    "ARKANSAS": "AR",
    "CALIFORNIA": "CA",
    "COLORADO": "CO",
    "CONNECTICUT": "CT",
    "DELAWARE": "DE",
    "FLORIDA": "FL",
    "GEORGIA": "GA",
    "HAWAII": "HI",
    "IDAHO": "ID",
    "ILLINOIS": "IL",
    "INDIANA": "IN",
    "IOWA": "IA",
    "KANSAS": "KS",
    "KENTUCKY": "KY",
    "LOUISIANA": "LA",
    "MAINE": "ME",
    "MARYLAND": "MD",
    "MASSACHUSETTS": "MA",
    "MICHIGAN": "MI",
    "MINNESOTA": "MN",
    "MISSISSIPPI": "MS",
    "MISSOURI": "MO",
    "MONTANA": "MT",
    "NEBRASKA": "NE",
    "NEVADA": "NV",
    "NEW HAMPSHIRE": "NH",
    "NEW JERSEY": "NJ",
    "NEW MEXICO": "NM",
    "NEW YORK": "NY",
    "NORTH CAROLINA": "NC",
    "NORTH DAKOTA": "ND",
    "OHIO": "OH",
    "OKLAHOMA": "OK",
    "OREGON": "OR",
    "PENNSYLVANIA": "PA",
    "RHODE ISLAND": "RI",
    "SOUTH CAROLINA": "SC",
    "SOUTH DAKOTA": "SD",
    "TENNESSEE": "TN",
    "TEXAS": "TX",
    "UTAH": "UT",
    "VERMONT": "VT",
    "VIRGINIA": "VA",
    "WASHINGTON": "WA",
    "WEST VIRGINIA": "WV",
    "WISCONSIN": "WI",
    "WYOMING": "WY",
    "DISTRICT OF COLUMBIA": "DC",
    "PUERTO RICO": "PR",
    "VIRGIN ISLANDS": "VI",
    "GUAM": "GU",
}

# Age group to canonical AGE_BUCKET_ENUM
AGE_GROUP_TO_CANONICAL = {
    "infant": "INFANT",
    "infants": "INFANT",
    "baby": "INFANT",
    "babies": "INFANT",
    "toddler": "TODDLER",
    "toddlers": "TODDLER",
    "preschool": "PRESCHOOL",
    "preschooler": "PRESCHOOL",
    "preschoolers": "PRESCHOOL",
    "pre-k": "PRESCHOOL",
    "prek": "PRESCHOOL",
    "pre-school": "PRESCHOOL",
    "school age": "SCHOOL_AGE",
    "school-age": "SCHOOL_AGE",
    "schoolage": "SCHOOL_AGE",
    "school": "SCHOOL_AGE",
    "kindergarten": "KINDERGARTEN",
    "infant toddler": "INFANT_TODDLER",
    "infant/toddler": "INFANT_TODDLER",
    "birth to 5": "BIRTH_TO_5",
    "birth-5": "BIRTH_TO_5",
    "0-5": "BIRTH_TO_5",
    "birth to 12": "BIRTH_TO_12",
    "birth-12": "BIRTH_TO_12",
    "0-12": "BIRTH_TO_12",
    "all ages": "MIXED_AGES",
    "mixed ages": "MIXED_AGES",
    "mixed": "MIXED_AGES",
}

# Canonical facility types (UPPER_SNAKE_CASE)
CANONICAL_FACILITY_TYPES = {
    "CENTER",
    "FAMILY_HOME",
    "GROUP_HOME",
    "SCHOOL_AGE",
    "HEAD_START",
    "EARLY_HEAD_START",
    "MONTESSORI",
    "RELIGIOUS",
    "DROP_IN",
    "EXEMPT",
    "OTHER",
    "UNKNOWN",
}

# Canonical license statuses (STATUS_ENUM)
CANONICAL_LICENSE_STATUSES = {
    "ACTIVE",
    "CONDITIONAL",
    "PROBATION",
    "TEMPORARY",
    "PENDING",
    "SUSPENDED",
    "REVOKED",
    "EXPIRED",
    "CLOSED",
    "DENIED",
    "VOLUNTARILY_CLOSED",
    "UNKNOWN",
}

# Canonical license types (LICENSE_TYPE_ENUM)
CANONICAL_LICENSE_TYPES = {
    "REGULAR",
    "PROVISIONAL",
    "TEMPORARY",
    "INITIAL",
    "RENEWAL",
    "REGISTERED",
    "EXEMPT",
    "GROUP",
    "HOME",
    "CENTER",
    "OTHER",
    "UNKNOWN",
}

# Canonical ages served (AGE_BUCKET_ENUM)
CANONICAL_AGES_SERVED = {
    "INFANT",
    "TODDLER",
    "PRESCHOOL",
    "SCHOOL_AGE",
    "INFANT_TODDLER",
    "BIRTH_TO_5",
    "BIRTH_TO_12",
    "KINDERGARTEN",
    "MIXED_AGES",
    "UNKNOWN",
}


class BaseNormalizer(ABC):
    """Abstract base class for field normalizers."""

    @abstractmethod
    def normalize(self, value: Any) -> Tuple[Any, Dict[str, Any]]:
        """
        Normalize a value to canonical ETL-ready format.

        Args:
            value: Input value to normalize

        Returns:
            Tuple of (normalized_value, metadata)
        """
        pass


class PhoneNormalizer(BaseNormalizer):
    """Normalizer for phone numbers to E164 format (+15551234567)."""

    def normalize(self, value: Any) -> Tuple[Optional[str], Dict[str, Any]]:
        """
        Normalize phone number to E164 format: +1XXXXXXXXXX

        Args:
            value: Phone number string

        Returns:
            Tuple of (e164_phone, metadata) or (None, metadata) if invalid
        """
        if not value or (HAS_PANDAS and pd.isna(value)):
            return None, {"valid": False, "error": "empty_value"}

        phone_str = str(value).strip()

        # Extract all digits
        digits = re.sub(r"\D", "", phone_str)

        # Handle country code
        if digits.startswith("1") and len(digits) == 11:
            # Already has country code
            pass
        elif len(digits) == 10:
            # Add US country code
            digits = "1" + digits
        else:
            # Invalid length
            return None, {
                "valid": False,
                "error": "invalid_length",
                "digits_found": len(digits),
                "original": phone_str,
            }

        # Format to E164: +1XXXXXXXXXX
        e164 = f"+{digits}"

        return e164, {"valid": True, "original": phone_str, "format": "E164"}


class StateNormalizer(BaseNormalizer):
    """Normalizer for US state codes to USPS 2-letter format."""

    def normalize(self, value: Any) -> Tuple[Optional[str], Dict[str, Any]]:
        """
        Normalize state to USPS 2-letter code.

        Args:
            value: State name or abbreviation

        Returns:
            Tuple of (state_code, metadata) or (None, metadata) if invalid
        """
        if not value or (HAS_PANDAS and pd.isna(value)):
            return None, {"valid": False, "error": "empty_value"}

        state_str = str(value).strip().upper()

        # Already a valid abbreviation
        if state_str in STATE_ABBREVIATIONS:
            return state_str, {"valid": True, "original": value}

        # Full name lookup
        if state_str in STATE_NAME_TO_ABBR:
            return STATE_NAME_TO_ABBR[state_str], {
                "valid": True,
                "original": value,
                "matched_from": "full_name",
            }

        # Common variations
        variations = {
            "CALIF": "CA",
            "CALIF.": "CA",
            "TEX": "TX",
            "TEX.": "TX",
            "NEV": "NV",
            "NEV.": "NV",
            "OKLA": "OK",
            "OKLA.": "OK",
            "FLA": "FL",
            "FLA.": "FL",
            "PENN": "PA",
            "PENNA": "PA",
        }

        if state_str in variations:
            return variations[state_str], {
                "valid": True,
                "original": value,
                "matched_from": "variation",
            }

        # Invalid - return None to fill NaN
        return None, {"valid": False, "error": "unknown_state", "original": value}


class ZipNormalizer(BaseNormalizer):
    """Normalizer for ZIP codes to 5-digit format."""

    def normalize(self, value: Any) -> Tuple[Optional[str], Dict[str, Any]]:
        """
        Normalize ZIP code to 5-digit format (XXXXX).

        Args:
            value: ZIP code string

        Returns:
            Tuple of (zip5, metadata) or (None, metadata) if invalid
        """
        if not value or (HAS_PANDAS and pd.isna(value)):
            return None, {"valid": False, "error": "empty_value"}

        zip_str = str(value).strip()

        # Extract digits
        digits = re.sub(r"\D", "", zip_str)

        # Handle 9-digit ZIP+4 - take first 5
        if len(digits) == 9:
            return digits[:5], {
                "valid": True,
                "original": value,
                "note": "truncated_zip4",
            }

        # Valid 5-digit ZIP
        if len(digits) == 5:
            return digits, {"valid": True, "original": value}

        # Handle 4-digit (pad with leading zero)
        if len(digits) == 4:
            return f"0{digits}", {
                "valid": True,
                "original": value,
                "note": "padded_with_zero",
            }

        # Handle 3-digit (pad with leading zeros)
        if len(digits) == 3:
            return f"00{digits}", {
                "valid": True,
                "original": value,
                "note": "padded_with_zeros",
            }

        # Invalid - return None
        return None, {
            "valid": False,
            "error": "invalid_length",
            "digits_found": len(digits),
        }


class AddressNormalizer(BaseNormalizer):
    """Normalizer for addresses - standardizes street types."""

    STREET_TYPE_MAPPINGS = {
        " ST ": " STREET ",
        " ST. ": " STREET ",
        " AVE ": " AVENUE ",
        " AVE. ": " AVENUE ",
        " RD ": " ROAD ",
        " RD. ": " ROAD ",
        " BLVD ": " BOULEVARD ",
        " BLVD. ": " BOULEVARD ",
        " DR ": " DRIVE ",
        " DR. ": " DRIVE ",
        " LN ": " LANE ",
        " LN. ": " LANE ",
        " CT ": " COURT ",
        " CT. ": " COURT ",
        " CIR ": " CIRCLE ",
        " CIR. ": " CIRCLE ",
        " PL ": " PLACE ",
        " PL. ": " PLACE ",
    }

    def normalize(self, value: Any) -> Tuple[Optional[str], Dict[str, Any]]:
        """
        Normalize address by standardizing street type abbreviations.
        Returns Title Case format.

        Args:
            value: Address string

        Returns:
            Tuple of (normalized_address, metadata) or (None, metadata)
        """
        if not value or (HAS_PANDAS and pd.isna(value)):
            return None, {"valid": False, "error": "empty_value"}

        address_str = str(value).strip()

        # Convert to uppercase for matching
        normalized = " " + address_str.upper() + " "

        # Apply street type standardization
        for abbr, full in self.STREET_TYPE_MAPPINGS.items():
            normalized = normalized.replace(abbr, full)

        # Trim and convert to Title Case
        normalized = normalized.strip()
        normalized = " ".join(normalized.split())  # Remove extra spaces
        normalized = normalized.title()

        return normalized, {"valid": True, "original": address_str}


class NameNormalizer(BaseNormalizer):
    """Normalizer for contact names to Title Case format."""

    TITLES = {
        "DR",
        "DR.",
        "DOCTOR",
        "MR",
        "MR.",
        "MRS",
        "MRS.",
        "MS",
        "MS.",
        "MISS",
        "PROF",
        "PROF.",
        "SIR",
        "MADAM",
    }

    SUFFIXES = {
        "JR",
        "JR.",
        "SR",
        "SR.",
        "II",
        "III",
        "IV",
        "V",
        "PHD",
        "PH.D",
        "MD",
        "M.D.",
        "ESQ",
        "ESQ.",
    }

    def normalize(self, value: Any) -> Tuple[Dict[str, Optional[str]], Dict[str, Any]]:
        """
        Parse full name into first and last name in Title Case.

        Args:
            value: Full name string

        Returns:
            Tuple of ({first_name, last_name}, metadata)
        """
        if not value or (HAS_PANDAS and pd.isna(value)):
            return {"first_name": None, "last_name": None}, {
                "valid": False,
                "error": "empty_value",
            }

        name_str = str(value).strip()

        # Schema regex for first_name: ^\s*([A-Za-z'\-]+)
        first_match = re.match(r"^\s*([A-Za-z'\-]+)", name_str)

        # Schema regex for last_name: ^\s*[A-Za-z'\-]+\s+([A-Za-z'\-]+)
        last_match = re.match(r"^\s*[A-Za-z'\-]+\s+([A-Za-z'\-]+)", name_str)

        first_name = first_match.group(1) if first_match else None
        last_name = last_match.group(1) if last_match else None

        if first_name or last_name:
            return {
                "first_name": self._to_title_case(first_name) if first_name else None,
                "last_name": self._to_title_case(last_name) if last_name else None,
            }, {
                "valid": True,
                "original": value,
            }

        # Fallback: Handle "Last, First" format
        if "," in name_str:
            parts = [p.strip() for p in name_str.split(",")]
            if len(parts) == 2:
                return {
                    "first_name": self._to_title_case(parts[1]),
                    "last_name": self._to_title_case(parts[0]),
                }, {
                    "valid": True,
                    "original": value,
                    "format": "last_first",
                }

        # Fallback: Split by space
        parts = name_str.split()

        # Remove titles
        while parts and parts[0].upper() in self.TITLES:
            parts.pop(0)

        # Remove suffixes
        while parts and parts[-1].upper() in self.SUFFIXES:
            parts.pop()

        if len(parts) == 0:
            return {"first_name": None, "last_name": None}, {
                "valid": False,
                "error": "no_name_parts",
            }

        if len(parts) == 1:
            return {"first_name": None, "last_name": self._to_title_case(parts[0])}, {
                "valid": True,
                "original": value,
                "note": "single_name",
            }

        # Multiple parts
        return {
            "first_name": self._to_title_case(parts[0]),
            "last_name": self._to_title_case(" ".join(parts[1:])),
        }, {
            "valid": True,
            "original": value,
        }

    def _to_title_case(self, name: str) -> str:
        """Convert name to Title Case, preserving hyphens and apostrophes."""
        if not name:
            return ""

        # Handle hyphenated names (e.g., Anne-Marie)
        if "-" in name:
            parts = name.split("-")
            return "-".join(p.capitalize() for p in parts)

        # Handle names with apostrophes (e.g., O'Brien)
        if "'" in name:
            parts = name.split("'")
            return "'".join(p.capitalize() for p in parts)

        return name.capitalize()


class AgeParser(BaseNormalizer):
    """Parser for age range strings to canonical AGE_BUCKET_ENUM."""

    def normalize(self, value: Any) -> Tuple[Optional[str], Dict[str, Any]]:
        """
        Parse age range string into canonical AGE_BUCKET_ENUM.

        Args:
            value: Age range string (e.g., "0-5", "Infant, Toddler")

        Returns:
            Tuple of (canonical_age_bucket, metadata) or (None, metadata)
        """
        if not value or (HAS_PANDAS and pd.isna(value)):
            return None, {"valid": False, "error": "empty_value"}

        age_str = str(value).strip().lower()

        # Direct mapping to canonical values
        if age_str in AGE_GROUP_TO_CANONICAL:
            return AGE_GROUP_TO_CANONICAL[age_str], {
                "valid": True,
                "original": value,
                "method": "direct_mapping",
            }

        # Try to parse numeric ranges
        if re.search(r"\d", age_str):
            canonical = self._parse_numeric_to_canonical(age_str)
            if canonical:
                return canonical, {
                    "valid": True,
                    "original": value,
                    "method": "numeric_parse",
                }

        # Try to parse multiple age groups
        canonical = self._parse_multiple_groups(age_str)
        if canonical:
            return canonical, {
                "valid": True,
                "original": value,
                "method": "multiple_groups",
            }

        # Default to UNKNOWN
        return "UNKNOWN", {
            "valid": True,
            "original": value,
            "note": "could_not_parse_defaulted_to_unknown",
        }

    def _parse_numeric_to_canonical(self, age_str: str) -> Optional[str]:
        """Parse numeric age ranges to canonical buckets."""
        # Pattern: "X-Y" or "X to Y"
        match = re.search(r"(\d+)\s*(?:-|to)\s*(\d+)", age_str)

        if match:
            min_age = int(match.group(1))
            max_age = int(match.group(2))

            # Map to canonical buckets
            if min_age == 0 and max_age <= 1:
                return "INFANT"
            elif min_age <= 1 and max_age <= 3:
                return "INFANT_TODDLER"
            elif min_age == 0 and max_age <= 5:
                return "BIRTH_TO_5"
            elif min_age == 0 and max_age <= 12:
                return "BIRTH_TO_12"
            elif min_age >= 1 and max_age <= 3:
                return "TODDLER"
            elif min_age >= 3 and max_age <= 5:
                return "PRESCHOOL"
            elif min_age >= 5 and max_age <= 12:
                return "SCHOOL_AGE"
            else:
                return "MIXED_AGES"

        return None

    def _parse_multiple_groups(self, age_str: str) -> Optional[str]:
        """Parse multiple age group labels."""
        groups = re.split(r"[,;/&]|\band\b", age_str)
        groups = [g.strip() for g in groups if g.strip()]

        found_groups = []
        for group in groups:
            if group in AGE_GROUP_TO_CANONICAL:
                found_groups.append(AGE_GROUP_TO_CANONICAL[group])

        if not found_groups:
            return None

        # If multiple different groups, return MIXED_AGES
        if len(set(found_groups)) > 2:
            return "MIXED_AGES"

        # If contains both infant and toddler
        if "INFANT" in found_groups and "TODDLER" in found_groups:
            return "INFANT_TODDLER"

        # Return first found
        return found_groups[0]


class MinMaxAgeNormalizer(BaseNormalizer):
    """Normalizer for min_age and max_age to INTEGER_YEARS."""

    def normalize(self, value: Any) -> Tuple[Optional[int], Dict[str, Any]]:
        """
        Normalize age to integer years.
        Converts months/weeks to years.

        Args:
            value: Age value (number or string with units)

        Returns:
            Tuple of (age_in_years, metadata) or (None, metadata)
        """
        if not value or (HAS_PANDAS and pd.isna(value)):
            return None, {"valid": False, "error": "empty_value"}

        age_str = str(value).strip().lower()

        # Extract number
        match = re.search(r"(\d+(?:\.\d+)?)", age_str)
        if not match:
            return None, {"valid": False, "error": "no_number_found"}

        age_val = float(match.group(1))

        # Convert based on units
        if "week" in age_str:
            age_years = age_val / 52
        elif "month" in age_str:
            age_years = age_val / 12
        else:
            # Assume years
            age_years = age_val

        # Round to nearest integer
        age_int = round(age_years)

        return age_int, {
            "valid": True,
            "original": value,
            "converted_from": (
                "weeks"
                if "week" in age_str
                else "months" if "month" in age_str else "years"
            ),
        }


class CapacityNormalizer(BaseNormalizer):
    """Normalizer for capacity values to integer."""

    def normalize(self, value: Any) -> Tuple[Optional[int], Dict[str, Any]]:
        """
        Extract numeric capacity as integer.

        Args:
            value: Capacity string or number

        Returns:
            Tuple of (capacity_int, metadata) or (None, metadata)
        """
        if not value or (HAS_PANDAS and pd.isna(value)):
            return None, {"valid": False, "error": "empty_value"}

        cap_str = str(value).strip()

        # Check for invalid values
        invalid_values = {"n/a", "na", "unknown", "none", "", "null"}
        if cap_str.lower() in invalid_values:
            return None, {"valid": False, "error": "invalid_value"}

        # Schema regex: (\d+)\s*(?:children|kids|child|spaces|capacity|enrollment)
        match = re.search(
            r"(\d+)\s*(?:children|kids|child|spaces|capacity|enrollment)",
            cap_str,
            re.IGNORECASE,
        )

        if match:
            return int(match.group(1)), {
                "valid": True,
                "original": value,
            }

        # Fallback: Extract any digits
        match = re.search(r"(\d+)", cap_str)
        if match:
            return int(match.group(1)), {
                "valid": True,
                "original": value,
            }

        return None, {"valid": False, "error": "no_digits_found"}


class LicenseStatusNormalizer(BaseNormalizer):
    """Normalizer for license status to canonical STATUS_ENUM."""

    STATUS_MAPPINGS = {
        # ACTIVE
        "licensed": "ACTIVE",
        "valid": "ACTIVE",
        "current": "ACTIVE",
        "good standing": "ACTIVE",
        "active": "ACTIVE",
        "open": "ACTIVE",
        "approved": "ACTIVE",
        "full permit": "ACTIVE",
        "permit": "ACTIVE",
        "in good standing": "ACTIVE",
        # CONDITIONAL
        "conditional": "CONDITIONAL",
        # PROBATION
        "probation": "PROBATION",
        "monitored": "PROBATION",
        "probationary": "PROBATION",
        # TEMPORARY
        "temporary": "TEMPORARY",
        "temp": "TEMPORARY",
        # PENDING
        "pending": "PENDING",
        "application submitted": "PENDING",
        "under review": "PENDING",
        "application": "PENDING",
        "in progress": "PENDING",
        "provisional": "PENDING",
        # SUSPENDED
        "suspended": "SUSPENDED",
        "on hold": "SUSPENDED",
        # REVOKED
        "revoked": "REVOKED",
        "denied": "REVOKED",
        "cancelled": "REVOKED",
        "canceled": "REVOKED",
        # EXPIRED
        "expired": "EXPIRED",
        "lapsed": "EXPIRED",
        "past due": "EXPIRED",
        "delinquent": "EXPIRED",
        # CLOSED
        "closed": "CLOSED",
        "inactive": "CLOSED",
        "terminated": "CLOSED",
        # VOLUNTARILY_CLOSED
        "voluntarily closed": "VOLUNTARILY_CLOSED",
        "voluntary closure": "VOLUNTARILY_CLOSED",
    }

    def normalize(self, value: Any) -> Tuple[str, Dict[str, Any]]:
        """
        Normalize license status to canonical STATUS_ENUM.

        Args:
            value: Status string

        Returns:
            Tuple of (canonical_status, metadata) - defaults to UNKNOWN if not recognized
        """
        if not value or (HAS_PANDAS and pd.isna(value)):
            return "UNKNOWN", {"valid": True, "note": "empty_value_defaulted"}

        status_str = str(value).strip().lower()

        # Direct mapping
        if status_str in self.STATUS_MAPPINGS:
            return self.STATUS_MAPPINGS[status_str], {
                "valid": True,
                "original": value,
            }

        # Check if already canonical
        if status_str.upper() in CANONICAL_LICENSE_STATUSES:
            return status_str.upper(), {"valid": True, "original": value}

        # Default to UNKNOWN
        return "UNKNOWN", {
            "valid": True,
            "note": "unrecognized_value",
            "original": value,
        }


class LicenseTypeNormalizer(BaseNormalizer):
    """Normalizer for license type to canonical LICENSE_TYPE_ENUM."""

    LICENSE_TYPE_MAPPINGS = {
        "regular": "REGULAR",
        "standard": "REGULAR",
        "full": "REGULAR",
        "provisional": "PROVISIONAL",
        "temporary": "TEMPORARY",
        "temp": "TEMPORARY",
        "initial": "INITIAL",
        "new": "INITIAL",
        "renewal": "RENEWAL",
        "renew": "RENEWAL",
        "registered": "REGISTERED",
        "registration": "REGISTERED",
        "exempt": "EXEMPT",
        "exemption": "EXEMPT",
        "group": "GROUP",
        "group home": "GROUP",
        "home": "HOME",
        "family home": "HOME",
        "family": "HOME",
        "center": "CENTER",
        "child care center": "CENTER",
    }

    def normalize(self, value: Any) -> Tuple[str, Dict[str, Any]]:
        """
        Normalize license type to canonical LICENSE_TYPE_ENUM.
        Extracts from "Type License" field format.

        Args:
            value: License type string

        Returns:
            Tuple of (canonical_license_type, metadata)
        """
        if not value or (HAS_PANDAS and pd.isna(value)):
            return "UNKNOWN", {"valid": True, "note": "empty_value_defaulted"}

        type_str = str(value).strip()

        # Extract license type using schema regex: ^\s*([^\-]+?)\s*-
        match = re.match(r"^\s*([^\-]+?)\s*-", type_str)

        if match:
            license_type = match.group(1).strip().lower()
        else:
            license_type = type_str.lower()

        # Map to canonical
        if license_type in self.LICENSE_TYPE_MAPPINGS:
            return self.LICENSE_TYPE_MAPPINGS[license_type], {
                "valid": True,
                "original": value,
            }

        # Check if already canonical
        if license_type.upper() in CANONICAL_LICENSE_TYPES:
            return license_type.upper(), {"valid": True, "original": value}

        # Default to OTHER
        return "OTHER", {
            "valid": True,
            "note": "unmapped_defaulted_to_other",
            "original": value,
        }


class FacilityTypeNormalizer(BaseNormalizer):
    """Normalizer for facility type to canonical UPPER_SNAKE_CASE format."""

    FACILITY_TYPE_MAPPINGS = {
        "child care center": "CENTER",
        "center": "CENTER",
        "daycare center": "CENTER",
        "day care center": "CENTER",
        "child care family": "FAMILY_HOME",
        "family child care": "FAMILY_HOME",
        "family home": "FAMILY_HOME",
        "family day care": "FAMILY_HOME",
        "family": "FAMILY_HOME",
        "home": "FAMILY_HOME",
        "group home": "GROUP_HOME",
        "group": "GROUP_HOME",
        "school-age": "SCHOOL_AGE",
        "school age": "SCHOOL_AGE",
        "school age program": "SCHOOL_AGE",
        "before/after school": "SCHOOL_AGE",
        "head start": "HEAD_START",
        "early head start": "EARLY_HEAD_START",
        "montessori": "MONTESSORI",
        "montessori school": "MONTESSORI",
        "religious": "RELIGIOUS",
        "church": "RELIGIOUS",
        "faith-based": "RELIGIOUS",
        "drop in": "DROP_IN",
        "drop-in": "DROP_IN",
        "exempt": "EXEMPT",
        "preschool": "CENTER",
        "nursery school": "CENTER",
    }

    def normalize(self, value: Any) -> Tuple[str, Dict[str, Any]]:
        """
        Normalize facility type to canonical UPPER_SNAKE_CASE format.

        Args:
            value: Facility type string

        Returns:
            Tuple of (canonical_facility_type, metadata)
        """
        if not value or (HAS_PANDAS and pd.isna(value)):
            return "UNKNOWN", {"valid": True, "note": "empty_value_defaulted"}

        type_str = str(value).strip()

        # Extract from "Type License" format using schema regex
        match = re.match(r"^\s*([^\-]+?)\s*-", type_str)

        if match:
            facility_type = match.group(1).strip().lower()
        else:
            facility_type = type_str.lower()

        # Map to canonical
        if facility_type in self.FACILITY_TYPE_MAPPINGS:
            return self.FACILITY_TYPE_MAPPINGS[facility_type], {
                "valid": True,
                "original": value,
            }

        # Check if already canonical
        if facility_type.upper() in CANONICAL_FACILITY_TYPES:
            return facility_type.upper(), {"valid": True, "original": value}

        # Default to OTHER
        return "OTHER", {
            "valid": True,
            "note": "unmapped_defaulted_to_other",
            "original": value,
        }


class EmailValidator(BaseNormalizer):
    """Validator for email addresses - converts to lowercase."""

    def normalize(self, value: Any) -> Tuple[Optional[str], Dict[str, Any]]:
        """
        Validate and normalize email to lowercase.

        Args:
            value: Email string

        Returns:
            Tuple of (lowercase_email, metadata) or (None, metadata)
        """
        if not value or (HAS_PANDAS and pd.isna(value)):
            return None, {"valid": False, "error": "empty_value"}

        email_str = str(value).strip().lower()

        # Schema regex: ^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$
        if re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", email_str):
            return email_str, {"valid": True, "original": value}

        # Invalid email
        return None, {"valid": False, "error": "invalid_format", "original": value}


class WebsiteNormalizer(BaseNormalizer):
    """Normalizer for website URLs to HTTPS format."""

    def normalize(self, value: Any) -> Tuple[Optional[str], Dict[str, Any]]:
        """
        Normalize website to https://example.com format.
        Rules:
        - Always https
        - No trailing slash
        - No query params
        - No www

        Args:
            value: Website URL

        Returns:
            Tuple of (normalized_url, metadata) or (None, metadata)
        """
        if not value or (HAS_PANDAS and pd.isna(value)):
            return None, {"valid": False, "error": "empty_value"}

        url_str = str(value).strip().lower()

        # Remove protocol
        url_str = re.sub(r"^https?://", "", url_str)

        # Remove www
        url_str = re.sub(r"^www\.", "", url_str)

        # Remove trailing slash
        url_str = url_str.rstrip("/")

        # Remove query params
        url_str = url_str.split("?")[0]

        # Remove fragment
        url_str = url_str.split("#")[0]

        # Validate basic domain structure
        if not re.match(r"^[a-z0-9.-]+\.[a-z]{2,}$", url_str):
            return None, {"valid": False, "error": "invalid_domain", "original": value}

        # Add https
        normalized = f"https://{url_str}"

        return normalized, {"valid": True, "original": value}


class CountyNormalizer(BaseNormalizer):
    """Normalizer for county names to Title Case with 'County' suffix."""

    def normalize(self, value: Any) -> Tuple[Optional[str], Dict[str, Any]]:
        """
        Normalize county to Title Case with 'County' suffix.

        Args:
            value: County name

        Returns:
            Tuple of (normalized_county, metadata) or (None, metadata)
        """
        if not value or (HAS_PANDAS and pd.isna(value)):
            return None, {"valid": False, "error": "empty_value"}

        county_str = str(value).strip()

        # Remove existing "County" suffix (case-insensitive)
        county_str = re.sub(r"\s+county$", "", county_str, flags=re.IGNORECASE)

        # Convert to Title Case
        county_str = county_str.title()

        # Add "County" suffix
        normalized = f"{county_str} County"

        return normalized, {"valid": True, "original": value}


class BooleanNormalizer(BaseNormalizer):
    """Normalizer for boolean values to true/false strings."""

    TRUE_VALUES = {"true", "t", "yes", "y", "1", "on", "active"}
    FALSE_VALUES = {"false", "f", "no", "n", "0", "off", "inactive"}

    def normalize(self, value: Any) -> Tuple[Optional[str], Dict[str, Any]]:
        """
        Normalize boolean value to 'true' or 'false' string.

        Args:
            value: Boolean value

        Returns:
            Tuple of ('true'/'false', metadata) or (None, metadata)
        """
        if value is None or (HAS_PANDAS and pd.isna(value)):
            return None, {"valid": False, "error": "empty_value"}

        # Handle actual boolean type
        if isinstance(value, bool):
            return "true" if value else "false", {"valid": True, "original": value}

        # Handle string
        val_str = str(value).strip().lower()

        if val_str in self.TRUE_VALUES:
            return "true", {"valid": True, "original": value}

        if val_str in self.FALSE_VALUES:
            return "false", {"valid": True, "original": value}

        # Invalid
        return None, {
            "valid": False,
            "error": "unrecognized_boolean",
            "original": value,
        }


class LicenseNumberExtractor(BaseNormalizer):
    """Extractor for license number from 'Type License' field."""

    def normalize(self, value: Any) -> Tuple[Optional[str], Dict[str, Any]]:
        """
        Extract license number from 'Type License' values.
        Schema regex: -\\s*([A-Z0-9-]+)$

        Args:
            value: Type License string

        Returns:
            Tuple of (license_number, metadata) or (None, metadata)
        """
        if not value or (HAS_PANDAS and pd.isna(value)):
            return None, {"valid": False, "error": "empty_value"}

        type_str = str(value).strip()

        # Schema regex: -\s*([A-Z0-9-]+)$
        match = re.search(r"-\s*([A-Z0-9-]+)$", type_str.upper())

        if match:
            return match.group(1), {
                "valid": True,
                "original": value,
            }

        return None, {
            "valid": False,
            "error": "no_license_number_found",
            "original": value,
        }
