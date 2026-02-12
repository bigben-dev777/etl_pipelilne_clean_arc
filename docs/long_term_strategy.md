# Long-Term Strategy: Facility Lead ETL Pipeline

## Executive Summary

This document outlines the strategic architecture for scaling the Facility Lead ETL Pipeline from its current state (handling a handful of CSV files) to a production-grade system capable of processing 100+ heterogeneous data sources with high reliability, data quality, and cost efficiency.

## 1. Ingestion Architecture at Scale (100+ Sources)

### Current State
- Manual file drops into `data/raw/`
- Local filesystem processing
- Single-machine execution

### Target Architecture: Event-Driven Ingestion

```
┌─────────────────────────────────────────────────────────────────┐
│                    Ingestion Architecture                        │
└─────────────────────────────────────────────────────────────────┘

  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
  │   Source    │    │   Source    │    │   Source    │
  │    (S3)     │    │    (SFTP)   │    │   (API)     │
  └──────┬──────┘    └──────┬──────┘    └──────┬──────┘
         │                  │                  │
         └──────────────────┼──────────────────┘
                            ▼
                   ┌─────────────────┐
                   │  Ingestion API  │
                   │  (API Gateway)  │
                   └────────┬────────┘
                            │
         ┌──────────────────┼──────────────────┐
         │                  │                  │
         ▼                  ▼                  ▼
  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
  │  S3 Events  │    │   SQS       │    │  EventBridge│
  │  (New File) │    │  (Queue)    │    │  (Scheduled)│
  └──────┬──────┘    └──────┬──────┘    └──────┬──────┘
         │                  │                  │
         └──────────────────┼──────────────────┘
                            ▼
                   ┌─────────────────┐
                   │   Lambda/ECS    │
                   │  (Validation)   │
                   └────────┬────────┘
                            │
                            ▼
                   ┌─────────────────┐
                   │  Schema Registry│
                   │  (Track Changes)│
                   └────────┬────────┘
                            │
                            ▼
                   ┌─────────────────┐
                   │   Raw S3 Bucket │
                   │  (Partitioned)  │
                   └─────────────────┘
```

### Key Components

#### 1.1 Self-Service Upload Portal
- Web interface for 3rd-party data providers
- Drag-and-drop file upload with validation
- Real-time feedback on schema compliance
- API key authentication for programmatic uploads

#### 1.2 Schema Registry
- Central repository of all source schemas
- Version tracking for schema evolution
- Automated drift detection
- Alerting on breaking changes

```python
# Schema Registry Example
{
  "source_id": "nevada_childcare",
  "version": "2024-01-15",
  "columns": [...],
  "checksum": "sha256:abc123...",
  "detected_changes": ["column 'phone' type changed from VARCHAR(20) to VARCHAR(50)"]
}
```

#### 1.3 Schema Drift Detection
- Automated comparison of incoming files against registered schemas
- Alert channels: PagerDuty, Slack, Email
- Auto-pause ingestion on critical drift

## 2. Orchestration & Scheduling

### Current State
- Manual execution via CLI
- No scheduling or dependency management

### Target Architecture: Dagster/Airflow

```
┌─────────────────────────────────────────────────────────────────┐
│                  Orchestration Architecture                      │
└─────────────────────────────────────────────────────────────────┘

  ┌─────────────────────────────────────────────────────────────┐
  │                      Dagster Instance                        │
  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
  │  │  Daily ETL  │  │ Weekly ETL  │  │  Monthly Full       │ │
  │  │  (Incremental)│ │ (Enrichment)│  │  Refresh            │ │
  │  └──────┬──────┘  └──────┬──────┘  └──────────┬──────────┘ │
  │         │                │                    │            │
  │         └────────────────┼────────────────────┘            │
  │                          │                                 │
  │                          ▼                                 │
  │  ┌─────────────────────────────────────────────────────┐  │
  │  │              Partitioned Asset Graph                 │  │
  │  │  ┌─────────┐    ┌─────────┐    ┌─────────┐         │  │
  │  │  │  Raw    │───▶│Staging  │───▶│  Clean  │         │  │
  │  │  │  (S3)   │    │ (Parquet)│   │ (Delta) │         │  │
  │  │  └─────────┘    └─────────┘    └────┬────┘         │  │
  │  │                                      │              │  │
  │  │                                      ▼              │  │
  │  │                           ┌─────────────────┐       │  │
  │  │                           │   Enriched      │       │  │
  │  │                           │   (Redshift)    │       │  │
  │  │                           └─────────────────┘       │  │
  │  └─────────────────────────────────────────────────────┘  │
  └─────────────────────────────────────────────────────────────┘
```

