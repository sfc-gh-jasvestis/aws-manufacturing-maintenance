"""Publish simulated production-asset telemetry to AWS IoT Core (topic sg/mfg/telemetry).

The IoT rule lands each message in S3; Snowpipe loads it into RAW.LIVE_TELEMETRY.
Machine IDs come from RAW.MACHINES (EQP-0000..EQP-0023). Values are seeded random.
"""
import argparse
import json
import random
from datetime import datetime, timezone


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--region', default='us-west-2')
    ap.add_argument('--count', type=int, default=40)
    ap.add_argument('--seed', type=int)
    args = ap.parse_args()
    import boto3
    iot = boto3.client('iot', region_name=args.region)
    endpoint = iot.describe_endpoint(endpointType='iot:Data-ATS')['endpointAddress']
    data = boto3.client('iot-data', region_name=args.region, endpoint_url=f'https://{endpoint}')
    rng = random.Random(args.seed)
    for _ in range(args.count):
        machine = f'EQP-{rng.randint(0, 23):04d}'
        alarm = rng.random() < 0.1
        msg = {'machine_id': machine,
               'event_ts': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3],
               'vibration_mm_s': round(rng.gauss(7.5 if alarm else 3.0, 0.8), 2),
               'temperature_c': round(rng.gauss(78 if alarm else 55, 4), 1),
               'status': 'ALARM' if alarm else 'RUNNING'}
        data.publish(topic='sg/mfg/telemetry', qos=1, payload=json.dumps(msg))
    print(f'published {args.count} messages to sg/mfg/telemetry via {endpoint}')


if __name__ == '__main__':
    main()
