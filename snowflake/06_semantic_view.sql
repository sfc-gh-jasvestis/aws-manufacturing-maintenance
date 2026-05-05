-- Predictive Maintenance: Semantic View
USE SCHEMA MANUFACTURING_MAINTENANCE.AI;

CREATE OR REPLACE SEMANTIC VIEW MAINTENANCE_ANALYTICS_VIEW
    COMMENT = 'Predictive maintenance analytics: equipment health, alerts, work orders'
AS
    TABLES (
        CURATED.EQUIPMENT_HEALTH AS equipment
            COLUMNS (
                EQUIPMENT_NAME AS equipment_name COMMENT 'Name of the equipment asset',
                EQUIPMENT_TYPE AS equipment_type COMMENT 'Type: CRANE, REEFER, CONVEYOR, PUMP, etc.',
                CRITICALITY AS criticality COMMENT 'CRITICAL, HIGH, MEDIUM, LOW',
                HEALTH_STATUS AS health_status COMMENT 'HEALTHY, WARNING, CRITICAL',
                HEALTH_SCORE_PCT AS health_score COMMENT 'Composite health score 0-100',
                CURRENT_VIBRATION AS vibration COMMENT 'Current vibration in mm/s',
                VIBRATION_THRESHOLD AS vibration_limit COMMENT 'Vibration alarm threshold',
                CURRENT_TEMPERATURE AS temperature COMMENT 'Current temperature in Celsius',
                TEMPERATURE_THRESHOLD AS temperature_limit COMMENT 'Temperature alarm threshold'
            ),
        CURATED.ANOMALY_ALERTS AS alerts
            COLUMNS (
                EQUIPMENT_NAME AS equipment_name COMMENT 'Equipment with active alert',
                ALERT_TYPE AS alert_type COMMENT 'VIBRATION or TEMPERATURE',
                CURRENT_VALUE AS current_reading COMMENT 'Current sensor value',
                THRESHOLD_VALUE AS threshold COMMENT 'Configured alarm threshold',
                TREND AS trend_direction COMMENT 'INCREASING, STABLE, or DECREASING',
                HOURS_TO_BREACH AS hours_remaining COMMENT 'Estimated hours until threshold breach'
            ),
        CURATED.MAINTENANCE_SCHEDULE AS work_orders
            COLUMNS (
                EQUIPMENT_NAME AS equipment_name COMMENT 'Equipment for this work order',
                WO_TYPE AS work_order_type COMMENT 'PREVENTIVE, CORRECTIVE, EMERGENCY',
                PRIORITY AS priority COMMENT 'Priority level',
                STATUS AS status COMMENT 'OPEN, IN_PROGRESS, OVERDUE',
                DAYS_OVERDUE AS days_overdue COMMENT 'Days past scheduled date (negative = upcoming)'
            )
    );
