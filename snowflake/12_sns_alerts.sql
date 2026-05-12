-- ============================================================================
-- 12_sns_alerts.sql
-- Outbound SNS notification integration + Snowflake Alert
-- ============================================================================
-- Architecture:
--   Equipment health < 20 -> Snowflake Alert (every 5 min) -> SNS topic
--   -> Email/SMS/Lambda subscriber -> Technician on-call
--
-- Prerequisites:
--   1. AWS SNS topic: mfg-maintenance-critical-alerts
--   2. IAM role: snowflake-maintenance-sns-role with sns:Publish
--   3. Trust policy updated with Snowflake IAM user ARN + external ID
--   See aws/README.md for full setup steps.
-- ============================================================================

CREATE OR REPLACE NOTIFICATION INTEGRATION MAINTENANCE_SNS_INT
  ENABLED = TRUE
  DIRECTION = OUTBOUND
  TYPE = QUEUE
  NOTIFICATION_PROVIDER = AWS_SNS
  AWS_SNS_TOPIC_ARN = 'arn:aws:sns:us-west-2:<ACCOUNT_ID>:mfg-maintenance-critical-alerts'
  AWS_SNS_ROLE_ARN = 'arn:aws:iam::<ACCOUNT_ID>:role/snowflake-maintenance-sns-role';

-- After creating, run DESC NOTIFICATION INTEGRATION MAINTENANCE_SNS_INT
-- to get SF_AWS_IAM_USER_ARN and SF_AWS_EXTERNAL_ID for the IAM trust policy.

CREATE OR REPLACE ALERT MANUFACTURING_MAINTENANCE.APP.CRITICAL_EQUIPMENT_ALERT
  WAREHOUSE = CORTEX
  SCHEDULE = '5 MINUTE'
  IF (EXISTS (
    SELECT 1 FROM MANUFACTURING_MAINTENANCE.CURATED.EQUIPMENT_HEALTH
    WHERE HEALTH_SCORE < 20 AND STATUS IN ('CRITICAL', 'OFFLINE')
  ))
  THEN
    CALL SYSTEM$SEND_NOTIFICATION(
      'MAINTENANCE_SNS_INT',
      OBJECT_CONSTRUCT(
        'subject', 'CRITICAL: Equipment Health Alert - Predictive Maintenance',
        'message', (SELECT LISTAGG(NAME || ' (health ' || HEALTH_SCORE::INT || ', ' || STATUS || ')', ', ')
                    FROM MANUFACTURING_MAINTENANCE.CURATED.EQUIPMENT_HEALTH
                    WHERE HEALTH_SCORE < 20 AND STATUS IN ('CRITICAL', 'OFFLINE'))
      )::STRING
    );

ALTER ALERT MANUFACTURING_MAINTENANCE.APP.CRITICAL_EQUIPMENT_ALERT RESUME;
