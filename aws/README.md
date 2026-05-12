# AWS Setup (Optional)

The Snowflake demo works standalone (scripts 00-07). These steps add AWS service integrations for the full closed-loop pipeline.

## Prerequisites

- AWS CLI configured (`aws sts get-caller-identity`)
- Python 3.10+ with `boto3`
- Snowflake account with `ACCOUNTADMIN` access
- AWS account with permissions: S3, IoT SiteWise, SNS, IAM, Lambda, Bedrock, QuickSight

## Variables

```bash
export REGION=us-west-2
export ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
export BUCKET=sg-manufacturing-demos-2026
export SNOWFLAKE_IAM_USER_ARN="<from DESC STORAGE INTEGRATION>"
```

---

## Step 1: S3 Bucket + Real-Time Sensor Data

The batch data is already in `s3://$BUCKET/maintenance/`. Create a real-time prefix for Snowpipe:

```bash
# Upload seed sensor data
python scripts/simulate_sensor_stream.py --batches 5 --upload
```

This creates CSV files at `s3://$BUCKET/maintenance/realtime/sensors_*.csv`.

---

## Step 2: Snowflake Storage Integration + Snowpipe

The storage integration `MANUFACTURING_DEMOS_S3_INTEGRATION` should already exist. If not:

```sql
CREATE STORAGE INTEGRATION MANUFACTURING_DEMOS_S3_INTEGRATION
  TYPE = EXTERNAL_STAGE
  STORAGE_PROVIDER = 'S3'
  ENABLED = TRUE
  STORAGE_AWS_ROLE_ARN = 'arn:aws:iam::<ACCOUNT_ID>:role/snowflake-manufacturing-s3-role'
  STORAGE_ALLOWED_LOCATIONS = ('s3://sg-manufacturing-demos-2026/');

DESC STORAGE INTEGRATION MANUFACTURING_DEMOS_S3_INTEGRATION;
-- Record STORAGE_AWS_IAM_USER_ARN and STORAGE_AWS_EXTERNAL_ID
-- Update IAM role trust policy with these values
```

Then run Snowpipe setup:

```bash
snowsql -f snowflake/09_snowpipe_s3.sql
```

Configure S3 event notification:

```bash
# Get the SQS ARN from Snowflake
# SHOW PIPES LIKE 'SENSOR_REALTIME_PIPE' IN SCHEMA MANUFACTURING_MAINTENANCE.RAW;
# Copy the notification_channel value

SQS_ARN="<notification_channel from SHOW PIPES>"

aws s3api put-bucket-notification-configuration \
  --bucket $BUCKET \
  --notification-configuration "{
    \"QueueConfigurations\": [{
      \"QueueArn\": \"$SQS_ARN\",
      \"Events\": [\"s3:ObjectCreated:*\"],
      \"Filter\": {\"Key\": {\"FilterRules\": [{\"Name\": \"prefix\", \"Value\": \"maintenance/realtime/\"}]}}
    }]
  }" \
  --region $REGION
```

Load existing files:

```sql
ALTER PIPE MANUFACTURING_MAINTENANCE.RAW.SENSOR_REALTIME_PIPE REFRESH;
```

---

## Step 3: AWS IoT SiteWise Asset Model

Create 100 assets under the existing SiteWise model:

```bash
python scripts/populate_sitewise.py
```

This creates assets under model `mfg-maintenance-cranes` with naming convention `EQUIP_ID-Type`.

Then populate Snowflake hierarchy tables:

```bash
snowsql -f snowflake/10_iot_sitewise.sql
```

---

## Step 4: Snowflake ML Model (replaces SageMaker)

Create training data view and RUL predictions Dynamic Table:

```bash
snowsql -f snowflake/11_snowflake_ml.sql
```

Optionally train and register an XGBoost model in the Snowflake Model Registry:

```bash
pip install snowflake-ml-python xgboost scikit-learn
SNOWFLAKE_CONNECTION_NAME=demo43 python scripts/train_rul_model.py
```

---

## Step 5: SNS Alert Topic

Create the SNS topic and IAM role:

```bash
# Create topic
TOPIC_ARN=$(aws sns create-topic --name mfg-maintenance-critical-alerts \
  --region $REGION --output text --query TopicArn)

# Subscribe your email
aws sns subscribe --topic-arn $TOPIC_ARN \
  --protocol email --notification-endpoint your@email.com --region $REGION

# Create IAM role for Snowflake
aws iam create-role --role-name snowflake-maintenance-sns-role \
  --assume-role-policy-document '{
    "Version":"2012-10-17",
    "Statement":[{
      "Effect":"Allow",
      "Principal":{"AWS":"arn:aws:iam::891377248908:root"},
      "Action":"sts:AssumeRole",
      "Condition":{"StringEquals":{"sts:ExternalId":"placeholder"}}
    }]
  }'

# Attach publish policy
aws iam put-role-policy --role-name snowflake-maintenance-sns-role \
  --policy-name sns-publish \
  --policy-document "{
    \"Version\":\"2012-10-17\",
    \"Statement\":[{
      \"Effect\":\"Allow\",
      \"Action\":\"sns:Publish\",
      \"Resource\":\"$TOPIC_ARN\"
    }]
  }"
```

