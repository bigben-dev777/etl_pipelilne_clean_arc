"""Validation utilities for common data fields."""

import re
from typing import Tuple, Optional


# Email validation regex
EMAIL_REGEX = re.compile(
    r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
)

# Phone validation - extracts digits
PHONE_REGEX = re.compile(r'\D')

# ZIP code validation
ZIP_REGEX = re.compile(r'^\d{5}(-\d{4})?$')


def validate_email(email: Optional[str]) -> Tuple[bool, Optional[str]]:
    """
    Validate an email address.
    
    Args:
        email: Email address to validate
        
    Returns:
        Tuple of (is_valid, normalized_email)
    """
    if not email or not isinstance(email, str):
        return False, None
    
    # Clean the email
    cleaned = email.strip().lower()
    
    # Remove common prefixes/suffixes that get added accidentally
    cleaned = re.sub(r'^[\s\n\r]+|[\s\n\r]+$', '', cleaned)
    
    if not cleaned or len(cleaned) > 254:
        return False, None
    
    if EMAIL_REGEX.match(cleaned):
        return True, cleaned
    
    return False, None


def validate_phone(phone: Optional[str]) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Validate and normalize a phone number.
    
    Args:
        phone: Phone number to validate
        
    Returns:
        Tuple of (is_valid, normalized_digits, formatted_number)
    """
    if not phone or not isinstance(phone, str):
        return False, None, None
    
    # Extract all digits
    digits = PHONE_REGEX.sub('', phone)
    
    # Handle country code
    if digits.startswith('1') and len(digits) == 11:
        digits = digits[1:]
    
    # Validate length
    if len(digits) != 10:
        return False, digits if digits else None, None
    
    # Format as (XXX) XXX-XXXX
    formatted = f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
    
    return True, digits, formatted


def validate_zip(zip_code: Optional[str]) -> Tuple[bool, Optional[str]]:
    """
    Validate and normalize a ZIP code.
    
    Args:
        zip_code: ZIP code to validate
        
    Returns:
        Tuple of (is_valid, normalized_zip)
    """
    if not zip_code or not isinstance(zip_code, str):
        return False, None
    
    # Clean the input
    cleaned = zip_code.strip().upper()
    
    # Extract just digits and hyphen
    cleaned = re.sub(r'[^\d-]', '', cleaned)
    
    # Check if it's a 5-digit or ZIP+4 format
    if ZIP_REGEX.match(cleaned):
        # Normalize to 5-digit
        normalized = cleaned[:5]
        return True, normalized
    
    # Try to handle short ZIPs (e.g., "9021" -> "09021")
    digits_only = re.sub(r'\D', '', cleaned)
    if len(digits_only) == 4:
        return True, f"0{digits_only}"
    elif len(digits_only) == 5:
        return True, digits_only
    
    return False, digits_only if digits_only else None


def validate_state(state: Optional[str]) -> Tuple[bool, Optional[str]]:
    """
    Validate and normalize a US state.
    
    Args:
        state: State name or abbreviation
        
    Returns:
        Tuple of (is_valid, normalized_abbreviation)
    """
    if not state or not isinstance(state, str):
        return False, None
    
    from ..transform.normalizers import STATE_ABBREVIATIONS, STATE_NAME_TO_ABBR
    
    cleaned = state.strip().upper()
    
    # Already an abbreviation
    if cleaned in STATE_ABBREVIATIONS:
        return True, cleaned
    
    # Full name lookup
    normalized = cleaned.title()
    if normalized in STATE_NAME_TO_ABBR:
        return True, STATE_NAME_TO_ABBR[normalized]
    
    # Try common variations
    variations = {
        'CALIF': 'CA',
        'CALIFORNIA': 'CA',
        'TEX': 'TX',
        'TEXAS': 'TX',
        'NEV': 'NV',
        'NEVADA': 'NV',
        'OKLA': 'OK',
        'OKLAHOMA': 'OK',
    }
    
    if cleaned in variations:
        return True, variations[cleaned]
    
    return False, None
