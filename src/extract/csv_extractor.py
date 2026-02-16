"""CSV and Excel file extractors with encoding detection."""

from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

import pandas as pd

from src.utils.logging_config import get_logger

from .base_extractor import BaseExtractor

logger = get_logger(__name__)


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
        **kwargs,
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
                on_bad_lines="warn",
                **self.options,
            )

            logger.info(f"Extracted {len(df)} rows from {self.file_path.name}")
            return df

        except UnicodeDecodeError:
            # Try with fallback encodings
            for enc in ["latin-1", "cp1252", "iso-8859-1"]:
                try:
                    df = pd.read_csv(
                        self.file_path,
                        encoding=enc,
                        delimiter=self.delimiter,
                        quotechar=self.quotechar,
                        skiprows=self.skip_rows,
                        low_memory=False,
                        **self.options,
                    )
                    logger.info(
                        f"Extracted {len(df)} rows using fallback encoding {enc}"
                    )
                    return df
                except UnicodeDecodeError:
                    continue

            raise ValueError(
                f"Could not decode file with any encoding: {self.file_path}"
            )

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
            **self.options,
        )

        for chunk in chunk_iter:
            yield chunk

    def _detect_delimiter(self) -> str:
        """Detect the CSV delimiter by analyzing the file."""
        with open(
            self.file_path, "r", encoding=self.encoding or "utf-8", errors="ignore"
        ) as f:
            # Read first few lines
            sample = "".join(f.readline() for _ in range(5))

        # Count occurrences of common delimiters
        delimiters = [",", "\t", ";", "|"]
        counts = {d: sample.count(d) for d in delimiters}

        # Return the most common delimiter
        best = max(counts, key=counts.get)
        return best if counts[best] > 0 else ","

    def get_metadata(self) -> Dict[str, Any]:
        """Get extended metadata including CSV-specific info."""
        meta = super().get_metadata()

        # Add CSV-specific metadata
        try:
            df = self.extract()
            meta.update(
                {
                    "encoding": self.encoding,
                    "delimiter": self.delimiter,
                    "row_count": len(df),
                    "column_count": len(df.columns),
                    "columns": list(df.columns),
                }
            )
        except Exception as e:
            meta["error"] = str(e)

        return meta
