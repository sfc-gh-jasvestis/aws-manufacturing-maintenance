-- ============================================================================
-- 13_enhanced_docs.sql
-- Enhanced maintenance documentation: manuals, tech notes, safety, parts
-- ============================================================================
-- Generates ~416 realistic documents using Cortex Complete (Claude):
--   60 Machine Manuals (10 types x 6 equipment types)
--   200 Technician Field Notes (20 equipment x 10 note types)
--   36 Safety Bulletins (6 topics x 6 equipment types)
--   120 Spare Parts Catalog entries (20 part categories x 6 equipment types)
--
-- Run time: ~5 minutes (LLM generation)
-- ============================================================================

USE SCHEMA MANUFACTURING_MAINTENANCE.RAW;

ALTER TABLE MAINTENANCE_DOCS ADD COLUMN IF NOT EXISTS EQUIPMENT_ID VARCHAR(20);
ALTER TABLE MAINTENANCE_DOCS ADD COLUMN IF NOT EXISTS AUTHOR VARCHAR(100);
ALTER TABLE MAINTENANCE_DOCS ADD COLUMN IF NOT EXISTS DOC_DATE DATE;
ALTER TABLE MAINTENANCE_DOCS ADD COLUMN IF NOT EXISTS SEVERITY VARCHAR(20);
ALTER TABLE MAINTENANCE_DOCS ADD COLUMN IF NOT EXISTS PART_NUMBER VARCHAR(50);

TRUNCATE TABLE MAINTENANCE_DOCS;

-- 1. Machine Manuals (60 docs)
INSERT INTO MAINTENANCE_DOCS (DOC_ID, TITLE, CATEGORY, EQUIPMENT_TYPE, CONTENT, LAST_UPDATED, AUTHOR, DOC_DATE)
WITH manual_templates AS (
    SELECT t.TYPE AS EQUIPMENT_TYPE, m.MANUAL_TYPE, m.MANUAL_TITLE,
           ROW_NUMBER() OVER (ORDER BY t.TYPE, m.MANUAL_TYPE) AS RN
    FROM (SELECT DISTINCT TYPE AS TYPE FROM EQUIPMENT) t
    CROSS JOIN (
        SELECT 'Installation' AS MANUAL_TYPE, 'Installation & Commissioning Guide' AS MANUAL_TITLE UNION ALL
        SELECT 'Operation', 'Operating Manual & Procedures' UNION ALL
        SELECT 'Troubleshooting', 'Troubleshooting & Diagnostics Guide' UNION ALL
        SELECT 'Preventive_Maintenance', 'Preventive Maintenance Schedule' UNION ALL
        SELECT 'Parts_Diagram', 'Parts List & Bill of Materials' UNION ALL
        SELECT 'Calibration', 'Sensor Calibration Procedures' UNION ALL
        SELECT 'Lubrication', 'Lubrication Chart & Schedule' UNION ALL
        SELECT 'Electrical', 'Electrical Schematics & Wiring' UNION ALL
        SELECT 'Decommission', 'Decommissioning & Disposal Procedure' UNION ALL
        SELECT 'Warranty', 'Warranty Terms & Service Intervals'
    ) m
)
SELECT
    'MAN-' || LPAD(RN::STRING, 4, '0'),
    EQUIPMENT_TYPE || ' — ' || MANUAL_TITLE,
    'Machine_Manual',
    EQUIPMENT_TYPE,
    SNOWFLAKE.CORTEX.COMPLETE('claude-4-sonnet',
        'Write a realistic ' || MANUAL_TYPE || ' manual section for industrial ' || EQUIPMENT_TYPE || ' equipment. ' ||
        'Include specific technical details: measurements, tolerances, part numbers (SKF-XXXX, Parker-XXXX), ' ||
        'safety warnings, tool requirements, step-by-step procedures. ' ||
        'Sensor thresholds: vibration < 6.0 mm/s, temperature < 85C, pressure 2-12 bar, current < 50A. ' ||
        'Write 800-1500 characters. Plain text paragraphs only, no markdown.'
    ),
    DATEADD('day', -UNIFORM(30, 365, RANDOM()), CURRENT_DATE()),
    'OEM Technical Publications',
    DATEADD('day', -UNIFORM(30, 365, RANDOM()), CURRENT_DATE())
FROM manual_templates;

