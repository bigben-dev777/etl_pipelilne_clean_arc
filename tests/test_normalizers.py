"""Unit tests for field normalizers."""

import pytest
import pandas as pd
from src.transform.normalizers import (
    PhoneNormalizer,
    StateNormalizer,
    ZipNormalizer,
    AddressNormalizer,
    NameNormalizer,
    AgeParser,
    CapacityNormalizer,
    LicenseStatusNormalizer,
)


class TestPhoneNormalizer:
    """Tests for PhoneNormalizer."""
    
    def test_valid_phone_with_formatting(self):
        normalizer = PhoneNormalizer()
        result, meta = normalizer.normalize("(555) 123-4567")
        assert result == "(555) 123-4567"
        assert meta["valid"] is True
    
    def test_valid_phone_digits_only(self):
        normalizer = PhoneNormalizer()
        result, meta = normalizer.normalize("5551234567")
        assert result == "(555) 123-4567"
        assert meta["valid"] is True
    
    def test_valid_phone_with_country_code(self):
        normalizer = PhoneNormalizer()
        result, meta = normalizer.normalize("+1-555-123-4567")
        assert result == "(555) 123-4567"
        assert meta["valid"] is True
    
    def test_valid_phone_with_dots(self):
        normalizer = PhoneNormalizer()
        result, meta = normalizer.normalize("555.123.4567")
        assert result == "(555) 123-4567"
        assert meta["valid"] is True
    
    def test_invalid_phone_too_short(self):
        normalizer = PhoneNormalizer()
        result, meta = normalizer.normalize("555-1234")
        assert result is None
        assert meta["valid"] is False
    
    def test_invalid_phone_empty(self):
        normalizer = PhoneNormalizer()
        result, meta = normalizer.normalize("")
        assert result is None
        assert meta["valid"] is False
    
    def test_invalid_phone_none(self):
        normalizer = PhoneNormalizer()
        result, meta = normalizer.normalize(None)
        assert result is None
        assert meta["valid"] is False


class TestStateNormalizer:
    """Tests for StateNormalizer."""
    
    def test_valid_abbreviation(self):
        normalizer = StateNormalizer()
        result, meta = normalizer.normalize("CA")
        assert result == "CA"
        assert meta["valid"] is True
    
    def test_valid_full_name(self):
        normalizer = StateNormalizer()
        result, meta = normalizer.normalize("California")
        assert result == "CA"
        assert meta["valid"] is True
    
    def test_valid_lowercase(self):
        normalizer = StateNormalizer()
        result, meta = normalizer.normalize("texas")
        assert result == "TX"
        assert meta["valid"] is True
    
    def test_valid_variation(self):
        normalizer = StateNormalizer()
        result, meta = normalizer.normalize("Calif")
        assert result == "CA"
        assert meta["valid"] is True
    
    def test_invalid_state(self):
        normalizer = StateNormalizer()
        result, meta = normalizer.normalize("XYZ")
        assert result is None
        assert meta["valid"] is False


class TestZipNormalizer:
    """Tests for ZipNormalizer."""
    
    def test_valid_5_digit(self):
        normalizer = ZipNormalizer()
        result, meta = normalizer.normalize("90210")
        assert result == "90210"
        assert meta["valid"] is True
    
    def test_valid_zip4(self):
        normalizer = ZipNormalizer()
        result, meta = normalizer.normalize("90210-1234")
        assert result == "90210"
        assert meta["valid"] is True
    
    def test_valid_padded_4_digit(self):
        normalizer = ZipNormalizer()
        result, meta = normalizer.normalize("9021")
        assert result == "09021"
        assert meta["valid"] is True
    
    def test_invalid_empty(self):
        normalizer = ZipNormalizer()
        result, meta = normalizer.normalize("")
        assert result is None
        assert meta["valid"] is False
    
    def test_invalid_too_long(self):
        normalizer = ZipNormalizer()
        result, meta = normalizer.normalize("12345678901")
        assert result is None
        assert meta["valid"] is False


