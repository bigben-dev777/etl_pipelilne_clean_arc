"""Field normalizers for standardizing data values."""

import re
from typing import Tuple, Optional, Dict, Any, List
from abc import ABC, abstractmethod
import logging

# Try to import pandas, but handle if not available
try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False
    pd = None

logger = logging.getLogger(__name__)


# US State abbreviations
STATE_ABBREVIATIONS = {
    'AL', 'AK', 'AZ', 'AR', 'CA', 'CO', 'CT', 'DE', 'FL', 'GA',
    'HI', 'ID', 'IL', 'IN', 'IA', 'KS', 'KY', 'LA', 'ME', 'MD',
    'MA', 'MI', 'MN', 'MS', 'MO', 'MT', 'NE', 'NV', 'NH', 'NJ',
    'NM', 'NY', 'NC', 'ND', 'OH', 'OK', 'OR', 'PA', 'RI', 'SC',
    'SD', 'TN', 'TX', 'UT', 'VT', 'VA', 'WA', 'WV', 'WI', 'WY',
    'DC', 'PR', 'VI', 'GU', 'AS', 'MP'
}

# State name to abbreviation mapping
STATE_NAME_TO_ABBR = {
    'ALABAMA': 'AL', 'ALASKA': 'AK', 'ARIZONA': 'AZ', 'ARKANSAS': 'AR',
    'CALIFORNIA': 'CA', 'COLORADO': 'CO', 'CONNECTICUT': 'CT', 'DELAWARE': 'DE',
    'FLORIDA': 'FL', 'GEORGIA': 'GA', 'HAWAII': 'HI', 'IDAHO': 'ID',
    'ILLINOIS': 'IL', 'INDIANA': 'IN', 'IOWA': 'IA', 'KANSAS': 'KS',
    'KENTUCKY': 'KY', 'LOUISIANA': 'LA', 'MAINE': 'ME', 'MARYLAND': 'MD',
    'MASSACHUSETTS': 'MA', 'MICHIGAN': 'MI', 'MINNESOTA': 'MN', 'MISSISSIPPI': 'MS',
    'MISSOURI': 'MO', 'MONTANA': 'MT', 'NEBRASKA': 'NE', 'NEVADA': 'NV',
    'NEW HAMPSHIRE': 'NH', 'NEW JERSEY': 'NJ', 'NEW MEXICO': 'NM', 'NEW YORK': 'NY',
    'NORTH CAROLINA': 'NC', 'NORTH DAKOTA': 'ND', 'OHIO': 'OH', 'OKLAHOMA': 'OK',
    'OREGON': 'OR', 'PENNSYLVANIA': 'PA', 'RHODE ISLAND': 'RI', 'SOUTH CAROLINA': 'SC',
    'SOUTH DAKOTA': 'SD', 'TENNESSEE': 'TN', 'TEXAS': 'TX', 'UTAH': 'UT',
    'VERMONT': 'VT', 'VIRGINIA': 'VA', 'WASHINGTON': 'WA', 'WEST VIRGINIA': 'WV',
    'WISCONSIN': 'WI', 'WYOMING': 'WY', 'DISTRICT OF COLUMBIA': 'DC',
    'PUERTO RICO': 'PR', 'VIRGIN ISLANDS': 'VI', 'GUAM': 'GU'
}

# Age group mappings
AGE_GROUP_RANGES = {
    'infant': (0, 1),
    'infants': (0, 1),
    'baby': (0, 1),
    'babies': (0, 1),
    'toddler': (1, 3),
    'toddlers': (1, 3),
    'preschool': (3, 5),
    'preschooler': (3, 5),
    'preschoolers': (3, 5),
    'pre-k': (4, 5),
    'prek': (4, 5),
    'school age': (5, 12),
    'school-age': (5, 12),
    'schoolage': (5, 12),
    'school': (5, 12),
    'adolescent': (13, 17),
    'teen': (13, 17),
    'teenager': (13, 17),
}


