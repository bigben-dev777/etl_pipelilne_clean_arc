"""Source registry for managing different data source configurations."""

import yaml
import re
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field


@dataclass
class SourceConfig:
    """Configuration for a data source."""
    name: str
    pattern: str
    column_map: Dict[str, str] = field(default_factory=dict)
    transformations: Dict[str, List[Dict[str, str]]] = field(default_factory=dict)
    file_type: str = "csv"  # csv, excel, etc.
    encoding: Optional[str] = None
    delimiter: Optional[str] = None
    skip_rows: int = 0
    
    def matches(self, file_name: str) -> bool:
        """Check if a file name matches this source pattern."""
        pattern = self.pattern.replace("*", ".*")
        return bool(re.match(pattern, file_name, re.IGNORECASE))


class SourceRegistry:
    """Registry for managing source configurations."""
    
    def __init__(self, config_path: Optional[Path] = None):
        """
        Initialize the source registry.
        
        Args:
            config_path: Path to the YAML configuration file
        """
        self.config_path = config_path or Path(__file__).parent.parent.parent / "config" / "schema_mapping.yaml"
        self.sources: Dict[str, SourceConfig] = {}
        self.default_config: Optional[SourceConfig] = None
        self._load_config()
    
    def _load_config(self) -> None:
        """Load source configurations from YAML file."""
        if not self.config_path.exists():
            return
        
        with open(self.config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        if not config or 'sources' not in config:
            return
        
        for name, source_def in config['sources'].items():
            if name == 'default':
                self.default_config = SourceConfig(
                    name='default',
                    pattern='*',
                    column_map=source_def.get('patterns', {}),
                    transformations={}
                )
            else:
                self.sources[name] = SourceConfig(
                    name=name,
                    pattern=source_def.get('pattern', '*'),
                    column_map=source_def.get('column_map', {}),
                    transformations=source_def.get('transformations', {}),
                    file_type=source_def.get('file_type', 'csv'),
                    encoding=source_def.get('encoding'),
                    delimiter=source_def.get('delimiter'),
                    skip_rows=source_def.get('skip_rows', 0)
                )
    
    def get_source_for_file(self, file_path: Path) -> Optional[SourceConfig]:
        """
        Find the best matching source configuration for a file.
        
        Args:
            file_path: Path to the data file
            
        Returns:
            Matching SourceConfig or None
        """
        file_name = file_path.name
        
        # Try exact matches first
        for source in self.sources.values():
            if source.matches(file_name):
                return source
        
        # Return default if no match
        return self.default_config
    
    def get_column_mapping(self, source_name: str) -> Dict[str, str]:
        """Get column mapping for a specific source."""
        if source_name in self.sources:
            return self.sources[source_name].column_map
        return {}
    
    def get_transformations(self, source_name: str) -> Dict[str, List[Dict[str, str]]]:
        """Get value transformations for a specific source."""
        if source_name in self.sources:
            return self.sources[source_name].transformations
        return {}
    
    def register_source(self, config: SourceConfig) -> None:
        """Register a new source configuration."""
        self.sources[config.name] = config
    
    def list_sources(self) -> List[str]:
        """List all registered source names."""
        return list(self.sources.keys())


# Global registry instance
_registry: Optional[SourceRegistry] = None


def get_source_registry() -> SourceRegistry:
    """Get the global source registry instance."""
    global _registry
    if _registry is None:
        _registry = SourceRegistry()
    return _registry


def get_source_config(file_path: Path) -> Optional[SourceConfig]:
    """Get source configuration for a file."""
    return get_source_registry().get_source_for_file(file_path)
