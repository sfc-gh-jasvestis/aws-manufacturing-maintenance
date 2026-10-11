import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from setup_aws import ident, names


class SetupAwsTests(unittest.TestCase):
    def test_names_are_scoped_to_prefix_account_region(self):
        n = names('sg-manufacturing-maintenance', '123456789012', 'us-west-2')
        self.assertEqual(n['bucket'], 'sg-manufacturing-maintenance-123456789012-us-west-2')
        self.assertEqual(n['storage_int'], 'SG_MANUFACTURING_MAINTENANCE_S3_INT')
        self.assertEqual(n['iot_rule'], 'sg_manufacturing_maintenance_telemetry')

    def test_rejects_unsafe_identifiers(self):
        for bad in ['DB; DROP', 'a-b', '1abc', '']:
            with self.assertRaises(ValueError):
                ident(bad)


class IotRequestSchemaTests(unittest.TestCase):
    """Validate the IoT Core requests against the botocore service models (no AWS calls)."""

    def validate(self, service, operation, params):
        import botocore.session
        from botocore.validate import ParamValidator
        model = botocore.session.get_session().get_service_model(service)
        report = ParamValidator().validate(params, model.operation_model(operation).input_shape)
        self.assertFalse(report.has_errors(), report.generate_report())

    def test_topic_rule_request_matches_schema(self):
        from setup_aws import TOPIC
        n = names('sg-manufacturing-maintenance', '123456789012', 'us-west-2')
        rule = {'sql': f"SELECT *, timestamp() AS iot_received_ms FROM '{TOPIC}'", 'awsIotSqlVersion': '2016-03-23',
                'ruleDisabled': False, 'actions': [{'s3': {'roleArn': 'arn:aws:iam::123456789012:role/r',
                                                           'bucketName': n['bucket'],
                                                           'key': 'iot/${timestamp()}-${newuuid()}.json'}}]}
        self.validate('iot', 'CreateTopicRule', {'ruleName': n['iot_rule'], 'topicRulePayload': rule})

    def test_publish_request_matches_schema(self):
        import json
        msg = {'machine_id': 'EQP-0007', 'event_ts': '2026-01-01T00:00:00.000', 'vibration_mm_s': 3.1,
               'temperature_c': 55.0, 'status': 'RUNNING'}
        self.validate('iot-data', 'Publish', {'topic': 'sg/mfg/telemetry', 'qos': 1, 'payload': json.dumps(msg)})

    def test_bucket_name_is_valid_s3_length(self):
        n = names('sg-manufacturing-maintenance', '123456789012', 'ap-southeast-2')
        self.assertLessEqual(len(n['bucket']), 63)


if __name__ == '__main__':
    unittest.main()
