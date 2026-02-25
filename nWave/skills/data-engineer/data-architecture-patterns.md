---
name: data-architecture-patterns
description: Data architecture patterns (warehouse, lake, lakehouse, mesh), ETL/ELT pipelines, streaming architectures, scaling strategies, and schema design patterns
---

# Data Architecture Patterns

## Architecture Selection Decision Tree

```
What data types do you have?
  Structured only -> Data Warehouse
  Mixed (structured + semi-structured + unstructured) ->
    Do you need SQL analytics on all data? -> Data Lakehouse
    Is data science/ML the primary use case? -> Data Lake
    Is your organization large with autonomous domain teams? -> Data Mesh
```

## Data Warehouse

Schema: structured, schema-on-write | Data: tables, rows, columns | Governance: centralized | Query: SQL analytics, BI | Architecture: centralized single source of truth

### Schema Patterns

**Star Schema**: Central fact table (measures) surrounded by denormalized dimension tables. Best for BI dashboards, standard reporting.

```
         dim_date
            |
dim_customer--fact_sales--dim_product
            |
         dim_store
```

**Snowflake Schema**: Normalized dimensions (dimensions reference other dimensions). Reduces storage, increases JOIN complexity. Best when storage cost matters more than query speed.

### Kimball vs Inmon

**Kimball (Bottom-Up)**: Build data marts first, integrate later | Star schema, business-process driven | Faster initial delivery | Best for quick wins, department-level analytics

**Inmon (Top-Down)**: Build enterprise DW first, derive data marts | Normalized 3NF enterprise model | Higher upfront effort | Best for large enterprises needing single source of truth

Technology: Snowflake | Amazon Redshift | Google BigQuery | Azure Synapse Analytics

## Data Lake

Schema-on-read, flexible | All formats (structured, semi-structured, unstructured) | Raw data in native format | Query via Athena, Spark SQL, PySpark, Pandas | Risk: "data swamp" without governance

### Organization Pattern
```
data-lake/
  raw/           # Landing zone - original format
  curated/       # Cleaned, validated, standardized
  processed/     # Transformed for specific use cases
  archive/       # Historical data, cold storage
```

### Anti-Patterns
- No metadata catalog -> undiscoverable data
- No access controls -> security/compliance risk
- No data quality checks -> garbage in/out
- No retention policy -> unbounded cost growth

Technology: S3 + Athena/Glue | Azure Data Lake Storage + Synapse | HDFS + Hive

## Data Lakehouse

Combines warehouse reliability with lake flexibility | Schema enforcement on write with evolution support | ACID transactions on lake storage | Supports both BI/SQL and ML/data science workloads

### Medallion Architecture (Bronze / Silver / Gold)

```
Bronze (Raw)          Silver (Validated)       Gold (Business-Ready)
- Raw ingestion       - Cleaned, validated     - Aggregated
- Schema-on-read      - Deduplicated           - Business logic applied
- Full history        - Schema enforced        - Star/snowflake schema
- Audit trail         - Standardized formats   - Ready for BI/reporting
```

**Bronze**: Raw data as-is, append-only for auditability, partitioned by ingestion date, minimal transformations
**Silver**: Quality rules (null checks, range validation, referential integrity) | Deduplication on business keys | Schema standardization | SCD applied
**Gold**: Business-level aggregations | Dimensional models | Pre-computed metrics/KPIs | Optimized for query performance

Technology: Databricks (Delta Lake) | Apache Iceberg | Apache Hudi

## Data Mesh

### Core Principles (Martin Fowler)
1. **Domain-oriented ownership**: Data owned by domain teams, not central
2. **Data as a product**: Each domain publishes discoverable, trustworthy, self-describing data products
3. **Self-serve data platform**: Infrastructure team provides platform for domain teams
4. **Federated computational governance**: Global standards with domain autonomy

**Use when**: Large org with autonomous domain teams | Central data team is bottleneck | Domain expertise needed | Platform engineering maturity exists
**Avoid when**: Small team (<50 engineers) | Simple data needs | No platform capability | Unclear domain boundaries

