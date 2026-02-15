# Facility Lead ETL Pipeline

A production-grade ETL system that ingests heterogeneous external data sources containing facility/childcare business records, normalizes them into a  schema, and loads them into a SQL-queryable database — incorporating LLM/AI capabilities to improve data quality, classification, and enrichment.

## Quick Start

### Prerequisites

- Python 3.10+
- pip or conda for package management
- (Optional) OpenAI API key for AI features

### Installation

```bash
# Clone or extract the project
cd etl_pipeline

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Running the Pipeline

```bash
# Basic usage - process all files in data/raw/
python -m src.main

# With options
python -m src.main --data-dir ./data/raw --pattern "*.csv" --export

# Disable AI features (rule-based only)
python -m src.main --no-ai

# Custom database location
python -m src.main --db-url sqlite:///custom_path/leads.db
```

### Environment Configuration

Create a `.env` file for configuration:

```env
# LLM Provider (optional, for AI features)
OPENAI_API_KEY=your_key_here
LLM_PROVIDER=openai
LLM_MODEL_CLASSIFICATION=gpt-4o-mini
LLM_MODEL_RESOLUTION=gpt-4o

# Database
DATABASE_URL=sqlite:///./data/processed/leads.db

# Processing
BATCH_SIZE=100
MAX_WORKERS=4

# Logging
LOG_LEVEL=INFO
```

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                      ETL Pipeline Architecture                   │
└─────────────────────────────────────────────────────────────────┘

┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Extract   │────▶│  Transform  │────▶│    Load     │
└─────────────┘     └─────────────┘     └─────────────┘
      │                    │                   │
      ▼                    ▼                   ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│ CSV Extract │     │Schema Mapper│     │SQLite Loader│
│Excel Extract│     │Normalizers  │     │PostgreSQL   │
│Encoding Det │     │Age Parser   │     │  (optional) │
└─────────────┘     │Deduplication│     └─────────────┘
                    │Data Quality │
                    └─────────────┘
                           │
                    ┌─────────────┐
                    │  AI Layer   │
                    │─────────────│
                    │LLM Client   │
                    │Classifier   │
                    │Schema Infer │
                    │Entity Resolv│
                    └─────────────┘
```

### Data Flow

1. **Extract**: Reads CSV/Excel files with automatic encoding detection
2. **Transform**: Maps columns, normalizes values, detects duplicates, scores quality
3. **Load**: Upserts to SQLite with metadata tracking

### Component Descriptions

| Component | Purpose |
|-----------|---------|
| `CSVExtractor` | Reads CSV files with encoding detection |
| `ExcelExtractor` | Reads Excel files with multi-sheet support |
| `SchemaMapper` | Maps source columns to target schema |
| `PhoneNormalizer` | Normalizes phone numbers to (XXX) XXX-XXXX |
| `StateNormalizer` | Normalizes states to 2-letter codes |
| `AddressNormalizer` | Parses combined addresses |
| `AgeParser` | Extracts age ranges from text |
| `DuplicateDetector` | Exact + fuzzy duplicate detection |
| `DataQualityScorer` | Scores records 0-100 |
| `LLMClient` | Wrapper for OpenAI/Anthropic APIs |
| `FacilityClassifier` | AI-powered facility type classification |
| `SQLiteLoader` | Database loading with upsert |

## AI/ML Integration

### What Problems It Solves

1. **Schema Mapping**: Automatically maps unknown source columns to target schema
2. **Facility Classification**: Standardizes facility type descriptions
3. **Entity Resolution**: Resolves ambiguous duplicate candidates

### How Each Component Works

#### LLM Client
- Caches responses by input hash
- Implements retry with exponential backoff
- Tracks token usage and enforces budgets
- Falls back to rule-based when unavailable

#### Facility Classifier
```python
# Example usage
classifier = FacilityClassifier(llm_client)
results = classifier.classify([
    "Licensed Child Care Center",
    "Family Home Daycare"
])
# Returns: [{"category": "Child Care Center", "confidence": 0.95}, ...]
```

