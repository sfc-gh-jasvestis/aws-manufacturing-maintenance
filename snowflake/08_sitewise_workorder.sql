-- ============================================================================
-- 08_sitewise_workorder.sql
-- AWS hero: AWS IoT SiteWise + AWS Bedrock (work-order generation)
-- ----------------------------------------------------------------------------
-- Architecture (real customer flow):
--   Crane sensors -> AWS IoT SiteWise asset model -> S3 hot-tier export ->
--   Snowflake external table -> Cortex anomaly detection -> Bedrock Lambda
--     `mfg-maint-workorder-bedrock` -> structured work order
--
-- For this demo, the "Bedrock" call uses Snowflake Cortex Complete (Claude on
-- Snowflake) so the demo runs without any AWS API integration. In production
-- the customer swaps the SP body to an external function pointing at
-- arn:aws:lambda:<REGION>:<ACCOUNT_ID>:function:mfg-maint-workorder-bedrock.
-- ============================================================================
CREATE SCHEMA IF NOT EXISTS MANUFACTURING_MAINTENANCE.SITEWISE;

-- Asset model table (mirrors IoT SiteWise asset model `mfg-maintenance/cranes`)
CREATE OR REPLACE TABLE MANUFACTURING_MAINTENANCE.SITEWISE.ASSET_MODEL (
    ASSET_ID         STRING,
    ASSET_NAME       STRING,
    ASSET_MODEL_ID   STRING,
    PARENT_ASSET     STRING,
    PROPERTIES       VARIANT,
    CREATED_AT       TIMESTAMP_NTZ
);

INSERT INTO MANUFACTURING_MAINTENANCE.SITEWISE.ASSET_MODEL
SELECT
    EQUIPMENT_ID                                                  AS ASSET_ID,
    NAME                                                          AS ASSET_NAME,
    'mfg-maintenance/cranes'                                      AS ASSET_MODEL_ID,
    LOCATION                                                      AS PARENT_ASSET,
    OBJECT_CONSTRUCT(
        'health_score',     HEALTH_SCORE,
        'critical_sensors', CRITICAL_SENSORS,
        'warning_sensors',  WARNING_SENSORS,
        'criticality',      CRITICALITY,
        'last_maintenance', LAST_MAINTENANCE::STRING
    )                                                             AS PROPERTIES,
    CURRENT_TIMESTAMP()                                           AS CREATED_AT
FROM MANUFACTURING_MAINTENANCE.CURATED.EQUIPMENT_HEALTH;

-- Reference view that resembles the SiteWise hot-tier export
CREATE OR REPLACE VIEW MANUFACTURING_MAINTENANCE.SITEWISE.VW_SENSOR_ROLLUP AS
SELECT
    am.ASSET_ID,
    am.ASSET_NAME,
    am.PARENT_ASSET,
    eh.HEALTH_SCORE,
    eh.CRITICAL_SENSORS,
    eh.WARNING_SENSORS,
    eh.STATUS,
    eh.CRITICALITY,
    aa.SENSOR_TYPE AS ANOMALY_TYPE,
    aa.TREND_DIRECTION AS SEVERITY,
    aa.CURRENT_VALUE AS SENSOR_VALUE,
    aa.THRESHOLD_HIGH AS THRESHOLD,
    aa.HOURS_TO_BREACH_ESTIMATE AS HOURS_TO_BREACH
FROM MANUFACTURING_MAINTENANCE.SITEWISE.ASSET_MODEL am
JOIN MANUFACTURING_MAINTENANCE.CURATED.EQUIPMENT_HEALTH eh ON am.ASSET_ID = eh.EQUIPMENT_ID
LEFT JOIN MANUFACTURING_MAINTENANCE.CURATED.ANOMALY_ALERTS aa ON aa.EQUIPMENT_ID = am.ASSET_ID;

-- ----------------------------------------------------------------------------
-- SP_GENERATE_WORK_ORDER
-- Returns a markdown work order. In demo: Cortex Complete. In prod: Bedrock.
-- ----------------------------------------------------------------------------
CREATE OR REPLACE PROCEDURE MANUFACTURING_MAINTENANCE.AI.SP_GENERATE_WORK_ORDER(ASSET_ID STRING)
RETURNS STRING
LANGUAGE SQL
AS
$$
DECLARE
    ctx     STRING;
    prompt  STRING;
    answer  STRING;
BEGIN
    SELECT
        'Asset: '            || ASSET_NAME      || '\n' ||
        'Location: '         || PARENT_ASSET    || '\n' ||
        'Status: '           || STATUS          || '\n' ||
        'Criticality: '      || CRITICALITY     || '\n' ||
        'Health score: '     || HEALTH_SCORE::STRING    || '\n' ||
        'Critical sensors: ' || CRITICAL_SENSORS::STRING|| '\n' ||
        'Warning sensors: '  || WARNING_SENSORS::STRING || '\n' ||
        'Anomaly: '          || COALESCE(ANOMALY_TYPE,'NONE') || ' (severity ' || COALESCE(SEVERITY,'NONE') || ')' || '\n' ||
        'Sensor value: '     || COALESCE(SENSOR_VALUE::STRING,'n/a') ||
                              ' / threshold ' || COALESCE(THRESHOLD::STRING,'n/a')
    INTO :ctx
    FROM MANUFACTURING_MAINTENANCE.SITEWISE.VW_SENSOR_ROLLUP
    WHERE ASSET_ID = :ASSET_ID
    LIMIT 1;

    prompt :=
        'You are a maintenance dispatcher. Given the equipment context below, ' ||
        'produce a concise work order in Markdown with these sections: ' ||
        'Summary, Recommended Action, Parts List (with rough quantities), ' ||
        'Required Skills, Estimated Time, Safety Notes. Keep it under 200 words.\n\n' ||
        '<context>\n' || :ctx || '\n</context>';

    answer := SNOWFLAKE.CORTEX.COMPLETE('claude-4-sonnet', :prompt);
    RETURN :answer;
END;
$$;