## ETL vs ELT Pipeline Design

### ETL (Extract-Transform-Load)
```
Source -> [Extract] -> Staging -> [Transform] -> [Load] -> Target
```
Transform before loading via dedicated engine (Informatica, Talend, SSIS). Best for complex transforms, constrained targets, regulatory requirements. Scaling limited by transform engine.

### ELT (Extract-Load-Transform)
```
Source -> [Extract] -> [Load] -> Target -> [Transform in-place]
```
Load raw first, transform using target compute (dbt, Snowflake SQL, BigQuery SQL). Best for cloud DWs with elastic compute, preserving raw data. Scales with target system.

### Pipeline Design Principles
- **Idempotency**: Re-running produces same result (use MERGE/upsert, not INSERT)
- **Incremental processing**: Process only new/changed data (watermarks, CDC)
- **Schema evolution**: Handle added/removed columns gracefully (schema registry)
- **Data quality gates**: Validate between stages (null rates, row counts, value ranges)
- **Observability**: Log metrics (rows processed, duration, errors, freshness)

### Orchestration
Apache Airflow: DAG-based, Python-native, wide adoption | Prefect: modern, dynamic workflows | Dagster: software-defined assets

## Streaming Architecture

### Apache Kafka
Distributed event streaming platform | Use as event bus, message broker, stream storage | Concepts: topics, partitions, consumer groups, offsets | At-least-once delivery (exactly-once with transactions) | Configurable retention or compacted topics

### Apache Flink
Stateful stream processing engine | Use for real-time analytics, event processing, CDC | Concepts: DataStreams, windows (tumbling, sliding, session), state management | Exactly-once with checkpointing

### Kafka + Flink Pattern
```
Sources -> Kafka (event storage) -> Flink (stream processing) -> Sinks
```
Kafka provides durable scalable event buffer | Flink provides stateful computation | Combined: end-to-end exactly-once semantics

### Streaming vs Batch
- **Streaming**: Real-time dashboards, fraud detection, IoT, event-driven architectures
- **Batch**: Overnight reporting, historical analysis, large transforms, ML training
- **Lambda**: Parallel batch + stream (complex, consider Kappa instead)
- **Kappa**: Stream-only, reprocess from Kafka log (simpler, requires retention)

## Scaling Strategies

### Vertical (Scale Up)
Add CPU/RAM/storage to existing server | Simpler ops, no app changes | Hard limit: largest hardware | Use first for moderate growth

### Horizontal (Scale Out)

**Read Replicas**: Replicate to read-only copies | Route reads to replicas, writes to primary | Trade-off: replication lag (eventual consistency) | Use for read-heavy workloads

**Partitioning (Single Server)**: Range (date, alphabetical) | List (region, category) | Hash (even distribution) | Benefits: query pruning, maintenance (drop old partitions)

**Sharding (Multiple Servers)**: Distribute data across DB instances by shard key | Strategies: range-based, hash-based, directory-based, geographic

**Shard Key Selection** (most impactful decision):
- High cardinality for even distribution
- Even access frequency to avoid hot shards
- Query alignment: most queries target single shard
- Avoid monotonically increasing keys (hot spots)

**Challenges**: Cross-shard queries need scatter-gather | Distributed transactions (2PC) complex/slow | Resharding expensive | App complexity increases

### Scaling Decision Guide
```
Current load exceeding single server?
  NO -> Optimize queries and indexes first
  YES -> Is it read-heavy?
    YES -> Add read replicas
    NO (write-heavy) -> Is data naturally partitionable?
      YES -> Partition within server first, then shard if needed
      NO -> Consider write-optimized databases (Cassandra, DynamoDB)
```

## Normalization vs Denormalization

**Normalize (3NF)**: OLTP with frequent writes | Data integrity paramount | Storage optimization | Write > read performance
**Denormalize**: OLAP/analytics (star schema) | Read-heavy, predictable queries | Query > write performance | Acceptable redundancy

**Practical approach**: Start normalized for transactional tables | Add denormalized/materialized views for reporting | Denormalize selectively based on measured performance | Document decisions and rationale