class TestAddressNormalizer:
    """Tests for AddressNormalizer."""
    
    def test_parse_combined_address(self):
        normalizer = AddressNormalizer()
        result, meta = normalizer.normalize("123 Main St, Springfield, IL 62701")
        
        assert result["address1"] is not None
        assert result["city"] == "Springfield"
        assert result["state"] == "IL"
        assert result["zip"] == "62701"
    
    def test_parse_with_suite(self):
        normalizer = AddressNormalizer()
        result, meta = normalizer.normalize("123 Main St, Suite 200, Springfield, IL 62701")
        
        assert result["address1"] is not None
        assert result["city"] == "Springfield"
        assert result["state"] == "IL"
    
    def test_empty_address(self):
        normalizer = AddressNormalizer()
        result, meta = normalizer.normalize("")
        
        assert result["address1"] is None
        assert result["city"] is None
        assert meta["valid"] is False


class TestNameNormalizer:
    """Tests for NameNormalizer."""
    
    def test_first_last_format(self):
        normalizer = NameNormalizer()
        result, meta = normalizer.normalize("John Smith")
        
        assert result["first_name"] == "John"
        assert result["last_name"] == "Smith"
    
    def test_last_first_format(self):
        normalizer = NameNormalizer()
        result, meta = normalizer.normalize("Smith, John")
        
        assert result["first_name"] == "John"
        assert result["last_name"] == "Smith"
    
    def test_with_title(self):
        normalizer = NameNormalizer()
        result, meta = normalizer.normalize("Dr. Jane Doe")
        
        assert result["first_name"] == "Jane"
        assert result["last_name"] == "Doe"
    
    def test_single_name(self):
        normalizer = NameNormalizer()
        result, meta = normalizer.normalize("Madonna")
        
        assert result["first_name"] is None
        assert result["last_name"] == "Madonna"
    
    def test_empty_name(self):
        normalizer = NameNormalizer()
        result, meta = normalizer.normalize("")
        
        assert result["first_name"] is None
        assert result["last_name"] is None


class TestAgeParser:
    """Tests for AgeParser."""
    
    def test_numeric_range(self):
        parser = AgeParser()
        result, meta = parser.normalize("0-5")
        
        assert result["min_age"] == 0
        assert result["max_age"] == 5
    
    def test_age_groups(self):
        parser = AgeParser()
        result, meta = parser.normalize("Infant, Toddler, Preschool")
        
        assert result["min_age"] == 0
        assert result["max_age"] == 5
    
    def test_weeks_to_years(self):
        parser = AgeParser()
        result, meta = parser.normalize("6 weeks to 12 years")
        
        assert result["min_age"] is not None
        assert result["max_age"] == 12
    
    def test_ages_served_preserved(self):
        parser = AgeParser()
        result, meta = parser.normalize("Infant through School Age")
        
        assert result["ages_served"] == "Infant through School Age"


class TestCapacityNormalizer:
    """Tests for CapacityNormalizer."""
    
    def test_numeric_capacity(self):
        normalizer = CapacityNormalizer()
        result, meta = normalizer.normalize("50")
        
        assert result == 50
        assert meta["valid"] is True
    
    def test_string_with_number(self):
        normalizer = CapacityNormalizer()
        result, meta = normalizer.normalize("50 children")
        
        assert result == 50
        assert meta["valid"] is True
    
    def test_na_value(self):
        normalizer = CapacityNormalizer()
        result, meta = normalizer.normalize("N/A")
        
        assert result is None
        assert meta["valid"] is False
    
    def test_unknown_value(self):
        normalizer = CapacityNormalizer()
        result, meta = normalizer.normalize("unknown")
        
        assert result is None
        assert meta["valid"] is False


class TestLicenseStatusNormalizer:
    """Tests for LicenseStatusNormalizer."""
    
    def test_active_variations(self):
        normalizer = LicenseStatusNormalizer()
        
        variations = ["Active", "true", "1", "OPEN", "Licensed", "Current", "Full Permit"]
        for var in variations:
            result, meta = normalizer.normalize(var)
            assert result == "Active", f"Failed for: {var}"
    
    def test_inactive_variations(self):
        normalizer = LicenseStatusNormalizer()
        
        variations = ["Inactive", "false", "0", "closed"]
        for var in variations:
            result, meta = normalizer.normalize(var)
            assert result == "Inactive", f"Failed for: {var}"
    
    def test_empty_defaults_unknown(self):
        normalizer = LicenseStatusNormalizer()
        result, meta = normalizer.normalize("")
        
        assert result == "Unknown"
    
    def test_unrecognized_value(self):
        normalizer = LicenseStatusNormalizer()
        result, meta = normalizer.normalize("SomeRandomStatus")
        
        assert result == "Unknown"