class BaseNormalizer(ABC):
    """Abstract base class for field normalizers."""
    
    @abstractmethod
    def normalize(self, value: Any) -> Tuple[Any, Dict[str, Any]]:
        """
        Normalize a value.
        
        Args:
            value: Input value to normalize
            
        Returns:
            Tuple of (normalized_value, metadata)
        """
        pass


class PhoneNormalizer(BaseNormalizer):
    """Normalizer for phone numbers."""
    
    def normalize(self, value: Any) -> Tuple[Optional[str], Dict[str, Any]]:
        """
        Normalize phone number to (XXX) XXX-XXXX format.
        
        Args:
            value: Phone number string
            
        Returns:
            Tuple of (formatted_phone, metadata)
        """
        if not value or pd.isna(value):
            return None, {"valid": False, "error": "empty_value"}
        
        # Convert to string and extract digits
        phone_str = str(value).strip()
        digits = re.sub(r'\D', '', phone_str)
        
        # Handle country code
        if digits.startswith('1') and len(digits) == 11:
            digits = digits[1:]
        
        # Validate length
        if len(digits) != 10:
            return None, {
                "valid": False,
                "error": "invalid_length",
                "digits_found": len(digits)
            }
        
        # Format
        formatted = f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
        
        return formatted, {
            "valid": True,
            "digits": digits,
            "original": phone_str
        }


class StateNormalizer(BaseNormalizer):
    """Normalizer for US state codes."""
    
    def normalize(self, value: Any) -> Tuple[Optional[str], Dict[str, Any]]:
        """
        Normalize state to 2-letter abbreviation.
        
        Args:
            value: State name or abbreviation
            
        Returns:
            Tuple of (abbreviation, metadata)
        """
        if not value or pd.isna(value):
            return None, {"valid": False, "error": "empty_value"}
        
        state_str = str(value).strip().upper()
        
        # Already an abbreviation
        if state_str in STATE_ABBREVIATIONS:
            return state_str, {"valid": True, "original": value}
        
        # Full name lookup
        normalized = state_str.title()
        if normalized in STATE_NAME_TO_ABBR:
            return STATE_NAME_TO_ABBR[normalized], {
                "valid": True,
                "original": value,
                "matched_from": "full_name"
            }
        
        # Common variations
        variations = {
            'CALIF': 'CA', 'CALIF.': 'CA', 'CALIFORNIA': 'CA',
            'TEX': 'TX', 'TEX.': 'TX', 'TEXAS': 'TX',
            'NEV': 'NV', 'NEV.': 'NV', 'NEVADA': 'NV',
            'OKLA': 'OK', 'OKLA.': 'OK', 'OKLAHOMA': 'OK',
            'FLA': 'FL', 'FLA.': 'FL', 'FLORIDA': 'FL',
            'PENN': 'PA', 'PENNA': 'PA', 'PENNSYLVANIA': 'PA',
        }
        
        if state_str in variations:
            return variations[state_str], {
                "valid": True,
                "original": value,
                "matched_from": "variation"
            }
        
        return None, {"valid": False, "error": "unknown_state", "original": value}


class ZipNormalizer(BaseNormalizer):
    """Normalizer for ZIP codes."""
    
    def normalize(self, value: Any) -> Tuple[Optional[str], Dict[str, Any]]:
        """
        Normalize ZIP code to 5-digit format.
        
        Args:
            value: ZIP code string
            
        Returns:
            Tuple of (normalized_zip, metadata)
        """
        if not value or pd.isna(value):
            return None, {"valid": False, "error": "empty_value"}
        
        zip_str = str(value).strip()
        
        # Extract digits
        digits = re.sub(r'\D', '', zip_str)
        
        # Handle 9-digit ZIP+4
        if len(digits) == 9:
            return digits[:5], {
                "valid": True,
                "original": value,
                "zip4": digits[5:]
            }
        
        # Valid 5-digit ZIP
        if len(digits) == 5:
            return digits, {"valid": True, "original": value}
        
        # Handle 4-digit (likely missing leading zero)
        if len(digits) == 4:
            normalized = f"0{digits}"
            return normalized, {
                "valid": True,
                "original": value,
                "note": "padded_with_zero"
            }
        
        # Handle 3-digit (likely missing leading zeros)
        if len(digits) == 3:
            normalized = f"00{digits}"
            return normalized, {
                "valid": True,
                "original": value,
                "note": "padded_with_zeros"
            }
        
        return None, {
            "valid": False,
            "error": "invalid_length",
            "digits_found": len(digits)
        }