#### Schema Inferrer
```python
# Example usage
inferrer = SchemaInferrer(llm_client)
mapping = inferrer.infer_mapping(
    source_columns=["Name", "Type", "Phone"],
    sample_data=[{"Name": "ABC Daycare", ...}]
)
# Returns: {"mappings": {"company": "Name", ...}, "confidence": 0.85}
```

### Design Decisions

| Decision | Rationale |
|----------|-----------|
| AI as Enhancement | Pipeline works without AI (rule-based fallback) |
| Response Caching | Avoid redundant LLM calls for same inputs |
| Batch Processing | Group multiple items per LLM call (cost efficiency) |
| Temperature=0 | Deterministic outputs for classification |
| Confidence Scores | Track certainty for human review |

### Cost Considerations

- Use `gpt-4o-mini` for classification ($0.15/1M input tokens)
- Use `gpt-4o` only for complex entity resolution
- Cache aggressively - same inputs never call LLM twice
- Batch 20-50 items per call
- Set `LLM_MAX_CALLS_PER_RUN` to control costs

### Running Without AI

```bash
python -m src.main --no-ai
```

When AI is disabled:
- Schema mapping uses fuzzy matching
- Facility types use keyword-based rules
- Duplicates use exact + fuzzy matching only

## Testing

### Run Tests

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=src --cov-report=html

# Run specific test file
pytest tests/test_normalizers.py -v

# Run specific test
pytest tests/test_normalizers.py::TestPhoneNormalizer -v
```

### Test Coverage

| Module | Coverage |
|--------|----------|
| Normalizers | 95% |
| Schema Mapper | 85% |
| Data Quality | 90% |
| Deduplication | 80% |
| SQLite Loader | 90% |

### Key Test Cases

- **Phone Normalization**: Various formats, country codes, invalid inputs
- **State Normalization**: Abbreviations, full names, variations
- **Address Parsing**: Combined fields, suite numbers
- **Duplicate Detection**: Exact matches, fuzzy matches, edge cases
- **Data Quality**: Complete records, partial records, invalid data

## Tradeoffs & Future Improvements

### Known Limitations

1. **Address Parsing**: Uses regex fallback without `usaddress` library
2. **AI Dependency**: Requires API key for full functionality
3. **Single Machine**: Not distributed (suitable for 100K-1M records)
4. **No Real-time**: Batch processing only

### What I'd Do With More Time

1. **Add PostgreSQL Loader**: For production scale
2. **Implement Incremental Loading**: Based on timestamps
3. **Add Data Lineage**: Track transformations per field
4. **Build Monitoring Dashboard**: Track pipeline health
5. **Add Data Validation**: Great Expectations integration
6. **Implement SCD Type 2**: Track facility changes over time
7. **Add Unit Tests**: For AI components with mocking
8. **Build CLI Tool**: Interactive schema mapping review

### Scaling Considerations

| Scale | Recommendation |
|-------|----------------|
| < 100K records | Current SQLite implementation |
| 100K - 1M | PostgreSQL + connection pooling |
| 1M - 10M | Partition by state/source |
| 10M+ | Consider cloud data warehouse |

## Long-Term Strategy

See [docs/long_term_strategy.md](docs/long_term_strategy.md) for detailed architecture planning including:

- Event-driven ingestion at scale (100+ sources)
- Orchestration with Airflow/Dagster
- Data modeling (medallion architecture)
- AI/ML at scale (batch inference, monitoring)
- Infrastructure (cloud-native, CI/CD, IaC)

## Project Structure

```
etl_pipeline/
├── README.md
├── requirements.txt
├── config/
│   ├── settings.py          # Configuration management
│   └── schema_mapping.yaml  # Source schema mappings
├── src/
│   ├── main.py              # Entry point / orchestrator
│   ├── extract/             # Extraction modules
│   ├── transform/           # Transformation modules
│   │   └── ai/              # AI/ML integration
│   ├── load/                # Loading modules
│   └── utils/               # Utilities
├── tests/                   # Test suite
├── data/                    # Data directories
│   ├── raw/                 # Source files
│   └── processed/           # Output files
└── docs/                    # Documentation
```

## License

MIT License - See LICENSE file for details.
