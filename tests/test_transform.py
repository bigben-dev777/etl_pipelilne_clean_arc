"""Unit tests for transformation components."""

import pytest
import pandas as pd
import numpy as np
from pathlib import Path

from src.transform.schema_mapper import SchemaMapper
from src.transform.data_quality import DataQualityScorer
from src.transform.deduplication import DuplicateDetector


class TestSchemaMapper:
    """Tests for SchemaMapper."""
    
    @pytest.fixture
    def sample_df(self):
        return pd.DataFrame({
            'Name': ['ABC Daycare', 'XYZ Preschool'],
            'Credential Type': ['CENTER', 'FAMILY CARE'],
            'Address': ['123 Main St, Springfield, IL 62701', '456 Oak Ave, Dallas, TX 75201'],
            'Phone': ['555-123-4567', '555-987-6543'],
            'Status': ['Active', 'Active']
        })
    
    def test_map_dataframe_basic(self, sample_df):
        mapper = SchemaMapper()
        
        result = mapper.map_dataframe(
            sample_df,
            source_file=Path("test.csv")
        )
        
        assert 'company' in result.columns
        assert 'phone' in result.columns
        assert 'state' in result.columns
        assert len(result) == 2
    
    def test_phone_normalization(self, sample_df):
        mapper = SchemaMapper()
        
        result = mapper.map_dataframe(
            sample_df,
            source_file=Path("test.csv")
        )
        
        # Phone should be normalized
        assert result['phone'].iloc[0] == "(555) 123-4567"
    
    def test_address_parsing(self, sample_df):
        mapper = SchemaMapper()
        
        result = mapper.map_dataframe(
            sample_df,
            source_file=Path("test.csv")
        )
        
        # Address should be parsed
        assert 'city' in result.columns
        assert 'state' in result.columns
        assert 'zip' in result.columns


class TestDataQualityScorer:
    """Tests for DataQualityScorer."""
    
    @pytest.fixture
    def good_record_df(self):
        return pd.DataFrame({
            'company': ['ABC Daycare'],
            'phone': ['(555) 123-4567'],
            'email': ['test@example.com'],
            'address1': ['123 Main St'],
            'city': ['Springfield'],
            'state': ['IL'],
            'zip': ['62701'],
            'capacity': [50],
            'license_number': ['L12345'],
            'license_status': ['Active'],
            'first_name': ['John'],
            'last_name': ['Smith'],
            'min_age': [0],
            'max_age': [5],
            'is_duplicate': [False]
        })
    
    @pytest.fixture
    def poor_record_df(self):
        return pd.DataFrame({
            'company': [None],
            'phone': [None],
            'email': ['invalid-email'],
            'address1': [None],
            'city': [None],
            'state': [None],
            'zip': [None],
            'capacity': [None],
            'license_number': [None],
            'license_status': [None],
            'first_name': [None],
            'last_name': [None],
            'min_age': [None],
            'max_age': [None],
            'is_duplicate': [True]
        })
    
    def test_good_record_score(self, good_record_df):
        scorer = DataQualityScorer()
        result = scorer.score_dataframe(good_record_df)
        
        assert result['data_quality_score'].iloc[0] >= 90
    
    def test_poor_record_score(self, poor_record_df):
        scorer = DataQualityScorer()
        result = scorer.score_dataframe(poor_record_df)
        
        assert result['data_quality_score'].iloc[0] < 50
    
    def test_quality_flags(self, poor_record_df):
        scorer = DataQualityScorer()
        result = scorer.score_dataframe(poor_record_df)
        
        flags = result['data_quality_flags'].iloc[0]
        assert flags is not None


class TestDuplicateDetector:
    """Tests for DuplicateDetector."""
    
    @pytest.fixture
    def df_with_duplicates(self):
        return pd.DataFrame({
            'company': ['ABC Daycare', 'ABC Daycare', 'XYZ Preschool'],
            'phone': ['555-123-4567', '555-123-4567', '555-987-6543'],
            'email': ['abc@test.com', 'abc@test.com', 'xyz@test.com'],
            'address1': ['123 Main St', '123 Main Street', '456 Oak Ave'],
            'city': ['Springfield', 'Springfield', 'Dallas'],
            'state': ['IL', 'IL', 'TX']
        })
    
    def test_detect_exact_duplicates(self, df_with_duplicates):
        detector = DuplicateDetector()
        result = detector.detect_duplicates(df_with_duplicates)
        
        assert 'is_duplicate' in result.columns
        assert 'duplicate_cluster_id' in result.columns
        assert result['is_duplicate'].sum() > 0
    
    def test_duplicate_clusters(self, df_with_duplicates):
        detector = DuplicateDetector()
        result = detector.detect_duplicates(df_with_duplicates)
        
        # Duplicates should have same cluster ID
        cluster_ids = result['duplicate_cluster_id'].unique()
        assert len(cluster_ids) < len(result)
    
    def test_duplicate_summary(self, df_with_duplicates):
        detector = DuplicateDetector()
        result = detector.detect_duplicates(df_with_duplicates)
        
        summary = detector.get_duplicate_summary(result)
        
        assert 'total_records' in summary
        assert 'duplicate_records' in summary
        assert summary['total_records'] == len(df_with_duplicates)


class TestEndToEndTransform:
    """End-to-end transformation tests."""
    
    def test_full_pipeline_on_sample(self):
        # Create sample data
        df = pd.DataFrame({
            'Name': ['ABC Daycare', 'XYZ Preschool'],
            'Credential Type': ['CENTER', 'FAMILY CARE'],
            'Address': ['123 Main St, Springfield, IL 62701', '456 Oak Ave, Dallas, TX 75201'],
            'Phone': ['555-123-4567', '555-987-6543'],
            'Status': ['Active', 'Active'],
            'Primary Contact Name': ['John Smith', 'Jane Doe']
        })
        
        # Map schema
        mapper = SchemaMapper()
        result = mapper.map_dataframe(df, source_file=Path("test.csv"))
        
        # Detect duplicates
        detector = DuplicateDetector()
        result = detector.detect_duplicates(result)
        
        # Score quality
        scorer = DataQualityScorer()
        result = scorer.score_dataframe(result)
        
        # Verify results
        assert len(result) == 2
        assert 'data_quality_score' in result.columns
        assert 'is_duplicate' in result.columns