### Scheduling Strategy

| Pipeline | Frequency | Trigger | Purpose |
|----------|-----------|---------|---------|
| Incremental | Hourly | S3 Event | Process new files |
| Daily ETL | 2 AM | Scheduled | Full transformation |
| Weekly Enrichment | Sunday 3 AM | Scheduled | AI classification batch |
| Monthly Full Refresh | 1st of month | Scheduled | Reprocess all data |

### Watermark-Based Incremental Processing

```python
# Watermark tracking for incremental loads
class WatermarkManager:
    def get_last_processed(self, source: str) -> datetime:
        """Get timestamp of last successful processing."""
        
    def update_watermark(self, source: str, timestamp: datetime):
        """Update watermark after successful processing."""
```

## 3. Data Modeling

### Medallion Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Medallion Architecture                        │
└─────────────────────────────────────────────────────────────────┘

  ┌─────────────────────────────────────────────────────────────┐
  │                         BRONZE (Raw)                         │
  │  - Original files in S3                                      │
  │  - No transformations                                        │
  │  - Partitioned by source/date                                │
  │  - Retention: 90 days                                        │
  └─────────────────────────────┬───────────────────────────────┘
                                │
                                ▼
  ┌─────────────────────────────────────────────────────────────┐
  │                        SILVER (Clean)                        │
  │  - Schema enforcement                                        │
  │  - Basic normalization (phone, address)                      │
  │  - Deduplication                                             │
  │  - Data quality flags                                        │
  │  - Format: Delta Lake on S3                                  │
  └─────────────────────────────┬───────────────────────────────┘
                                │
                                ▼
  ┌─────────────────────────────────────────────────────────────┐
  │                       GOLD (Enriched)                        │
  │  - AI classifications                                        │
  │  - Entity resolution                                         │
  │  - Aggregations and metrics                                  │
  │  - Business-ready views                                      │
  │  - Format: Redshift/Athena                                   │
  └─────────────────────────────────────────────────────────────┘
```

### SCD Type 2 Implementation

Track facility changes over time for analytics:

```sql
CREATE TABLE leads_scd2 (
    facility_sk BIGINT,           -- Surrogate key
    facility_nk VARCHAR(255),     -- Natural key (license_number)
    company VARCHAR(500),
    address1 VARCHAR(500),
    ...
    valid_from TIMESTAMP,
    valid_to TIMESTAMP,           -- NULL for current record
    is_current BOOLEAN,
    change_reason VARCHAR(100)    -- 'address_change', 'status_change', etc.
);
```

### Dimensional Modeling for Analytics

```sql
-- Fact table
CREATE TABLE fact_facility_enrollments (
    date_key INT,
    facility_key INT,
    state_key INT,
    facility_type_key INT,
    capacity INT,
    enrollment_count INT,
    quality_score DECIMAL(5,2)
);

