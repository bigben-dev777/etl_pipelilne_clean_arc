"""CSV and Excel file extractors with encoding detection."""

import pandas as pd
from pathlib import Path
from typing import Iterator, Dict, Any, Optional, List
import logging

from .base_extractor import BaseExtractor


logger = logging.getLogger(__name__)


class CSVExtractor(BaseExtractor):
    """Extractor for CSV files with automatic encoding detection."""
    
    def __init__(
        self,
        file_path: Path,
        encoding: Optional[str] = None,
        delimiter: Optional[str] = None,
        quotechar: str = '"',
        escapechar: Optional[str] = None,
        skip_rows: int = 0,
        **kwargs
    ):
        """
        Initialize CSV extractor.
        
        Args:
            file_path: Path to CSV file
            encoding: File encoding (auto-detected if None)
            delimiter: Field delimiter (auto-detected if None)
            quotechar: Quote character
            escapechar: Escape character
            skip_rows: Number of rows to skip at beginning
            **kwargs: Additional pandas read_csv options
        """
        super().__init__(file_path, **kwargs)
        self.encoding = encoding
        self.delimiter = delimiter
        self.quotechar = quotechar
        self.escapechar = escapechar
        self.skip_rows = skip_rows
    
    def extract(self) -> pd.DataFrame:
        """
        Extract data from CSV file.
        
        Returns:
            DataFrame with extracted data
        """
        # Detect encoding if not provided
        if self.encoding is None:
            self.encoding = self.detect_encoding()
            logger.info(f"Detected encoding: {self.encoding}")
        
        # Detect delimiter if not provided
        if self.delimiter is None:
            self.delimiter = self._detect_delimiter()
        
        try:
            df = pd.read_csv(
                self.file_path,
                encoding=self.encoding,
                delimiter=self.delimiter,
                quotechar=self.quotechar,
                escapechar=self.escapechar,
                skiprows=self.skip_rows,
                low_memory=False,
                on_bad_lines='warn',
                **self.options
            )
            
            logger.info(f"Extracted {len(df)} rows from {self.file_path.name}")
            return df
            
        except UnicodeDecodeError:
            # Try with fallback encodings
            for enc in ['latin-1', 'cp1252', 'iso-8859-1']:
                try:
                    df = pd.read_csv(
                        self.file_path,
                        encoding=enc,
                        delimiter=self.delimiter,
                        quotechar=self.quotechar,
                        skiprows=self.skip_rows,
                        low_memory=False,
                        **self.options
                    )
                    logger.info(f"Extracted {len(df)} rows using fallback encoding {enc}")
                    return df
                except UnicodeDecodeError:
                    continue
            
            raise ValueError(f"Could not decode file with any encoding: {self.file_path}")
    
    def extract_streaming(self, chunk_size: int = 1000) -> Iterator[pd.DataFrame]:
        """
        Extract CSV data in chunks.
        
        Args:
            chunk_size: Number of rows per chunk
            
        Yields:
            DataFrame chunks
        """
        if self.encoding is None:
            self.encoding = self.detect_encoding()
        
        if self.delimiter is None:
            self.delimiter = self._detect_delimiter()
        
        chunk_iter = pd.read_csv(
            self.file_path,
            encoding=self.encoding,
            delimiter=self.delimiter,
            chunksize=chunk_size,
            low_memory=False,
            **self.options
        )
        
        for chunk in chunk_iter:
            yield chunk
    
    def _detect_delimiter(self) -> str:
        """Detect the CSV delimiter by analyzing the file."""
        with open(self.file_path, 'r', encoding=self.encoding or 'utf-8', errors='ignore') as f:
            # Read first few lines
            sample = ''.join(f.readline() for _ in range(5))
        
        # Count occurrences of common delimiters
        delimiters = [',', '\t', ';', '|']
        counts = {d: sample.count(d) for d in delimiters}
        
        # Return the most common delimiter
        best = max(counts, key=counts.get)
        return best if counts[best] > 0 else ','
    
    def get_metadata(self) -> Dict[str, Any]:
        """Get extended metadata including CSV-specific info."""
        meta = super().get_metadata()
        
        # Add CSV-specific metadata
        try:
            df = self.extract()
            meta.update({
                "encoding": self.encoding,
                "delimiter": self.delimiter,
                "row_count": len(df),
                "column_count": len(df.columns),
                "columns": list(df.columns),
            })
        except Exception as e:
            meta["error"] = str(e)
        
        return meta


