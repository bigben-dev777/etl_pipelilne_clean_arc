"""Abstract base class for data extractors."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Iterator, Dict, Any, Optional
import pandas as pd


class BaseExtractor(ABC):
    """Abstract base class for data extractors."""
    
    def __init__(self, file_path: Path, **kwargs):
        """
        Initialize the extractor.
        
        Args:
            file_path: Path to the source file
            **kwargs: Additional extractor-specific options
        """
        self.file_path = Path(file_path)
        self.options = kwargs
        self._validate_file()
    
    def _validate_file(self) -> None:
        """Validate that the file exists and is readable."""
        if not self.file_path.exists():
            raise FileNotFoundError(f"File not found: {self.file_path}")
        
        if not self.file_path.is_file():
            raise ValueError(f"Path is not a file: {self.file_path}")
    
    @abstractmethod
    def extract(self) -> pd.DataFrame:
        """
        Extract data from the source file.
        
        Returns:
            DataFrame containing the extracted data
        """
        pass
    
    @abstractmethod
    def extract_streaming(self, chunk_size: int = 1000) -> Iterator[pd.DataFrame]:
        """
        Extract data in chunks for memory efficiency.
        
        Args:
            chunk_size: Number of rows per chunk
            
        Yields:
            DataFrame chunks
        """
        pass
    
    def get_metadata(self) -> Dict[str, Any]:
        """
        Get metadata about the source file.
        
        Returns:
            Dictionary with file metadata
        """
        import os
        import mimetypes
        
        stat = os.stat(self.file_path)
        
        return {
            "file_path": str(self.file_path),
            "file_name": self.file_path.name,
            "file_size_bytes": stat.st_size,
            "file_size_mb": round(stat.st_size / (1024 * 1024), 2),
            "mime_type": mimetypes.guess_type(self.file_path)[0] or "unknown",
            "last_modified": stat.st_mtime,
        }
    
    def detect_encoding(self) -> str:
        """
        Detect file encoding using chardet.
        
        Returns:
            Detected encoding name
        """
        import chardet
        
        # Read a sample of the file
        with open(self.file_path, 'rb') as f:
            raw_data = f.read(100000)  # First 100KB
        
        result = chardet.detect(raw_data)
        encoding = result.get('encoding', 'utf-8')
        confidence = result.get('confidence', 0)
        
        # Fall back to utf-8 if confidence is low
        if confidence < 0.5 or encoding is None:
            return 'utf-8'
        
        return encoding