-- 2. Technician Field Notes (200 docs)
INSERT INTO MAINTENANCE_DOCS (DOC_ID, TITLE, CATEGORY, EQUIPMENT_TYPE, EQUIPMENT_ID, CONTENT, LAST_UPDATED, AUTHOR, DOC_DATE)
WITH equip_sample AS (
    SELECT EQUIPMENT_ID, NAME, TYPE, ROW_NUMBER() OVER (ORDER BY RANDOM()) AS RN FROM EQUIPMENT
),
note_types AS (
    SELECT 1 AS NT, 'Repair Log' AS NOTE_TYPE UNION ALL SELECT 2, 'Inspection Report' UNION ALL
    SELECT 3, 'Shift Handover Note' UNION ALL SELECT 4, 'Vibration Analysis' UNION ALL
    SELECT 5, 'Oil Sample Results' UNION ALL SELECT 6, 'Thermal Scan Report' UNION ALL
    SELECT 7, 'Bearing Replacement Log' UNION ALL SELECT 8, 'Alignment Check' UNION ALL
    SELECT 9, 'Pressure Test Results' UNION ALL SELECT 10, 'Emergency Repair Log'
),
combos AS (
    SELECT e.EQUIPMENT_ID, e.NAME, e.TYPE, n.NOTE_TYPE,
           ROW_NUMBER() OVER (ORDER BY e.RN, n.NT) AS COMBO_RN
    FROM equip_sample e CROSS JOIN note_types n WHERE e.RN <= 20
)
SELECT
    'FN-' || LPAD(COMBO_RN::STRING, 4, '0'),
    NAME || ' — ' || NOTE_TYPE,
    'Field_Note', TYPE, EQUIPMENT_ID,
    SNOWFLAKE.CORTEX.COMPLETE('claude-4-sonnet',
        'Write a realistic handwritten-style technician field note for ' || NAME || ' (ID: ' || EQUIPMENT_ID || ', type: ' || TYPE || '). ' ||
        'This is a ' || NOTE_TYPE || '. Use informal technician language with abbreviations. ' ||
        'Include specific sensor readings (vibration mm/s, temp C, pressure bar, current A). ' ||
        'Reference real part numbers (SKF bearings, Parker seals, Gates belts). ' ||
        'Include date, technician initials, observations. Write 400-900 chars. No markdown.'
    ),
    DATEADD('day', -UNIFORM(1, 180, RANDOM()), CURRENT_DATE()),
    CASE UNIFORM(1,8,RANDOM()) WHEN 1 THEN 'T. Rodriguez' WHEN 2 THEN 'M. Chen' WHEN 3 THEN 'S. Patel'
        WHEN 4 THEN 'J. Kim' WHEN 5 THEN 'R. Santos' WHEN 6 THEN 'A. Nakamura'
        WHEN 7 THEN 'D. Okonkwo' ELSE 'L. Petrov' END,
    DATEADD('day', -UNIFORM(1, 180, RANDOM()), CURRENT_DATE())
FROM combos;

-- 3. Safety Bulletins (36 docs)
INSERT INTO MAINTENANCE_DOCS (DOC_ID, TITLE, CATEGORY, EQUIPMENT_TYPE, CONTENT, LAST_UPDATED, AUTHOR, DOC_DATE, SEVERITY)
WITH safety_topics AS (
    SELECT t.TYPE AS EQUIPMENT_TYPE, s.TOPIC, s.SEV,
           ROW_NUMBER() OVER (ORDER BY t.TYPE, s.TOPIC) AS RN
    FROM (SELECT DISTINCT TYPE FROM EQUIPMENT) t
    CROSS JOIN (
        SELECT 'Lockout/Tagout (LOTO) Procedure' AS TOPIC, 'CRITICAL' AS SEV UNION ALL
        SELECT 'Confined Space Entry Protocol', 'CRITICAL' UNION ALL
        SELECT 'Hot Work Permit Requirements', 'WARNING' UNION ALL
        SELECT 'Electrical Safety & Arc Flash', 'CRITICAL' UNION ALL
        SELECT 'Fall Protection Requirements', 'WARNING' UNION ALL
        SELECT 'Chemical Handling & MSDS', 'INFO'
    ) s
)
SELECT
    'SAF-' || LPAD(RN::STRING, 4, '0'),
    EQUIPMENT_TYPE || ' — ' || TOPIC,
    'Safety_Bulletin', EQUIPMENT_TYPE,
    SNOWFLAKE.CORTEX.COMPLETE('claude-4-sonnet',
        'Write an industrial safety bulletin about ' || TOPIC || ' for ' || EQUIPMENT_TYPE || ' equipment. ' ||
        'Include OSHA references (29 CFR 1910.xxx), specific hazards, required PPE, step-by-step procedure, ' ||
        'emergency contacts, consequences of non-compliance. Use WARNING/CAUTION/DANGER markers. ' ||
        'Write 600-1200 chars. Plain text, no markdown.'
    ),
    DATEADD('day', -UNIFORM(30, 365, RANDOM()), CURRENT_DATE()),
    'EHS Department',
    DATEADD('day', -UNIFORM(30, 365, RANDOM()), CURRENT_DATE()),
    SEV
