-- ============================================================================
-- 09_snowpipe_s3.sql
-- Real-time sensor ingestion: S3 -> Snowpipe -> SENSOR_READINGS_REALTIME
-- ============================================================================
-- Architecture:
--   Factory sensors -> IoT SiteWise -> S3 hot-tier export (realtime/ prefix)
--   -> Snowpipe AUTO_INGEST -> RAW.SENSOR_READINGS_REALTIME
--   -> Dynamic Tables consume both SENSOR_READINGS and SENSOR_READINGS_REALTIME
--
-- Prerequisites:
--   Storage integration MANUFACTURING_DEMOS_S3_INTEGRATION must exist
--   (created during initial account setup — see aws/README.md for IAM details)
-- ============================================================================

USE SCHEMA MANUFACTURING_MAINTENANCE.RAW;

CREATE OR REPLACE STAGE REALTIME_SENSOR_STAGE
    STORAGE_INTEGRATION = MANUFACTURING_DEMOS_S3_INTEGRATION
    URL = 's3://sg-manufacturing-demos-2026/maintenance/realtime/'
    FILE_FORMAT = (
        TYPE = 'CSV'
        SKIP_HEADER = 1
        FIELD_OPTIONALLY_ENCLOSED_BY = '"'
        NULL_IF = ('', 'NULL')
    );

CREATE OR REPLACE TABLE SENSOR_READINGS_REALTIME (
    READING_ID VARCHAR,
    EQUIPMENT_ID VARCHAR,
    TIMESTAMP TIMESTAMP_NTZ,
    VIBRATION_MM_S NUMBER(6,3),
    TEMPERATURE_C NUMBER(6,2),
    PRESSURE_BAR NUMBER(6,2),
    CURRENT_A NUMBER(6,2),
    OPERATIONAL_HOURS NUMBER,
    INGESTED_AT TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);

CREATE OR REPLACE PIPE SENSOR_REALTIME_PIPE
    AUTO_INGEST = TRUE
    COMMENT = 'Auto-ingest sensor CSVs from S3 realtime/ prefix via SQS'
AS
    COPY INTO SENSOR_READINGS_REALTIME (
        READING_ID, EQUIPMENT_ID, TIMESTAMP,
        VIBRATION_MM_S, TEMPERATURE_C, PRESSURE_BAR,
        CURRENT_A, OPERATIONAL_HOURS
    )
    FROM @REALTIME_SENSOR_STAGE
    FILE_FORMAT = (
        TYPE = 'CSV'
        SKIP_HEADER = 1
        FIELD_OPTIONALLY_ENCLOSED_BY = '"'
        NULL_IF = ('', 'NULL')
    );

-- Show the SQS ARN for S3 event notification configuration
SHOW PIPES LIKE 'SENSOR_REALTIME_PIPE' IN SCHEMA MANUFACTURING_MAINTENANCE.RAW;
-- Note the notification_channel column — use this ARN in the S3 event notification