-- Dimension tables
CREATE TABLE dim_facility (...);
CREATE TABLE dim_date (...);
CREATE TABLE dim_geography (...);
```

## 4. AI/ML at Scale

### Current State
- Real-time LLM calls during transformation
- No monitoring or evaluation
- Limited cost controls

### Target Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      AI/ML Architecture                          │
└─────────────────────────────────────────────────────────────────┘

  ┌─────────────────────────────────────────────────────────────┐
  │                    Batch Inference Pipeline                  │
  │                                                              │
  │  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐     │
  │  │  Unclassified│   │   LLM       │    │  Classified │     │
  │  │   Records    │──▶│  Inference  │───▶│  Records    │     │
  │  │              │   │  (Nightly)  │    │             │     │
  │  └─────────────┘    └─────────────┘    └─────────────┘     │
  │                            │                                 │
  │                            ▼                                 │
  │                   ┌─────────────────┐                       │
  │                   │  Prompt Version │                       │
  │                   │  Control (Git)  │                       │
  │                   └─────────────────┘                       │
  └─────────────────────────────────────────────────────────────┘

  ┌─────────────────────────────────────────────────────────────┐
  │                    Monitoring & Evaluation                   │
  │                                                              │
  │  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐     │
  │  │  Accuracy   │    │  Token Cost │    │  Latency    │     │
  │  │  Tracking   │    │  Tracking   │    │  Tracking   │     │
  │  └─────────────┘    └─────────────┘    └─────────────┘     │
  │                                                              │
  │  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐     │
  │  │  Low Conf   │    │  Human-in-  │    │  Feedback   │     │
  │  │  Detection  │───▶│  Loop Queue │◀───│  Loop       │     │
  │  └─────────────┘    └─────────────┘    └─────────────┘     │
  └─────────────────────────────────────────────────────────────┘
```

### Cost Optimization Strategies

| Strategy | Implementation | Expected Savings |
|----------|----------------|------------------|
| Embedding-based dedup | Use embeddings for similarity instead of LLM | 80% on dedup |
| Fine-tuned classifier | Train small model for facility types | 90% on classification |
| Cache warming | Pre-compute embeddings for common values | 50% on repeats |
| Batch sizing | Process 100+ items per LLM call | 30% on API calls |

### Model/Prompt Versioning

```
ai_models/
├── facility_classifier/
│   ├── v1.0.0/
│   │   ├── prompt.txt
│   │   ├── evaluation_results.json
│   │   └── training_data.jsonl
│   ├── v1.1.0/
│   │   └── ...
│   └── latest -> v1.1.0
├── schema_inferrer/
│   └── ...
└── entity_resolver/
    └── ...
```

### Human-in-the-Loop for Low Confidence

```python
# Queue low-confidence classifications for review
if classification['confidence'] < 0.7:
    human_review_queue.send({
        'record_id': record['record_id'],
        'input': record['facility_type'],
        'ai_suggestion': classification['category'],
        'confidence': classification['confidence']
    })
```

## 5. Infrastructure

### Cloud-Native Architecture (AWS)

```
┌─────────────────────────────────────────────────────────────────┐
│                    AWS Infrastructure                            │
└─────────────────────────────────────────────────────────────────┘

  ┌─────────────────────────────────────────────────────────────┐
  │                        VPC                                   │
  │  ┌─────────────────────────────────────────────────────┐   │
  │  │  Public Subnets                                    │   │
  │  │  - ALB (Application Load Balancer)                 │   │
  │  │  - NAT Gateway                                     │   │
  │  └─────────────────────────────────────────────────────┘   │
  │                          │                                  │
  │  ┌─────────────────────────────────────────────────────┐   │
  │  │  Private Subnets                                   │   │
  │  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐ │   │
  │  │  │   ECS       │  │   Lambda    │  │  Redshift   │ │   │
  │  │  │  (Fargate)  │  │  (ETL Jobs) │  │  (Warehouse)│ │   │
  │  │  └─────────────┘  └─────────────┘  └─────────────┘ │   │
  │  └─────────────────────────────────────────────────────┘   │
  └─────────────────────────────────────────────────────────────┘

  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
  │     S3      │  │   SQS/SNS   │  │  EventBridge│
  │  (Data Lake)│  │  (Queues)   │  │  (Scheduler)│
  └─────────────┘  └─────────────┘  └─────────────┘
```

### Infrastructure as Code (Terraform)