Then create the Snowflake notification integration:

```bash
snowsql -f snowflake/12_sns_alerts.sql
```

**Important**: After creating the integration, update the IAM trust policy:

```sql
DESC NOTIFICATION INTEGRATION MAINTENANCE_SNS_INT;
-- Record SF_AWS_IAM_USER_ARN and SF_AWS_EXTERNAL_ID
```

```bash
aws iam update-assume-role-policy --role-name snowflake-maintenance-sns-role \
  --policy-document '{
    "Version":"2012-10-17",
    "Statement":[{
      "Sid":"",
      "Effect":"Allow",
      "Principal":{"AWS":"<SF_AWS_IAM_USER_ARN>"},
      "Action":"sts:AssumeRole",
      "Condition":{"StringEquals":{"sts:ExternalId":"<SF_AWS_EXTERNAL_ID>"}}
    }]
  }'
```

---

## Step 6: AWS Lambda + Bedrock (Work Order Generator)

Create the Lambda function for Bedrock-powered work order generation:

```bash
# Create IAM role
aws iam create-role --role-name mfg-maint-bedrock-lambda-role \
  --assume-role-policy-document '{
    "Version":"2012-10-17",
    "Statement":[{"Effect":"Allow","Principal":{"Service":"lambda.amazonaws.com"},"Action":"sts:AssumeRole"}]
  }'

aws iam attach-role-policy --role-name mfg-maint-bedrock-lambda-role \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole

aws iam put-role-policy --role-name mfg-maint-bedrock-lambda-role \
  --policy-name bedrock-invoke \
  --policy-document '{
    "Version":"2012-10-17",
    "Statement":[{"Effect":"Allow","Action":"bedrock:InvokeModel","Resource":"*"}]
  }'

# Create Lambda function (Python 3.12, uses boto3 bedrock-runtime)
# See snowflake/08_sitewise_workorder.sql for the Cortex Complete fallback
```

---

## Step 7: QuickSight Dashboard

Requires a QuickSight Snowflake datasource. Once configured:

```bash
python quicksight/build_dashboards.py --demo maintenance
python quicksight/build_dashboards.py --demo maintenance-rul
```

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Snowpipe not loading | Check S3 event notification points to correct SQS ARN. Run `ALTER PIPE ... REFRESH` to manually load. |
| SNS notification not delivered | Verify IAM trust policy has correct SF_AWS_EXTERNAL_ID. Check SNS subscription is confirmed. |
| SiteWise rate limit | Script has built-in backoff. Re-run to skip existing assets. |
| Model Registry error | Ensure `snowflake-ml-python` >= 1.5.0. Check `xgboost` is in Snowflake conda channel. |
| QuickSight datasource | Must have Snowflake connectivity configured in QuickSight first. |

---

## Teardown

```bash
# Snowflake objects
# (DROP CASCADE on database removes everything)

# AWS resources (reverse order)
aws quicksight delete-dashboard --dashboard-id mfg-maintenance-dashboard --aws-account-id $ACCOUNT_ID --region $REGION
aws quicksight delete-dashboard --dashboard-id mfg-maintenance-rul-dashboard --aws-account-id $ACCOUNT_ID --region $REGION

# SNS
aws sns delete-topic --topic-arn arn:aws:sns:$REGION:$ACCOUNT_ID:mfg-maintenance-critical-alerts --region $REGION
aws iam delete-role-policy --role-name snowflake-maintenance-sns-role --policy-name sns-publish
aws iam delete-role --role-name snowflake-maintenance-sns-role

# Lambda
aws lambda delete-function --function-name mfg-maint-workorder-bedrock --region $REGION
aws iam detach-role-policy --role-name mfg-maint-bedrock-lambda-role --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
aws iam delete-role-policy --role-name mfg-maint-bedrock-lambda-role --policy-name bedrock-invoke
aws iam delete-role --role-name mfg-maint-bedrock-lambda-role

# SiteWise (assets then model)
python -c "
import boto3
sw = boto3.client('iotsitewise', region_name='$REGION')
for page in sw.get_paginator('list_assets').paginate(assetModelId='<MODEL_ID>'):
    for a in page['assetSummaries']:
        sw.delete_asset(assetId=a['id'])
        print(f'Deleted {a[\"name\"]}')
"

# S3 sensor data
aws s3 rm s3://$BUCKET/maintenance/realtime/ --recursive --region $REGION
```
