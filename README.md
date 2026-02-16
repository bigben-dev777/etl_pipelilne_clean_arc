# Facility Lead ETL Pipeline

An intelligent, AI-powered ETL (Extract, Transform, Load) pipeline designed for childcare facility lead enrichment and data standardization. This pipeline automates the ingestion, transformation, and loading of facility lead data from various sources into a unified, queryable database format.

## Overview

This ETL pipeline specializes in processing childcare facility data (daycares, preschools, family childcare homes, etc.) from heterogeneous sources. It uses AI/LLM capabilities for intelligent schema mapping, facility classification, and entity resolution, while maintaining robust fallback mechanisms for rule-based processing.

## Key Features

- **Multi-Source Data Ingestion**: Supports CSV, Excel (XLSX/XLS), and other formats
- **AI-Powered Schema Mapping**: LLM-driven automatic column mapping and transformation rule generation
- **Intelligent Data Normalization**: Standardizes phone numbers (E164), addresses, states (USPS), ZIP codes, and facility types
- **Duplicate Detection**: Multi-tier deduplication with exact matching, fuzzy matching, and AI-assisted entity resolution
- **Data Quality Scoring**: Comprehensive quality assessment with weighted scoring (0-100)
- **Facility Classification**: AI-powered categorization of facility types
- **Caching System**: Persistent YAML-based caching for schema mappings to reduce LLM costs
- **SQLite Backend**: Efficient local database storage with upsert capabilities

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   Extract       │────▶│   Transform      │────▶│   Load          │
│                 │     │                  │     │                 │
│ • CSVExtractor  │     │ • SchemaMapper   │     │ • SQLiteLoader  │
│ • SourceRegistry│     │ • Normalizers    │     │ • Upsert logic  │
│ • Excel support │     │ • Deduplication  │     │ • Indexing      │
│                 │     │ • Data Quality   │     │                 │
└─────────────────┘     └──────────────────┘     └─────────────────┘
         │                       │                        │
         ▼                       ▼                        ▼
   data/raw/              AI/LLM Components          data/processed/
   • CSV files           • SchemaGenerator          • leads.db
   • Excel files         • FacilityClassifier       • Export CSVs
   • Multiple sheets     • LLMClient
```

## Project Structure

```
etl_pipeline/
├── src/
│   ├── main.py                    # Main orchestrator and CLI entry point
│   ├── extract/
│   │   ├── base_extractor.py      # Abstract base for extractors
│   │   ├── csv_extractor.py       # CSV/Excel extraction with encoding detection
│   │   └── source_registry.py     # Source configuration management
│   ├── transform/
│   │   ├── ai/
│   │   │   ├── llm_client.py      # LLM provider wrapper (OpenAI, Anthropic, Gemini, Local)
│   │   │   └── facility_classifier.py  # AI facility type classification
│   │   ├── schema_mapper.py       # Main mapping orchestrator
│   │   ├── schema_generator.py    # LLM-based schema generation
│   │   ├── schema_cache.py        # YAML-based caching system
│   │   ├── transformation_engine.py  # Rule application engine
│   │   ├── normalizers.py         # Data normalization utilities
│   │   ├── deduplication.py       # Duplicate detection and resolution
│   │   ├── data_quality.py        # Quality scoring system
│   │   └── prompt.py              # LLM prompt templates
│   ├── load/
│   │   ├── base_loader.py         # Abstract base for loaders
│   │   └── sqlite_loader.py       # SQLite implementation with upsert
│   └── utils/                     # Utility modules
├── config/
│   ├── settings.py                # Application configuration
│   └── schema_mapping.yaml        # Source-specific mappings
├── cache/schemas/                 # Persisted schema mappings (YAML)
├── data/
│   ├── raw/                       # Input data files
│   └── processed/                 # Output database and exports
└── docs/                          # Documentation
```

## Installation

```bash
# Clone the repository
git clone <repository-url>
cd etl_pipeline

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment variables
cp .env.example .env
# Edit .env with your API keys (OpenAI, Anthropic, or Gemini)
```

### Requirements

- Python 3.12+
- pandas
- rapidfuzz (for fuzzy matching)
- PyYAML
- python-dotenv
- openai (optional, for OpenAI provider)
- anthropic (optional, for Anthropic provider)
- google-genai (optional, for Gemini provider)

## Usage

### Basic Usage

```bash
# Run full ETL pipeline
python -m src.main

# Run with specific file pattern
python -m src.main --pattern="*source1*"

# Disable AI features (rule-based only)
python -m src.main --no-ai

# Export results to CSV after loading
python -m src.main --export

# Custom data directory
python -m src.main --data-dir=/path/to/data --output-dir=/path/to/output
```

### Python API

```python
from src.main import ETLPipeline
from pathlib import Path

# Initialize pipeline
pipeline = ETLPipeline(
    data_dir=Path("./data/raw"),
    output_dir=Path("./data/processed"),
    use_ai=True,
    batch_id="custom_batch_001"
)

# Run pipeline
stats = pipeline.run(file_pattern="*")

# Export to CSV
pipeline.export_to_csv(filename="my_export.csv")
```

## Configuration

### Environment Variables

Create a `.env` file:

```env
# LLM Provider Configuration
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
LLM_MODEL_RESOLUTION=gpt-4o-mini
LLM_MODEL_CLASSIFICATION=gpt-4o-mini

# Or use Anthropic
# LLM_PROVIDER=anthropic
# ANTHROPIC_API_KEY=sk-ant-...