```hcl
# main.tf - ETL Pipeline Infrastructure
module "etl_pipeline" {
  source = "./modules/etl"
  
  environment = "production"
  
  # Compute
  ecs_cluster_name = "etl-cluster"
  task_cpu         = 2048
  task_memory      = 8192
  
  # Storage
  s3_raw_bucket    = "facility-leads-raw"
  s3_processed_bucket = "facility-leads-processed"
  
  # Database
  redshift_cluster = "facility-leads-warehouse"
  
  # Monitoring
  enable_datadog   = true
  pagerduty_key    = var.pagerduty_key
}
```

### CI/CD Pipeline

```yaml
# .github/workflows/deploy.yml
name: Deploy ETL Pipeline

on:
  push:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Run Tests
        run: pytest tests/ --cov=src --cov-fail-under=80
      
  deploy:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - name: Deploy to ECS
        run: terraform apply -auto-approve
      - name: Run DB Migrations
        run: alembic upgrade head
      - name: Smoke Test
        run: python -m src.main --dry-run
```

### Monitoring & Alerting

| Metric | Threshold | Alert Channel |
|--------|-----------|---------------|
| Pipeline duration | > 2 hours | PagerDuty |
| Error rate | > 5% | PagerDuty |
| Data quality score | < 70 avg | Slack |
| Duplicate rate | > 30% | Slack |
| LLM token usage | > $100/day | Email |

### Data Quality with Great Expectations

```python
# expectations/leads_expectations.py
validator.expect_column_values_to_not_be_null("company")
validator.expect_column_values_to_match_regex("phone", r"\(\d{3}\) \d{3}-\d{4}")
validator.expect_column_values_to_be_between("data_quality_score", 0, 100)
validator.expect_column_pair_values_to_be_equal("state", "zip", state_zip_match)
```

## 6. Implementation Roadmap

### Phase 1: Foundation (Months 1-2)
- [ ] Migrate to PostgreSQL
- [ ] Implement Dagster orchestration
- [ ] Set up S3 data lake
- [ ] Deploy to ECS

### Phase 2: Scale (Months 3-4)
- [ ] Implement medallion architecture
- [ ] Add schema registry
- [ ] Build monitoring dashboard
- [ ] Implement SCD Type 2

### Phase 3: Intelligence (Months 5-6)
- [ ] Fine-tune facility classifier
- [ ] Implement embedding-based dedup
- [ ] Build human-in-the-loop workflow
- [ ] Add predictive analytics

### Phase 4: Optimization (Months 7-8)
- [ ] Cost optimization review
- [ ] Performance tuning
- [ ] Disaster recovery testing
- [ ] Documentation and training

## 7. Cost Estimates

### Monthly Costs (Production Scale)

| Component | Service | Estimated Cost |
|-----------|---------|----------------|
| Compute | ECS Fargate | $500-1000 |
| Storage | S3 (10TB) | $230 |
| Database | Redshift | $1000-2000 |
| LLM API | OpenAI | $500-1500 |
| Monitoring | Datadog | $500 |
| **Total** | | **$3000-5500/month** |

### Cost vs. Scale

| Records/Month | Compute | Storage | LLM | Total |
|---------------|---------|---------|-----|-------|
| 100K | $200 | $50 | $200 | $450 |
| 1M | $500 | $200 | $800 | $1500 |
| 10M | $2000 | $1000 | $3000 | $6000 |

## 8. Risk Mitigation

| Risk | Mitigation |
|------|------------|
| LLM API downtime | Rule-based fallback, request queueing |
| Schema drift | Automated detection, human review workflow |
| Data quality issues | Great Expectations, quality gates |
| Cost overruns | Token budgets, usage alerts, caching |
| Security breaches | Encryption, IAM roles, audit logging |

## Conclusion

This long-term strategy provides a clear path from the current MVP to a production-grade, scalable ETL system. The phased approach allows for incremental value delivery while building toward the target architecture.

Key success metrics:
- Process 100+ sources with < 2 hour latency
- Maintain > 95% data quality score
- Keep LLM costs under $2000/month at scale
- Achieve 99.9% pipeline uptime
