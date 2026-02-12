"""Unit tests for database loading."""

import pytest
import pandas as pd
import tempfile
from pathlib import Path

from src.load.sqlite_loader import SQLiteLoader


class TestSQLiteLoader:
    """Tests for SQLiteLoader."""
    
    @pytest.fixture
    def temp_db(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            yield str(db_path)
    
    @pytest.fixture
    def sample_df(self):
        return pd.DataFrame({
            'company': ['ABC Daycare', 'XYZ Preschool'],
            'facility_type': ['Child Care Center', 'Preschool'],
            'address1': ['123 Main St', '456 Oak Ave'],
            'city': ['Springfield', 'Dallas'],
            'state': ['IL', 'TX'],
            'zip': ['62701', '75201'],
            'phone': ['(555) 123-4567', '(555) 987-6543'],
            'email': ['abc@test.com', 'xyz@test.com'],
            'capacity': [50, 30],
            'license_status': ['Active', 'Active'],
            'license_number': ['L12345', 'L67890'],
            'record_id': ['test_001', 'test_002'],
            'is_duplicate': [False, False],
            'data_quality_score': [95, 90]
        })
    
    def test_create_table(self, temp_db):
        loader = SQLiteLoader(f"sqlite:///{temp_db}")
        
        # Verify table was created
        stats = loader.get_stats()
        assert stats['table'] == 'leads'
        assert stats['total_records'] == 0
    
    def test_load_data(self, temp_db, sample_df):
        loader = SQLiteLoader(f"sqlite:///{temp_db}")
        
        stats = loader.load(sample_df)
        
        assert stats['inserted'] == 2
        assert stats['errors'] == 0
        
        # Verify data was loaded
        db_stats = loader.get_stats()
        assert db_stats['total_records'] == 2
    
    def test_upsert_existing(self, temp_db, sample_df):
        loader = SQLiteLoader(f"sqlite:///{temp_db}")
        
        # Load initial data
        loader.load(sample_df)
        
        # Modify and upsert
        updated_df = sample_df.copy()
        updated_df.loc[0, 'company'] = 'ABC Daycare Updated'
        
        stats = loader.upsert(updated_df)
        
        assert stats['updated'] == 2  # Both records exist
        
        # Verify update
        result = loader.query("SELECT * FROM leads WHERE record_id = 'test_001'")
        assert result[0]['company'] == 'ABC Daycare Updated'
    
    def test_query(self, temp_db, sample_df):
        loader = SQLiteLoader(f"sqlite:///{temp_db}")
        loader.load(sample_df)
        
        # Query specific records
        result = loader.query("SELECT * FROM leads WHERE state = ?", ('IL',))
        
        assert len(result) == 1
        assert result[0]['state'] == 'IL'
    
    def test_get_stats(self, temp_db, sample_df):
        loader = SQLiteLoader(f"sqlite:///{temp_db}")
        loader.load(sample_df)
        
        stats = loader.get_stats()
        
        assert 'total_records' in stats
        assert 'states' in stats
        assert 'quality' in stats
        assert stats['total_records'] == 2