class AddressNormalizer(BaseNormalizer):
    """Normalizer for addresses - parses combined address fields."""
    
    def normalize(self, value: Any) -> Tuple[Dict[str, Optional[str]], Dict[str, Any]]:
        """
        Parse combined address into components.
        
        Args:
            value: Combined address string
            
        Returns:
            Tuple of (address_components, metadata)
        """
        if not value or pd.isna(value):
            return {
                "address1": None,
                "address2": None,
                "city": None,
                "state": None,
                "zip": None
            }, {"valid": False, "error": "empty_value"}
        
        address_str = str(value).strip()
        
        # Try to parse with usaddress if available
        try:
            import usaddress
            parsed, address_type = usaddress.tag(address_str)
            
            result = {
                "address1": self._build_address_line(parsed),
                "address2": parsed.get('OccupancyType', '') + ' ' + parsed.get('OccupancyIdentifier', '') if parsed.get('OccupancyType') else None,
                "city": parsed.get('PlaceName'),
                "state": parsed.get('StateName'),
                "zip": parsed.get('ZipCode')
            }
            
            # Clean up address2
            if result["address2"]:
                result["address2"] = result["address2"].strip()
            
            return result, {"valid": True, "parsed_with": "usaddress", "type": address_type}
            
        except ImportError:
            logger.debug("usaddress not installed, using regex parsing")
        except Exception as e:
            logger.debug(f"usaddress parsing failed: {e}")
        
        # Fallback to regex parsing
        return self._parse_with_regex(address_str)
    
    def _build_address_line(self, parsed: Dict) -> str:
        """Build address line from parsed components."""
        parts = []
        for key in ['AddressNumber', 'StreetNamePreDirectional', 'StreetName', 
                    'StreetNamePostType', 'StreetNamePostDirectional']:
            if key in parsed:
                parts.append(parsed[key])
        return ' '.join(parts)
    
    def _parse_with_regex(self, address: str) -> Tuple[Dict[str, Optional[str]], Dict[str, Any]]:
        """Parse address using regex patterns."""
        result = {
            "address1": None,
            "address2": None,
            "city": None,
            "state": None,
            "zip": None
        }
        
        # Pattern for "City, STATE ZIP" at the end
        city_state_zip_pattern = r'([^,]+),\s*([A-Z]{2})\s*(\d{5}(-\d{4})?)'
        match = re.search(city_state_zip_pattern, address)
        
        if match:
            result["city"] = match.group(1).strip()
            result["state"] = match.group(2)
            result["zip"] = match.group(3)[:5]
            
            # Everything before is the street address
            street_part = address[:match.start()].strip()
            
            # Try to split address1/address2
            if ',' in street_part:
                parts = [p.strip() for p in street_part.split(',')]
                result["address1"] = parts[0]
                result["address2"] = ', '.join(parts[1:]) if len(parts) > 1 else None
            else:
                result["address1"] = street_part
            
            return result, {"valid": True, "parsed_with": "regex"}
        
        # If no match, return the whole thing as address1
        result["address1"] = address
        return result, {"valid": False, "parsed_with": "fallback", "note": "could_not_parse"}