# Or use Gemini
# LLM_PROVIDER=gemini
# GEMINI_API_KEY=...

# Or use local model
# LLM_PROVIDER=local

# Database
DATABASE_URL=sqlite:///./data/processed/leads.db
```

### Source Configuration

Edit `config/schema_mapping.yaml` to define source-specific mappings:

```yaml
sources:
  default:
    patterns:
      company: ["Facility Name", "Center Name", "Provider"]
      phone: ["Phone", "Contact Phone", "Telephone"]
      # ... more mappings
  
  texas_data:
    pattern: "*texas*"
    column_map:
      license_number: "License ID"
      capacity: "Max Children"
    # ... source-specific rules
```

## Data Schema

### Target Schema

The pipeline normalizes all data to the following standard schema:

| Field | Type | Description |
|-------|------|-------------|
| `company` | VARCHAR(500) | Facility legal name |
| `facility_type` | VARCHAR(255) | Normalized facility category |
| `address1` | VARCHAR(500) | Primary street address |
| `address2` | VARCHAR(255) | Suite/Unit number |
| `city` | VARCHAR(255) | City name |
| `state` | VARCHAR(2) | USPS state abbreviation |
| `zip` | VARCHAR(20) | ZIP/ZIP+4 code |
| `county` | VARCHAR(255) | County name |
| `phone` | VARCHAR(50) | Primary phone (E164 format) |
| `phone2` | VARCHAR(50) | Secondary phone |
| `email` | VARCHAR(255) | Contact email |
| `website_address` | VARCHAR(500) | Website URL |
| `first_name` | VARCHAR(255) | Contact first name |
| `last_name` | VARCHAR(255) | Contact last name |
| `capacity` | NUMERIC | Licensed capacity |
| `min_age` | NUMERIC | Minimum age served (months) |
| `max_age` | NUMERIC | Maximum age served (months) |
| `ages_served` | VARCHAR(500) | Age range description |
| `license_status` | VARCHAR(100) | Normalized license status |
| `license_number` | VARCHAR(255) | State license ID |
| `license_type` | VARCHAR(255) | Type of license |

### Metadata Fields

| Field | Description |
|-------|-------------|
| `record_id` | Unique deterministic ID |
| `source_file` | Origin file name |
| `is_duplicate` | Duplicate flag |
| `duplicate_cluster_id` | Cluster identifier |
| `data_quality_score` | Quality score (0-100) |
| `data_quality_flags` | JSON array of quality issues |
| `batch_id` | ETL batch identifier |
| `ingestion_timestamp` | Processing timestamp |

## AI/LLM Features

### Schema Generation

The pipeline uses LLMs to automatically generate column mappings and transformation rules:

1. Analyzes source column names and sample data
2. Generates mappings to target schema
3. Creates transformation rules (regex, mappings, conditions)
4. Caches results in YAML format for reuse

### Facility Classification

Automatically categorizes facilities into standardized types:
- Child Care Center
- Family Child Care
- Group Home
- School Age Program
- Head Start
- Preschool
- Residential
- Other

### Entity Resolution

AI-assisted duplicate detection for ambiguous cases:
- Compares similar names and addresses
- Determines if records represent same facility
- Handles renamed/relocated facilities

## Data Quality Scoring

Records are scored 0-100 based on:

| Field | Weight | Criteria |
|-------|--------|----------|
| Company | 15 | Presence, length, generic value detection |
| Phone | 15 | Valid format (E164) |
| Email | 10 | Valid format |
| Address | 15 | Completeness (street, city, state, ZIP) |
| Capacity | 10 | Valid numeric value |
| License | 10 | Number and status present |
| Contact Name | 10 | First and last name |
| Age Info | 10 | Min/max ages or ages_served |
| Not Duplicate | 5 | Not marked as duplicate |

## Normalization Rules

### Phone Numbers
- Input: Various formats
- Output: E164 (`+15551234567`)

### States
- Input: Full names or abbreviations
- Output: USPS 2-letter codes

### ZIP Codes
- Input: 5-digit, ZIP+4, or partial
- Output: Standardized 5-digit or ZIP+4

### Addresses
- Standardizes street types (St→Street, Ave→Avenue, etc.)
- Title Case formatting

### License Status
Maps to canonical values: `ACTIVE`, `CONDITIONAL`, `PROBATION`, `TEMPORARY`, `PENDING`, `SUSPENDED`, `REVOKED`, `EXPIRED`, `CLOSED`, `VOLUNTARILY_CLOSED`

## Caching

Schema mappings are cached in `cache/schemas/` as YAML files:

- **Fingerprint-based**: Named by schema hash (`schema_{hash}.yaml`)
- **Human-readable**: Easy to inspect and manually edit
- **Metadata-rich**: Includes confidence scores, timestamps, statistics

To clear cache:
```python
from src.transform.schema_cache import SchemaCacheManager
cache = SchemaCacheManager()
cache.clear_all()
```

## Development

### Adding New Normalizers

1. Create class in `src/transform/normalizers.py` extending `BaseNormalizer`
2. Implement `normalize(self, value) -> Tuple[Any, Dict]`
3. Register in `TransformationEngine.normalizers` dict

### Adding New LLM Providers

1. Create class in `src/transform/ai/llm_client.py` extending `LLMProvider`
2. Implement `complete()` and `count_tokens()` methods
3. Add to `LLMClient._create_provider()` factory