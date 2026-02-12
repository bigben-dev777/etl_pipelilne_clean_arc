"""End-to-end integration tests for the ETL pipeline."""

import pytest
import pandas as pd
import tempfile
from pathlib import Path

from src.main import ETLPipeline


class TestEndToEndPipeline:
    """End-to-end pipeline tests."""
    
    @pytest.fixture
    def temp_pipeline(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir) / "raw"
            output_dir = Path(tmpdir) / "processed"
            data_dir.mkdir()
            output_dir.mkdir()
            
            pipeline = ETLPipeline(
                data_dir=data_dir,
                output_dir=output_dir,
                use_ai=False  # Don't require LLM for tests
            )
            
            yield pipeline, data_dir, output_dir
    
    def test_extract_csv(self, temp_pipeline):
        pipeline, data_dir, _ = temp_pipeline
        
        # Create test CSV
        test_csv = data_dir / "test_data.csv"
        test_csv.write_text("""Name,Type,Address,Phone,Status
ABC Daycare,CENTER,123 Main St Springfield IL 62701,555-123-4567,Active
XYZ Preschool,FAMILY CARE,456 Oak Ave Dallas TX 75201,555-987-6543,Active""")
        
        # Extract
        raw_data = pipeline.extract("*.csv")
        
        assert len(raw_data) == 1
        assert "test_data.csv" in raw_data
        assert len(raw_data["test_data.csv"]) == 2
    
    def test_full_pipeline_run(self, temp_pipeline):
        pipeline, data_dir, _ = temp_pipeline
        
        # Create test CSV
        test_csv = data_dir / "test_data.csv"
        test_csv.write_text("""Name,Credential Type,Address,Phone,Status
ABC Daycare,CENTER,123 Main St Springfield IL 62701,555-123-4567,Active
XYZ Preschool,FAMILY CARE,456 Oak Ave Dallas TX 75201,555-987-6543,Active""")
        
        # Run full pipeline
        stats = pipeline.run("*.csv")
        
        assert stats['extraction']['files_processed'] == 1
        assert stats['extraction']['total_records'] == 2
        assert stats['transformation']['records_transformed'] == 2
        assert stats['loading']['inserted'] == 2
    
    def test_pipeline_with_duplicates(self, temp_pipeline):
        pipeline, data_dir, _ = temp_pipeline
        
        # Create test CSV with duplicates
        test_csv = data_dir / "test_data.csv"
        test_csv.write_text("""Name,Credential Type,Address,Phone,Status
ABC Daycare,CENTER,123 Main St Springfield IL 62701,555-123-4567,Active
ABC Daycare Center,CENTER,123 Main Street Springfield IL 62701,555-123-4567,Active
XYZ Preschool,FAMILY CARE,456 Oak Ave Dallas TX 75201,555-987-6543,Active""")
        
        # Run pipeline
        stats = pipeline.run("*.csv")
        
        # Should detect at least one duplicate
        assert stats['transformation']['duplicates_found'] >= 1
    
    def test_multiple_files(self, temp_pipeline):
        pipeline, data_dir, _ = temp_pipeline
        
        # Create multiple test files
        (data_dir / "file1.csv").write_text("""Name,Type,Address,Phone
ABC Daycare,CENTER,123 Main St Springfield IL 62701,555-111-1111""")
        
        (data_dir / "file2.csv").write_text("""Name,Type,Address,Phone
XYZ Preschool,FAMILY CARE,456 Oak Ave Dallas TX 75201,555-222-2222""")
        
        # Run pipeline
        stats = pipeline.run("*.csv")
        
        assert stats['extraction']['files_processed'] == 2
        assert stats['extraction']['total_records'] == 2