class NameNormalizer(BaseNormalizer):
    """Normalizer for contact names."""
    
    # Common titles to remove
    TITLES = {'DR', 'DR.', 'DOCTOR', 'MR', 'MR.', 'MRS', 'MRS.', 'MS', 'MS.', 
              'MISS', 'PROF', 'PROF.', 'SIR', 'MADAM'}
    
    # Common suffixes
    SUFFIXES = {'JR', 'JR.', 'SR', 'SR.', 'II', 'III', 'IV', 'V', 'PHD', 'PH.D',
                'MD', 'M.D.', 'ESQ', 'ESQ.'}
    
    def normalize(self, value: Any) -> Tuple[Dict[str, Optional[str]], Dict[str, Any]]:
        """
        Parse full name into first and last name.
        
        Args:
            value: Full name string
            
        Returns:
            Tuple of ({first_name, last_name}, metadata)
        """
        if not value or pd.isna(value):
            return {"first_name": None, "last_name": None}, {"valid": False, "error": "empty_value"}
        
        name_str = str(value).strip()
        
        # Handle "Last, First" format
        if ',' in name_str:
            parts = [p.strip() for p in name_str.split(',')]
            if len(parts) == 2:
                last = self._clean_name(parts[0])
                first = self._clean_name(parts[1])
                return {
                    "first_name": first,
                    "last_name": last
                }, {"valid": True, "original": value, "format": "last_first"}
        
        # Handle "First Last" format
        parts = name_str.split()
        
        # Remove titles
        while parts and parts[0].upper() in self.TITLES:
            parts.pop(0)
        
        # Remove suffixes from end
        while parts and parts[-1].upper() in self.SUFFIXES:
            parts.pop()
        
        if len(parts) == 0:
            return {"first_name": None, "last_name": None}, {"valid": False, "error": "no_name_parts"}
        
        if len(parts) == 1:
            return {
                "first_name": None,
                "last_name": self._clean_name(parts[0])
            }, {"valid": True, "original": value, "note": "single_name"}
        
        # Multiple parts - first is first name, rest is last name
        first = self._clean_name(parts[0])
        last = self._clean_name(' '.join(parts[1:]))
        
        return {
            "first_name": first,
            "last_name": last
        }, {"valid": True, "original": value, "format": "first_last"}
    
    def _clean_name(self, name: str) -> str:
        """Clean and normalize a name part."""
        # Remove extra whitespace and newlines
        cleaned = ' '.join(name.split())
        # Title case
        return cleaned.title()