class ExcelExtractor(BaseExtractor):
    """Extractor for Excel files (.xlsx, .xls) with multi-sheet support."""
    
    def __init__(
        self,
        file_path: Path,
        sheet_name: Optional[str] = None,
        header_row: int = 0,
        **kwargs
    ):
        """
        Initialize Excel extractor.
        
        Args:
            file_path: Path to Excel file
            sheet_name: Specific sheet to extract (None for all sheets)
            header_row: Row containing column headers
            **kwargs: Additional pandas read_excel options
        """
        super().__init__(file_path, **kwargs)
        self.sheet_name = sheet_name
        self.header_row = header_row
    
    def extract(self) -> pd.DataFrame:
        """
        Extract data from Excel file.
        
        Returns:
            DataFrame with extracted data (or concatenated if multiple sheets)
        """
        xl_file = pd.ExcelFile(self.file_path)
        
        sheets_to_read = self._get_sheets_to_read(xl_file)
        
        dataframes = []
        for sheet in sheets_to_read:
            try:
                df = pd.read_excel(
                    self.file_path,
                    sheet_name=sheet,
                    header=self.header_row,
                    **self.options
                )
                
                # Add source sheet metadata
                df['_source_sheet'] = sheet
                dataframes.append(df)
                
                logger.info(f"Extracted {len(df)} rows from sheet '{sheet}'")
                
            except Exception as e:
                logger.warning(f"Failed to extract sheet '{sheet}': {e}")
        
        if not dataframes:
            raise ValueError(f"No data extracted from {self.file_path}")
        
        # Concatenate all sheets
        combined = pd.concat(dataframes, ignore_index=True)
        logger.info(f"Total extracted: {len(combined)} rows from {len(dataframes)} sheets")
        
        return combined
    
    def extract_streaming(self, chunk_size: int = 1000) -> Iterator[pd.DataFrame]:
        """
        Extract Excel data sheet by sheet.
        
        Args:
            chunk_size: Not used for Excel, yields entire sheets
            
        Yields:
            DataFrames (one per sheet)
        """
        xl_file = pd.ExcelFile(self.file_path)
        sheets_to_read = self._get_sheets_to_read(xl_file)
        
        for sheet in sheets_to_read:
            df = pd.read_excel(
                self.file_path,
                sheet_name=sheet,
                header=self.header_row,
                **self.options
            )
            df['_source_sheet'] = sheet
            yield df
    
    def extract_sheet_names(self) -> List[str]:
        """Get list of sheet names in the Excel file."""
        xl_file = pd.ExcelFile(self.file_path)
        return xl_file.sheet_names
    
    def _get_sheets_to_read(self, xl_file: pd.ExcelFile) -> List[str]:
        """Determine which sheets to read based on configuration."""
        all_sheets = xl_file.sheet_names
        
        if self.sheet_name is None:
            # Read all sheets
            return all_sheets
        elif isinstance(self.sheet_name, str):
            # Read specific sheet
            if self.sheet_name in all_sheets:
                return [self.sheet_name]
            else:
                raise ValueError(f"Sheet '{self.sheet_name}' not found. Available: {all_sheets}")
        elif isinstance(self.sheet_name, list):
            # Read multiple sheets
            return [s for s in self.sheet_name if s in all_sheets]
        else:
            return all_sheets
    
    def get_metadata(self) -> Dict[str, Any]:
        """Get extended metadata including Excel-specific info."""
        meta = super().get_metadata()
        
        try:
            xl_file = pd.ExcelFile(self.file_path)
            meta["sheet_names"] = xl_file.sheet_names
            meta["sheet_count"] = len(xl_file.sheet_names)
            
            # Get row counts per sheet
            sheet_info = {}
            for sheet in xl_file.sheet_names:
                df = pd.read_excel(self.file_path, sheet_name=sheet, nrows=0)
                sheet_info[sheet] = {
                    "columns": list(df.columns),
                    "column_count": len(df.columns)
                }
            meta["sheets"] = sheet_info
            
        except Exception as e:
            meta["error"] = str(e)
        
        return meta
