"""Abstract base class for data loaders."""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
import pandas as pd


class BaseLoader(ABC):
    """Abstract base class for data loaders."""
    
    def __init__(self, connection_string: str, **kwargs):
        """
        Initialize the loader.
        
        Args:
            connection_string: Database connection string
            **kwargs: Additional loader-specific options
        """
        self.connection_string = connection_string
        self.options = kwargs
    
    @abstractmethod
    def load(self, df: pd.DataFrame, table_name: str = "leads") -> Dict[str, Any]:
        """
        Load data into the target database.
        
        Args:
            df: DataFrame to load
            table_name: Target table name
            
        Returns:
            Dictionary with load statistics
        """
        pass
    
    @abstractmethod
    def create_table(self, table_name: str = "leads") -> None:
        """
        Create the target table if it doesn't exist.
        
        Args:
            table_name: Table name to create
        """
        pass
    
    @abstractmethod
    def upsert(self, df: pd.DataFrame, table_name: str = "leads") -> Dict[str, Any]:
        """
        Upsert data (insert or update) into the target table.
        
        Args:
            df: DataFrame to upsert
            table_name: Target table name
            
        Returns:
            Dictionary with upsert statistics
        """
        pass
    
    @abstractmethod
    def get_stats(self, table_name: str = "leads") -> Dict[str, Any]:
        """
        Get statistics about the loaded data.
        
        Args:
            table_name: Table name
            
        Returns:
            Dictionary with table statistics
        """
        pass
