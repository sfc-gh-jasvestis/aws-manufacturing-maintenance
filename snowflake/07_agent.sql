-- Predictive Maintenance: Cortex Agent
USE SCHEMA MANUFACTURING_MAINTENANCE.AI;

CREATE OR REPLACE AGENT MAINTENANCE_AGENT
    COMMENT = 'Predictive maintenance AI agent for equipment health analysis and documentation search'
    PROFILE = '{"display_name": "Maintenance Agent", "color": "orange"}'
    FROM SPECIFICATION
    $$
    models:
      orchestration: auto

    orchestration:
      budget:
        seconds: 30
        tokens: 16000

    instructions:
      response: "You are an expert predictive maintenance engineer. Provide concise, actionable insights about equipment health, failure risks, and maintenance recommendations. Always highlight critical equipment first."
      orchestration: "For questions about equipment health metrics, anomaly counts, maintenance schedules, costs, or any quantitative data, use MaintenanceAnalyst. For questions about maintenance procedures, troubleshooting guides, safety protocols, or spare parts information, use MaintenanceDocs."
      system: "You are a predictive maintenance AI assistant for industrial port equipment. You help maintenance engineers identify equipment at risk of failure, find relevant procedures, and make data-driven maintenance decisions."
      sample_questions:
        - question: "Which equipment has the lowest health score?"
          answer: "I'll query the equipment health data to find equipment with the lowest scores."
        - question: "What is the vibration troubleshooting procedure for cranes?"
          answer: "I'll search the maintenance documentation for crane vibration procedures."
        - question: "How many anomaly alerts are active right now?"
          answer: "I'll check the current anomaly alert count from our monitoring data."

    tools:
      - tool_spec:
          type: "cortex_analyst_text_to_sql"
          name: "MaintenanceAnalyst"
          description: "Queries structured maintenance data including equipment health scores (0-100 scale where lower is worse), anomaly alerts for sensors trending toward failure thresholds, and maintenance schedules with overdue calculations. Use for any quantitative questions about equipment status, costs, counts, or trends."
      - tool_spec:
          type: "cortex_search"
          name: "MaintenanceDocs"
          description: "Searches 416 maintenance documents including OEM machine manuals (installation, operation, troubleshooting, calibration), technician field notes and repair logs with specific equipment IDs and sensor readings, safety bulletins (LOTO, arc flash, confined space, OSHA references), and spare parts catalogs with part numbers (SKF, Parker, Gates, etc.). Use for procedural questions, past repair history for specific equipment, troubleshooting, safety protocols, and parts lookup."
      - tool_spec:
          type: "data_to_chart"
          name: "data_to_chart"
          description: "Generates visualizations from equipment health and maintenance data"

    tool_resources:
      MaintenanceAnalyst:
        semantic_view: "MANUFACTURING_MAINTENANCE.AI.MAINTENANCE_ANALYTICS_VIEW"
      MaintenanceDocs:
        name: "MANUFACTURING_MAINTENANCE.SEARCH.MAINTENANCE_DOCS_SEARCH"
        max_results: "5"
        title_column: "TITLE"
    $$;
