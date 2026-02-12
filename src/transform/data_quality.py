"""Data quality scoring module for facility lead records."""

import json
from typing import Dict, Any, List, Optional, Tuple
import pandas as pd
import logging

from src.utils.validators import validate_email, validate_phone, validate_zip, validate_state

logger = logging.getLogger(__name__)


class DataQualityScorer:
    """Scores data quality for facility lead records."""
    
    # Quality check weights (must sum to 100)
    WEIGHTS = {
        'company': 15,
        'phone': 15,
        'email': 10,
        'address': 15,
        'capacity': 10,
        'license': 10,
        'contact_name': 10,
        'age_info': 10,
        'not_duplicate': 5,
    }
    
    def __init__(self):
        """Initialize the data quality scorer."""
        self.flags = []
    
    def score_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate data quality scores for all records in a DataFrame.
        
        Args:
            df: DataFrame with facility lead data
            
        Returns:
            DataFrame with added quality_score and quality_flags columns
        """
        logger.info(f"Scoring data quality for {len(df)} records")
        
        scores = []
        flags_list = []
        
        for idx, row in df.iterrows():
            score, flags = self._score_record(row)
            scores.append(score)
            flags_list.append(json.dumps(flags) if flags else None)
        
        result = df.copy()
        result['data_quality_score'] = scores
        result['data_quality_flags'] = flags_list
        
        # Log quality summary
        avg_score = sum(scores) / len(scores) if scores else 0
        logger.info(f"Average data quality score: {avg_score:.1f}/100")
        
        return result
    
    def _score_record(self, row: pd.Series) -> Tuple[int, List[str]]:
        """
        Score a single record's data quality.
        
        Args:
            row: DataFrame row with record data
            
        Returns:
            Tuple of (score, flags)
        """
        score = 0
        flags = []
        
        # Check company name
        company_score, company_flags = self._check_company(row.get('company'))
        score += company_score
        flags.extend(company_flags)
        
        # Check phone
        phone_score, phone_flags = self._check_phone(row.get('phone'))
        score += phone_score
        flags.extend(phone_flags)
        
        # Check email
        email_score, email_flags = self._check_email(row.get('email'))
        score += email_score
        flags.extend(email_flags)
        
        # Check address
        address_score, address_flags = self._check_address(row)
        score += address_score
        flags.extend(address_flags)
        
        # Check capacity
        capacity_score, capacity_flags = self._check_capacity(row.get('capacity'))
        score += capacity_score
        flags.extend(capacity_flags)
        
        # Check license info
        license_score, license_flags = self._check_license(row)
        score += license_score
        flags.extend(license_flags)
        
        # Check contact name
        name_score, name_flags = self._check_contact_name(row)
        score += name_score
        flags.extend(name_flags)
        
        # Check age information
        age_score, age_flags = self._check_age_info(row)
        score += age_score
        flags.extend(age_flags)
        
        # Check duplicate flag
        duplicate_score, duplicate_flags = self._check_duplicate(row.get('is_duplicate'))
        score += duplicate_score
        flags.extend(duplicate_flags)
        
        return score, flags
    
    def _check_company(self, company: Any) -> Tuple[int, List[str]]:
        """Check company name quality."""
        if not company or pd.isna(company):
            return 0, ['missing_company']
        
        company_str = str(company).strip()
        
        if len(company_str) < 2:
            return 5, ['company_too_short']
        
        # Check for generic/bad values
        bad_values = ['unknown', 'n/a', 'na', 'none', 'null', 'test']
        if company_str.lower() in bad_values:
            return 5, ['company_generic_value']
        
        return self.WEIGHTS['company'], []
    
    def _check_phone(self, phone: Any) -> Tuple[int, List[str]]:
        """Check phone number quality."""
        if not phone or pd.isna(phone):
            return 0, ['missing_phone']
        
        is_valid, _, _ = validate_phone(str(phone))
        
        if is_valid:
            return self.WEIGHTS['phone'], []
        else:
            return 5, ['invalid_phone_format']
    
    def _check_email(self, email: Any) -> Tuple[int, List[str]]:
        """Check email quality."""
        if not email or pd.isna(email):
            return 0, ['missing_email']
        
        is_valid, _ = validate_email(str(email))
        
        if is_valid:
            return self.WEIGHTS['email'], []
        else:
            return 0, ['invalid_email_format']
    
    def _check_address(self, row: pd.Series) -> Tuple[int, List[str]]:
        """Check address completeness."""
        flags = []
        
        address1 = row.get('address1')
        city = row.get('city')
        state = row.get('state')
        zip_code = row.get('zip')
        
        # Count present fields
        present = sum([
            1 for x in [address1, city, state, zip_code]
            if x and not pd.isna(x)
        ])
        
        if present == 4:
            # Validate state and zip
            state_valid, _ = validate_state(str(state) if state else '')
            zip_valid, _ = validate_zip(str(zip_code) if zip_code else '')
            
            if state_valid and zip_valid:
                return self.WEIGHTS['address'], []
            else:
                if not state_valid:
                    flags.append('invalid_state')
                if not zip_valid:
                    flags.append('invalid_zip')
                return 10, flags
        
        elif present >= 2:
            flags.append('incomplete_address')
            return 8, flags
        
        elif present >= 1:
            flags.append('incomplete_address')
            return 5, flags
        
        else:
            return 0, ['missing_address']
    
    def _check_capacity(self, capacity: Any) -> Tuple[int, List[str]]:
        """Check capacity value."""
        if capacity is None or pd.isna(capacity):
            return 0, ['missing_capacity']
        
        try:
            cap_val = float(capacity)
            if cap_val <= 0:
                return 0, ['invalid_capacity']
            elif cap_val > 1000:
                return 5, ['capacity_unusually_high']
            else:
                return self.WEIGHTS['capacity'], []
        except (ValueError, TypeError):
            return 0, ['invalid_capacity']
    
    def _check_license(self, row: pd.Series) -> Tuple[int, List[str]]:
        """Check license information."""
        license_num = row.get('license_number')
        license_status = row.get('license_status')
        
        if license_num and not pd.isna(license_num):
            if license_status and not pd.isna(license_status):
                return self.WEIGHTS['license'], []
            else:
                return 5, ['missing_license_status']
        
        if license_status and not pd.isna(license_status):
            return 5, ['missing_license_number']
        
        return 0, ['missing_license_info']
    
    def _check_contact_name(self, row: pd.Series) -> Tuple[int, List[str]]:
        """Check contact name completeness."""
        first = row.get('first_name')
        last = row.get('last_name')
        
        has_first = first and not pd.isna(first)
        has_last = last and not pd.isna(last)
        
        if has_first and has_last:
            return self.WEIGHTS['contact_name'], []
        elif has_first or has_last:
            return 5, ['partial_contact_name']
        else:
            return 0, ['missing_contact_name']
    
    def _check_age_info(self, row: pd.Series) -> Tuple[int, List[str]]:
        """Check age information."""
        min_age = row.get('min_age')
        max_age = row.get('max_age')
        ages_served = row.get('ages_served')
        
        has_min_max = (min_age is not None and not pd.isna(min_age) and
                       max_age is not None and not pd.isna(max_age))
        has_ages_served = ages_served and not pd.isna(ages_served)
        
        if has_min_max:
            return self.WEIGHTS['age_info'], []
        elif has_ages_served:
            return 5, ['ages_served_only']
        else:
            return 0, ['missing_age_info']
    
    def _check_duplicate(self, is_duplicate: Any) -> Tuple[int, List[str]]:
        """Check if record is marked as duplicate."""
        if is_duplicate is True or (isinstance(is_duplicate, str) and is_duplicate.lower() == 'true'):
            return 0, ['marked_duplicate']
        
        return self.WEIGHTS['not_duplicate'], []
    
    def get_quality_summary(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Get summary statistics for data quality.
        
        Args:
            df: DataFrame with quality scores
            
        Returns:
            Dictionary with quality summary
        """
        if 'data_quality_score' not in df.columns:
            return {"error": "DataFrame does not have quality scores"}
        
        scores = df['data_quality_score']
        
        # Collect all flags
        all_flags = []
        for flags_json in df['data_quality_flags'].dropna():
            all_flags.extend(json.loads(flags_json))
        
        flag_counts = pd.Series(all_flags).value_counts().to_dict()
        
        return {
            "total_records": len(df),
            "average_score": round(scores.mean(), 2),
            "median_score": round(scores.median(), 2),
            "min_score": int(scores.min()),
            "max_score": int(scores.max()),
            "score_distribution": {
                "excellent (90-100)": int((scores >= 90).sum()),
                "good (70-89)": int(((scores >= 70) & (scores < 90)).sum()),
                "fair (50-69)": int(((scores >= 50) & (scores < 70)).sum()),
                "poor (30-49)": int(((scores >= 30) & (scores < 50)).sum()),
                "critical (0-29)": int((scores < 30).sum()),
            },
            "common_issues": dict(list(flag_counts.items())[:10]),
        }
