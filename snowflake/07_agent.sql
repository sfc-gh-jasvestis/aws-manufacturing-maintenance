-- Predictive Maintenance: Cortex Agent
USE SCHEMA MANUFACTURING_MAINTENANCE.AI;

CREATE OR REPLACE CORTEX AGENT MAINTENANCE_AGENT
    COMMENT = 'AI assistant for predictive maintenance and equipment health'
    MODEL = 'claude-3-5-sonnet'
    TOOLS = (
        'MANUFACTURING_MAINTENANCE.AI.MAINTENANCE_ANALYTICS_VIEW' AS MaintenanceAnalyst,
        'MANUFACTURING_MAINTENANCE.SEARCH.MAINTENANCE_DOCS_SEARCH' AS MaintenanceSearch,
        'snowflake.cortex.data_to_chart' AS ChartGenerator
    )
    SYSTEM_PROMPT = 'You are a predictive maintenance intelligence assistant. Help plant managers monitor equipment health, interpret sensor anomalies, prioritize maintenance actions, and prevent unplanned downtime. Always reference specific equipment IDs, sensor values, and time-to-failure estimates.';
