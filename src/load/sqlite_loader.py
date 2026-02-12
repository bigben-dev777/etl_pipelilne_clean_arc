"""SQLite loader implementation."""

import sqlite3
import json
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
import pandas as pd
import logging

from .base_loader import BaseLoader
from ..utils.hashing import compute_record_hash

logger = logging.getLogger(__name__)


class SQLiteLoader(BaseLoader):
    """SQLite implementation of the data loader."""
    
    # Target schema DDL
    CREATE_TABLE_SQL = """
    CREATE TABLE IF NOT EXISTS leads (
        -- Core facility information
        company VARCHAR(500),
        facility_type VARCHAR(255),
        
        -- Location
        address1 VARCHAR(500),
        address2 VARCHAR(255),
        city VARCHAR(255),
        state VARCHAR(50),
        zip VARCHAR(20),
        county VARCHAR(255),
        
        -- Contact
        phone VARCHAR(50),
        phone2 VARCHAR(50),
        email VARCHAR(255),
        website_address VARCHAR(500),
        first_name VARCHAR(255),
        last_name VARCHAR(255),
        
        -- Facility details
        capacity NUMERIC,
        min_age NUMERIC,
        max_age NUMERIC,
        ages_served VARCHAR(500),
        
        -- Licensing
        license_status VARCHAR(100),
        license_number VARCHAR(255),
        license_type VARCHAR(255),
        
        -- ETL Metadata
        source_file VARCHAR(500),
        record_id VARCHAR(255) PRIMARY KEY,
        is_duplicate BOOLEAN DEFAULT FALSE,
        duplicate_cluster_id VARCHAR(255),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        
        -- AI/ML Metadata
        ai_facility_type_confidence NUMERIC,
        ai_duplicate_cluster_id VARCHAR(255),
        data_quality_score NUMERIC,
        data_quality_flags TEXT,
        
        -- ETL Tracking
        raw_record_hash VARCHAR(64),
        normalization_applied TEXT,
        batch_id VARCHAR(255),
        ingestion_timestamp TIMESTAMP
    )
    """
    
    CREATE_INDEXES_SQL = [
        "CREATE INDEX IF NOT EXISTS idx_leads_phone ON leads(phone)",
        "CREATE INDEX IF NOT EXISTS idx_leads_email ON leads(email)",
        "CREATE INDEX IF NOT EXISTS idx_leads_company ON leads(company)",
        "CREATE INDEX IF NOT EXISTS idx_leads_state ON leads(state)",
        "CREATE INDEX IF NOT EXISTS idx_leads_source ON leads(source_file)",
        "CREATE INDEX IF NOT EXISTS idx_leads_duplicate ON leads(is_duplicate)",
        "CREATE INDEX IF NOT EXISTS idx_leads_quality ON leads(data_quality_score)",
        "CREATE INDEX IF NOT EXISTS idx_leads_cluster ON leads(duplicate_cluster_id)",
    ]
    
    def __init__(self, connection_string: str = "sqlite:///./data/processed/leads.db", **kwargs):
        """
        Initialize SQLite loader.
        
        Args:
            connection_string: SQLite connection string (sqlite:///path/to/db)
            **kwargs: Additional options
        """
        super().__init__(connection_string, **kwargs)
        self.db_path = self._parse_connection_string(connection_string)
        self.batch_id = kwargs.get('batch_id', f"batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        
        # Ensure directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Initialize database
        self._init_database()
    
    def _parse_connection_string(self, connection_string: str) -> Path:
        """Parse SQLite connection string to get database path."""
        if connection_string.startswith("sqlite:///"):
            path = connection_string[10:]
            return Path(path)
        return Path(connection_string)
    
    def _init_database(self) -> None:
        """Initialize database with schema."""
        with sqlite3.connect(self.db_path) as conn:
            # Create table
            conn.execute(self.CREATE_TABLE_SQL)
            
            # Create indexes
            for sql in self.CREATE_INDEXES_SQL:
                conn.execute(sql)
            
            conn.commit()
        
        logger.info(f"Initialized database at {self.db_path}")
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get a database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def create_table(self, table_name: str = "leads") -> None:
        """Create the target table if it doesn't exist."""
        with self._get_connection() as conn:
            conn.execute(self.CREATE_TABLE_SQL)
            conn.commit()
    
    def load(self, df: pd.DataFrame, table_name: str = "leads") -> Dict[str, Any]:
        """
        Load data into SQLite (insert only, no updates).
        
        Args:
            df: DataFrame to load
            table_name: Target table name
            
        Returns:
            Dictionary with load statistics
        """
        if df.empty:
            return {"inserted": 0, "updated": 0, "errors": 0}
        
        # Prepare data
        df = self._prepare_dataframe(df)
        
        # Insert data
        with self._get_connection() as conn:
            df.to_sql(table_name, conn, if_exists='append', index=False)
        
        stats = {
            "inserted": len(df),
            "updated": 0,
            "errors": 0,
            "table": table_name
        }
        
        logger.info(f"Loaded {stats['inserted']} records into {table_name}")
        
        return stats
    
    def upsert(self, df: pd.DataFrame, table_name: str = "leads") -> Dict[str, Any]:
        """
        Upsert data (insert or update) based on record_id.
        
        Args:
            df: DataFrame to upsert
            table_name: Target table name
            
        Returns:
            Dictionary with upsert statistics
        """
        if df.empty:
            return {"inserted": 0, "updated": 0, "errors": 0}
        
        # Prepare data
        df = self._prepare_dataframe(df)
        
        inserted = 0
        updated = 0
        errors = 0
        
        with self._get_connection() as conn:
            for idx, row in df.iterrows():
                try:
                    record_id = row.get('record_id')
                    
                    if not record_id:
                        logger.warning(f"Skipping row {idx}: no record_id")
                        errors += 1
                        continue
                    
                    # Check if record exists
                    cursor = conn.execute(
                        f"SELECT record_id, raw_record_hash FROM {table_name} WHERE record_id = ?",
                        (record_id,)
                    )
                    existing = cursor.fetchone()
                    
                    if existing:
                        # Update existing record
                        self._update_record(conn, table_name, row)
                        updated += 1
                    else:
                        # Insert new record
                        self._insert_record(conn, table_name, row)
                        inserted += 1
                        
                except Exception as e:
                    logger.error(f"Error processing row {idx}: {e}")
                    errors += 1
            
            conn.commit()
        
        stats = {
            "inserted": inserted,
            "updated": updated,
            "errors": errors,
            "table": table_name
        }
        
        logger.info(f"Upsert complete: {inserted} inserted, {updated} updated, {errors} errors")
        
        return stats
    
    def _prepare_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """Prepare DataFrame for loading."""
        result = df.copy()
        
        # Add metadata columns if missing
        if 'batch_id' not in result.columns:
            result['batch_id'] = self.batch_id
        
        if 'ingestion_timestamp' not in result.columns:
            result['ingestion_timestamp'] = datetime.now()
        
        if 'raw_record_hash' not in result.columns:
            result['raw_record_hash'] = result.apply(
                lambda row: compute_record_hash(row.to_dict()), axis=1
            )
        
        # Convert boolean columns
        if 'is_duplicate' in result.columns:
            result['is_duplicate'] = result['is_duplicate'].astype(bool)
        
        # Handle JSON columns
        if 'data_quality_flags' in result.columns:
            result['data_quality_flags'] = result['data_quality_flags'].apply(
                lambda x: json.dumps(x) if isinstance(x, (list, dict)) else x
            )
        
        if 'normalization_applied' in result.columns:
            result['normalization_applied'] = result['normalization_applied'].apply(
                lambda x: json.dumps(x) if isinstance(x, (list, dict)) else x
            )
        
        # Convert Timestamp columns to ISO format strings
        for col in result.columns:
            if pd.api.types.is_datetime64_any_dtype(result[col]):
                result[col] = result[col].apply(
                    lambda x: x.isoformat() if pd.notna(x) else None
                )
        
        # Limit string lengths to prevent errors
        string_columns = ['company', 'address1', 'address2', 'city', 'email']
        for col in string_columns:
            if col in result.columns:
                result[col] = result[col].astype(str).str[:500]
        
        return result
    
    def _insert_record(self, conn: sqlite3.Connection, table_name: str, row: pd.Series) -> None:
        """Insert a single record."""
        columns = []
        placeholders = []
        values = []
        
        for col in row.index:
            val = row[col]
            
            # Skip NaN values
            if pd.isna(val):
                continue
            
            columns.append(col)
            placeholders.append('?')
            values.append(val)
        
        sql = f"INSERT INTO {table_name} ({', '.join(columns)}) VALUES ({', '.join(placeholders)})"
        conn.execute(sql, values)
    
    def _update_record(self, conn: sqlite3.Connection, table_name: str, row: pd.Series) -> None:
        """Update an existing record."""
        record_id = row.get('record_id')
        
        columns = []
        values = []
        
        for col in row.index:
            if col == 'record_id':
                continue
            if col == 'created_at':
                continue  # Don't update created_at
            
            val = row[col]
            
            if pd.isna(val):
                continue
            
            columns.append(f"{col} = ?")
            values.append(val)
        
        # Always update updated_at
        columns.append("updated_at = CURRENT_TIMESTAMP")
        
        values.append(record_id)
        
        sql = f"UPDATE {table_name} SET {', '.join(columns)} WHERE record_id = ?"
        conn.execute(sql, values)
    
    def get_stats(self, table_name: str = "leads") -> Dict[str, Any]:
        """Get statistics about the loaded data."""
        with self._get_connection() as conn:
            # Total count
            cursor = conn.execute(f"SELECT COUNT(*) FROM {table_name}")
            total = cursor.fetchone()[0]
            
            # Duplicate count
            cursor = conn.execute(f"SELECT COUNT(*) FROM {table_name} WHERE is_duplicate = 1")
            duplicates = cursor.fetchone()[0]
            
            # Source file breakdown
            cursor = conn.execute(f"""
                SELECT source_file, COUNT(*) as count 
                FROM {table_name} 
                GROUP BY source_file
            """)
            sources = {row['source_file']: row['count'] for row in cursor.fetchall()}
            
            # State breakdown
            cursor = conn.execute(f"""
                SELECT state, COUNT(*) as count 
                FROM {table_name} 
                WHERE state IS NOT NULL
                GROUP BY state
            """)
            states = {row['state']: row['count'] for row in cursor.fetchall()}
            
            # Quality score stats
            cursor = conn.execute(f"""
                SELECT 
                    AVG(data_quality_score) as avg_quality,
                    MIN(data_quality_score) as min_quality,
                    MAX(data_quality_score) as max_quality
                FROM {table_name}
            """)
            quality = cursor.fetchone()
            
            return {
                "table": table_name,
                "total_records": total,
                "duplicate_records": duplicates,
                "unique_records": total - duplicates,
                "sources": sources,
                "states": states,
                "quality": {
                    "average": round(quality['avg_quality'], 2) if quality['avg_quality'] else None,
                    "min": quality['min_quality'],
                    "max": quality['max_quality']
                }
            }
    
    def query(self, sql: str, params: Tuple = ()) -> List[Dict[str, Any]]:
        """Execute a query and return results."""
        with self._get_connection() as conn:
            cursor = conn.execute(sql, params)
            return [dict(row) for row in cursor.fetchall()]
    
    def get_table_schema(self, table_name: str = "leads") -> List[Dict[str, Any]]:
        """Get the schema of a table."""
        with self._get_connection() as conn:
            cursor = conn.execute(f"PRAGMA table_info({table_name})")
            return [dict(row) for row in cursor.fetchall()]
