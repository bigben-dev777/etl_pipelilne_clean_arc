"""
Main orchestrator for the Facility Lead ETL Pipeline.

This module provides the main entry point for running the ETL pipeline,
coordinating extraction, transformation, and loading of facility lead data.
"""

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
from dotenv import load_dotenv

# Add project root to path for absolute imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from config.settings import get_settings
from src.extract.csv_extractor import CSVExtractor, ExcelExtractor
from src.extract.source_registry import SourceRegistry, get_source_config
from src.load.sqlite_loader import SQLiteLoader
from src.transform.ai.facility_classifier import FacilityClassifier
from src.transform.ai.llm_client import get_llm_client
from src.transform.data_quality import DataQualityScorer
from src.transform.deduplication import DuplicateDetector
from src.transform.schema_mapper import SchemaMapper
from src.utils.hashing import compute_record_hash
from src.utils.logging_config import configure_logging, get_logger

load_dotenv()
logger = get_logger(__name__)


class ETLPipeline:
    """Main ETL pipeline orchestrator."""

    def __init__(
        self,
        data_dir: Optional[Path] = None,
        output_dir: Optional[Path] = None,
        db_url: Optional[str] = None,
        use_ai: bool = True,
        batch_id: Optional[str] = None,
    ):
        """
        Initialize the ETL pipeline.

        Args:
            data_dir: Directory containing source data files
            output_dir: Directory for output files
            db_url: Database connection URL
            use_ai: Whether to use AI/LLM features
            batch_id: Batch identifier for this run
        """
        self.settings = get_settings()

        self.data_dir = data_dir or self.settings.RAW_DATA_DIR
        self.output_dir = output_dir or self.settings.PROCESSED_DIR
        self.db_url = db_url or self.settings.DATABASE_URL
        self.use_ai = use_ai
        self.batch_id = batch_id or f"batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # Initialize components
        self.source_registry = SourceRegistry()
        self.llm_client = None
        self.facility_classifier = None

        if self.use_ai:
            try:
                self.llm_client = get_llm_client(provider=self.settings.LLM_PROVIDER)
                self.facility_classifier = FacilityClassifier(self.llm_client)
                logger.info("AI/LLM features enabled")
            except Exception as e:
                logger.warning(f"Could not initialize LLM client: {e}")
                logger.warning("Running in rule-based mode only")
                self.use_ai = False

        # Initialize other components
        self.schema_mapper = SchemaMapper(
            source_registry=self.source_registry,
            llm_client=self.llm_client,
            use_ai_mapping=self.use_ai,
            # logic_file=self.settings.SCHEMA_MAPPING_LOGIC_FILE,
        )
        self.data_quality_scorer = DataQualityScorer()
        self.duplicate_detector = DuplicateDetector(
            llm_client=self.llm_client, use_ai_resolution=self.use_ai
        )

        # Ensure output directory exists
        self.output_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"ETL Pipeline initialized (batch: {self.batch_id})")

    def run(self, file_pattern: str = "*") -> Dict[str, Any]:
        """
        Run the complete ETL pipeline.

        Args:
            file_pattern: Glob pattern for matching source files

        Returns:
            Dictionary with pipeline statistics
        """
        logger.info("=" * 60)
        logger.info("Starting ETL Pipeline")
        logger.info("=" * 60)

        start_time = datetime.now()

        # Step 1: Extract
        raw_data = self.extract(file_pattern)

        # Step 2: Transform
        transformed_data = self.transform(raw_data)

        # Step 3: Load
        load_stats = self.load(transformed_data)

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        # Compile statistics
        stats = {
            "batch_id": self.batch_id,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "duration_seconds": duration,
            "extraction": {
                "files_processed": len(raw_data),
                "total_records": sum(len(df) for df in raw_data.values()),
            },
            "transformation": {
                "records_transformed": (
                    len(transformed_data) if transformed_data is not None else 0
                ),
                "duplicates_found": (
                    int(transformed_data["is_duplicate"].sum())
                    if transformed_data is not None
                    else 0
                ),
                "avg_quality_score": (
                    transformed_data["data_quality_score"].mean()
                    if transformed_data is not None
                    and "data_quality_score" in transformed_data.columns
                    else 0
                ),
            },
            "loading": load_stats,
        }

        logger.info("=" * 60)
        logger.info("ETL Pipeline Complete")
        logger.info(f"Duration: {duration:.2f} seconds")
        logger.info(
            f"Records processed: {stats['transformation']['records_transformed']}"
        )
        logger.info("=" * 60)

        return stats

    def extract(self, file_pattern: str = "*") -> Dict[str, pd.DataFrame]:
        """
        Extract data from source files.

        Args:
            file_pattern: Glob pattern for matching source files

        Returns:
            Dictionary mapping file names to DataFrames
        """
        logger.info("Step 1: Extracting data from source files")

        raw_data = {}

        # Find source files
        source_files = []
        for ext in ["csv", "xlsx", "xls"]:
            source_files.extend(self.data_dir.glob(f"{file_pattern}.{ext}"))

        if not source_files:
            logger.warning(
                f"No source files found in {self.data_dir} matching '{file_pattern}'"
            )
            return raw_data

        logger.info(f"Found {len(source_files)} source files")

        for file_path in source_files:
            try:
                logger.info(f"Extracting: {file_path.name}")

                # Choose extractor based on file type
                if file_path.suffix.lower() in [".xlsx", ".xls"]:
                    extractor = ExcelExtractor(file_path)
                else:
                    extractor = CSVExtractor(file_path)

                df = extractor.extract()

                # Add source metadata
                df["_source_file"] = file_path.name
                df["_extraction_time"] = datetime.now()

                raw_data[file_path.name] = df

                logger.info(f"  Extracted {len(df)} rows, {len(df.columns)} columns")

            except Exception as e:
                logger.error(f"Failed to extract {file_path.name}: {e}")

        logger.info(f"Extraction complete: {len(raw_data)} files")

        return raw_data

    def transform(self, raw_data: Dict[str, pd.DataFrame]) -> Optional[pd.DataFrame]:
        """
        Transform raw data to target schema.

        Args:
            raw_data: Dictionary of extracted DataFrames

        Returns:
            Transformed and combined DataFrame
        """
        logger.info("Step 2: Transforming data")

        if not raw_data:
            logger.warning("No data to transform")
            return None

        transformed_dfs = []

        for file_name, df in raw_data.items():
            try:
                logger.info(f"Transforming: {file_name}")

                # Get source configuration
                source_config = self.source_registry.get_source_for_file(
                    Path(file_name)
                )

                # Map to target schema
                transformed = self.schema_mapper.map_dataframe(
                    df, source_file=Path(file_name), source_config=source_config
                )

                # Classify facility types if needed
                if "facility_type" in transformed.columns and self.facility_classifier:
                    descriptions = transformed["facility_type"].fillna("").tolist()
                    classifications = self.facility_classifier.classify(descriptions)

                    transformed["facility_type"] = [
                        c["category"] for c in classifications
                    ]
                    transformed["ai_facility_type_confidence"] = [
                        c["confidence"] for c in classifications
                    ]

                transformed_dfs.append(transformed)

                logger.info(f"  Transformed to {len(transformed)} rows")

            except Exception as e:
                logger.error(f"Failed to transform {file_name}: {e}")

        if not transformed_dfs:
            logger.warning("No data was successfully transformed")
            return None

        # Combine all transformed data
        combined = pd.concat(transformed_dfs, ignore_index=True)
        logger.info(
            f"Combined {len(transformed_dfs)} sources into {len(combined)} rows"
        )

        # Detect duplicates
        combined = self.duplicate_detector.detect_duplicates(combined)

        # Score data quality
        combined = self.data_quality_scorer.score_dataframe(combined)

        # Add batch metadata
        combined["batch_id"] = self.batch_id
        combined["ingestion_timestamp"] = datetime.now()

        logger.info("Transformation complete")

        return combined

    def load(self, transformed_data: Optional[pd.DataFrame]) -> Dict[str, Any]:
        """
        Load transformed data into the database.

        Args:
            transformed_data: Transformed DataFrame to load

        Returns:
            Dictionary with load statistics
        """
        logger.info("Step 3: Loading data to database")

        if transformed_data is None or transformed_data.empty:
            logger.warning("No data to load")
            return {"inserted": 0, "updated": 0, "errors": 0}

        # Initialize loader
        loader = SQLiteLoader(self.db_url, batch_id=self.batch_id)

        # Upsert data
        stats = loader.upsert(transformed_data)

        # Get database stats
        db_stats = loader.get_stats()

        logger.info(
            f"Loading complete: {stats['inserted']} inserted, {stats['updated']} updated"
        )

        return {**stats, "database_stats": db_stats}

    def export_to_csv(
        self, df: Optional[pd.DataFrame] = None, filename: str = "leads_export.csv"
    ) -> Path:
        """
        Export data to CSV file.

        Args:
            df: DataFrame to export (if None, loads from database)
            filename: Output filename

        Returns:
            Path to exported file
        """
        if df is None:
            # Load from database
            loader = SQLiteLoader(self.db_url)
            # Query all data
            data = loader.query("SELECT * FROM leads WHERE is_duplicate = 0")
            df = pd.DataFrame(data)

        output_path = self.output_dir / filename
        df.to_csv(output_path, index=False)

        logger.info(f"Exported {len(df)} records to {output_path}")

        return output_path