class AgeParser(BaseNormalizer):
    """Parser for age range strings."""
    
    def normalize(self, value: Any) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Parse age range string into min_age, max_age, ages_served.
        
        Args:
            value: Age range string (e.g., "0-5", "Infant, Toddler")
            
        Returns:
            Tuple of ({min_age, max_age, ages_served}, metadata)
        """
        if not value or pd.isna(value):
            return {
                "min_age": None,
                "max_age": None,
                "ages_served": None
            }, {"valid": False, "error": "empty_value"}
        
        age_str = str(value).strip()
        
        # Try numeric range pattern (e.g., "0-5", "6 weeks to 12 years")
        result = self._parse_numeric_range(age_str)
        if result["min_age"] is not None:
            result["ages_served"] = age_str
            return result, {"valid": True, "parsed_from": "numeric_range"}
        
        # Try age group labels
        result = self._parse_age_groups(age_str)
        if result["min_age"] is not None:
            result["ages_served"] = age_str
            return result, {"valid": True, "parsed_from": "age_groups"}
        
        # Could not parse, but save the original
        return {
            "min_age": None,
            "max_age": None,
            "ages_served": age_str
        }, {"valid": False, "error": "could_not_parse", "original": age_str}
    
    def _parse_numeric_range(self, age_str: str) -> Dict[str, Optional[float]]:
        """Parse numeric age ranges like '0-5' or '6 weeks to 12 years'."""
        result = {"min_age": None, "max_age": None}
        
        # Pattern: "X-Y" or "X to Y"
        range_pattern = r'(\d+(?:\.\d+)?)\s*(?:weeks?|months?|years?)?\s*(?:-|to|–)\s*(\d+(?:\.\d+)?)\s*(?:weeks?|months?|years?)?'
        match = re.search(range_pattern, age_str, re.IGNORECASE)
        
        if match:
            min_val = float(match.group(1))
            max_val = float(match.group(2))
            
            # Convert weeks to years (approximate)
            if 'week' in age_str.lower():
                min_val = min_val / 52
                max_val = max_val / 52
            # Convert months to years
            elif 'month' in age_str.lower():
                min_val = min_val / 12
                max_val = max_val / 12
            
            result["min_age"] = round(min_val, 1)
            result["max_age"] = round(max_val, 1)
        
        return result
    
    def _parse_age_groups(self, age_str: str) -> Dict[str, Optional[float]]:
        """Parse age group labels like 'Infant, Toddler, Preschool'."""
        result = {"min_age": None, "max_age": None}
        
        # Split by common delimiters
        groups = re.split(r'[,;/&]|\band\b', age_str, flags=re.IGNORECASE)
        groups = [g.strip().lower() for g in groups if g.strip()]
        
        ages_found = []
        for group in groups:
            # Clean up the group name
            clean_group = re.sub(r'\s*\([^)]*\)', '', group)  # Remove parentheses
            clean_group = clean_group.strip()
            
            if clean_group in AGE_GROUP_RANGES:
                ages_found.append(AGE_GROUP_RANGES[clean_group])
        
        if ages_found:
            result["min_age"] = min(a[0] for a in ages_found)
            result["max_age"] = max(a[1] for a in ages_found)
        
        return result


class CapacityNormalizer(BaseNormalizer):
    """Normalizer for capacity values."""
    
    def normalize(self, value: Any) -> Tuple[Optional[int], Dict[str, Any]]:
        """
        Extract numeric capacity from string.
        
        Args:
            value: Capacity string (e.g., "50", "50 children", "N/A")
            
        Returns:
            Tuple of (capacity, metadata)
        """
        if not value or pd.isna(value):
            return None, {"valid": False, "error": "empty_value"}
        
        cap_str = str(value).strip()
        
        # Check for N/A, unknown, etc.
        invalid_values = {'n/a', 'na', 'unknown', 'none', '', 'null'}
        if cap_str.lower() in invalid_values:
            return None, {"valid": False, "error": "invalid_value", "original": value}
        
        # Extract digits
        digits = re.search(r'(\d+)', cap_str)
        
        if digits:
            capacity = int(digits.group(1))
            return capacity, {"valid": True, "original": value, "extracted_from": cap_str}
        
        return None, {"valid": False, "error": "no_digits_found", "original": value}


class LicenseStatusNormalizer(BaseNormalizer):
    """Normalizer for license status values."""
    
    # Valid status values
    VALID_STATUSES = {'Active', 'Inactive', 'Expired', 'Pending', 'Revoked', 'Unknown'}
    
    # Mapping variations to standard values
    STATUS_MAPPINGS = {
        # Active variations
        'active': 'Active',
        'true': 'Active',
        '1': 'Active',
        'open': 'Active',
        'licensed': 'Active',
        'current': 'Active',
        'valid': 'Active',
        'approved': 'Active',
        'full permit': 'Active',
        'permit': 'Active',
        # Inactive variations
        'inactive': 'Inactive',
        'false': 'Inactive',
        '0': 'Inactive',
        'closed': 'Inactive',
        'not active': 'Inactive',
        # Expired variations
        'expired': 'Expired',
        'lapsed': 'Expired',
        'terminated': 'Expired',
        # Pending variations
        'pending': 'Pending',
        'application': 'Pending',
        'in progress': 'Pending',
        'provisional': 'Pending',
        # Revoked variations
        'revoked': 'Revoked',
        'suspended': 'Revoked',
        'denied': 'Revoked',
        'cancelled': 'Revoked',
        'canceled': 'Revoked',
    }
    
    def normalize(self, value: Any) -> Tuple[str, Dict[str, Any]]:
        """
        Normalize license status to standard enum.
        
        Args:
            value: Status string
            
        Returns:
            Tuple of (normalized_status, metadata)
        """
        if not value or pd.isna(value):
            return 'Unknown', {"valid": True, "note": "empty_value_defaulted"}
        
        status_str = str(value).strip().lower()
        
        # Direct mapping
        if status_str in self.STATUS_MAPPINGS:
            normalized = self.STATUS_MAPPINGS[status_str]
            return normalized, {"valid": True, "original": value, "mapped_from": status_str}
        
        # Check if already valid
        if status_str.title() in self.VALID_STATUSES:
            return status_str.title(), {"valid": True, "original": value}
        
        # Unknown value
        return 'Unknown', {"valid": True, "note": "unrecognized_value", "original": value}