FROM safety_topics;

-- 4. Spare Parts Catalog (120 docs)
INSERT INTO MAINTENANCE_DOCS (DOC_ID, TITLE, CATEGORY, EQUIPMENT_TYPE, CONTENT, LAST_UPDATED, AUTHOR, DOC_DATE, PART_NUMBER)
WITH part_types AS (
    SELECT t.TYPE AS EQUIPMENT_TYPE, p.PART_CAT, p.PART_PREFIX,
           ROW_NUMBER() OVER (ORDER BY t.TYPE, p.PART_CAT) AS RN
    FROM (SELECT DISTINCT TYPE FROM EQUIPMENT) t
    CROSS JOIN (
        SELECT 'Bearings & Seals' AS PART_CAT, 'SKF' AS PART_PREFIX UNION ALL
        SELECT 'Belts & Chains', 'GATES' UNION ALL SELECT 'Filters & Elements', 'DONALDSON' UNION ALL
        SELECT 'Hydraulic Components', 'PARKER' UNION ALL SELECT 'Electrical Components', 'ABB' UNION ALL
        SELECT 'Gaskets & O-Rings', 'GARLOCK' UNION ALL SELECT 'Fasteners & Hardware', 'HILTI' UNION ALL
        SELECT 'Lubricants & Fluids', 'SHELL' UNION ALL SELECT 'Sensors & Instruments', 'FLUKE' UNION ALL
        SELECT 'Motor & Drive Parts', 'SIEMENS' UNION ALL SELECT 'Valves & Fittings', 'SWAGELOK' UNION ALL
        SELECT 'Cooling System Parts', 'GRUNDFOS' UNION ALL SELECT 'Pneumatic Components', 'FESTO' UNION ALL
        SELECT 'Coupling & Alignment', 'REXNORD' UNION ALL SELECT 'Safety Devices', 'HONEYWELL' UNION ALL
        SELECT 'Wear Parts & Liners', 'METSO' UNION ALL SELECT 'Vibration Dampeners', 'LORD' UNION ALL
        SELECT 'Control System Parts', 'SCHNEIDER' UNION ALL SELECT 'Thermal Management', 'WATLOW' UNION ALL
        SELECT 'Structural Components', 'TIMKEN'
    ) p
)
SELECT
    'SPR-' || LPAD(RN::STRING, 4, '0'),
    EQUIPMENT_TYPE || ' — ' || PART_CAT,
    'Spare_Parts', EQUIPMENT_TYPE,
    SNOWFLAKE.CORTEX.COMPLETE('claude-4-sonnet',
        'Write a spare parts catalog entry for ' || PART_CAT || ' used in industrial ' || EQUIPMENT_TYPE || '. ' ||
        'Include 3-5 part numbers (' || PART_PREFIX || '-XXXXX format), descriptions, compatible models, ' ||
        'cost ($XX-$XXXX), lead time (days), min stock, supplier, aftermarket alternatives. ' ||
        'Write 500-1000 chars. Plain text catalog format, no markdown.'
    ),
    DATEADD('day', -UNIFORM(30, 180, RANDOM()), CURRENT_DATE()),
    'Procurement Department',
    DATEADD('day', -UNIFORM(30, 180, RANDOM()), CURRENT_DATE()),
    PART_PREFIX || '-' || LPAD(UNIFORM(10000, 99999, RANDOM())::STRING, 5, '0')
FROM part_types;