def main():
    """Main entry point for the ETL pipeline."""
    parser = argparse.ArgumentParser(
        description="ETL Pipeline for Facility Lead Enrichment"
    )
    parser.add_argument(
        "--data-dir", type=str, help="Directory containing source data files"
    )
    parser.add_argument("--output-dir", type=str, help="Directory for output files")
    parser.add_argument("--db-url", type=str, help="Database connection URL")
    parser.add_argument(
        "--pattern", type=str, default="*", help="File pattern to match (default: *)"
    )
    parser.add_argument("--no-ai", action="store_true", help="Disable AI/LLM features")
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level",
    )
    parser.add_argument(
        "--export", action="store_true", help="Export results to CSV after loading"
    )

    args = parser.parse_args()

    # Configure logging
    configure_logging(log_level=args.log_level, log_format="simple")

    # Create pipeline
    pipeline = ETLPipeline(
        data_dir=Path(args.data_dir) if args.data_dir else None,
        output_dir=Path(args.output_dir) if args.output_dir else None,
        db_url=args.db_url,
        use_ai=not args.no_ai,
    )

    # Run pipeline
    stats = pipeline.run(file_pattern=args.pattern)

    # Export if requested
    if args.export:
        pipeline.export_to_csv()

    # Print summary
    print("\n" + "=" * 60)
    print("ETL Pipeline Summary")
    print("=" * 60)
    print(f"Batch ID: {stats['batch_id']}")
    print(f"Duration: {stats['duration_seconds']:.2f} seconds")
    print(f"Files processed: {stats['extraction']['files_processed']}")
    print(f"Records extracted: {stats['extraction']['total_records']}")
    print(f"Records transformed: {stats['transformation']['records_transformed']}")
    print(f"Duplicates found: {stats['transformation']['duplicates_found']}")
    print(
        f"Average quality score: {stats['transformation']['avg_quality_score']:.1f}/100"
    )
    print(f"Records inserted: {stats['loading']['inserted']}")
    print(f"Records updated: {stats['loading']['updated']}")
    print("=" * 60)

    return stats


if __name__ == "__main__":
    main()
