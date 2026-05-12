#!/usr/bin/env python3
"""Generate synthetic real-time sensor CSVs and upload to S3.
Usage: python simulate_sensor_stream.py [--batches N] [--upload]
"""
import csv, io, random, uuid, argparse
from datetime import datetime, timezone

BUCKET = "sg-manufacturing-demos-2026"
PREFIX = "maintenance/realtime"
REGION = "us-west-2"

EQUIPMENT = [f"COMP-{i:03d}" for i in range(1, 21)] + \
            [f"CRANE-{i:03d}" for i in range(1, 21)] + \
            [f"CONV-{i:03d}" for i in range(1, 21)] + \
            [f"PUMP-{i:03d}" for i in range(1, 21)] + \
            [f"GEN-{i:03d}" for i in range(1, 21)]

FAILING = {"COMP-021", "COMP-033", "REEF-055", "REEF-034", "REEF-022", "PUMP-018", "CRANE-015"}

def gen_reading(equip_id, ts):
    failing = equip_id in FAILING
    vib = round(random.gauss(4.8 if failing else 2.5, 0.8 if failing else 0.5), 3)
    temp = round(random.gauss(72 if failing else 45, 8 if failing else 5), 2)
    pres = round(random.gauss(11.5 if failing else 8.0, 1.2 if failing else 0.8), 2)
    cur = round(random.gauss(42 if failing else 25, 5 if failing else 3), 2)
    hrs = random.randint(8000, 45000)
    return [str(uuid.uuid4())[:8], equip_id, ts.strftime("%Y-%m-%d %H:%M:%S"),
            max(0, vib), temp, max(0, pres), max(0, cur), hrs]

def gen_batch():
    ts = datetime.now(timezone.utc)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["READING_ID","EQUIPMENT_ID","TIMESTAMP","VIBRATION_MM_S",
                "TEMPERATURE_C","PRESSURE_BAR","CURRENT_A","OPERATIONAL_HOURS"])
    for eq in EQUIPMENT:
        w.writerow(gen_reading(eq, ts))
    return buf.getvalue()

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--batches", type=int, default=5)
    p.add_argument("--upload", action="store_true")
    args = p.parse_args()

    for i in range(args.batches):
        data = gen_batch()
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        key = f"{PREFIX}/sensors_{ts}_{i:03d}.csv"
        if args.upload:
            import boto3
            s3 = boto3.client("s3", region_name=REGION)
            s3.put_object(Bucket=BUCKET, Key=key, Body=data.encode())
            print(f"Uploaded s3://{BUCKET}/{key}")
        else:
            fname = f"/tmp/sensors_{ts}_{i:03d}.csv"
            with open(fname, "w") as f:
                f.write(data)
            print(f"Wrote {fname}")

if __name__ == "__main__":
    main()
