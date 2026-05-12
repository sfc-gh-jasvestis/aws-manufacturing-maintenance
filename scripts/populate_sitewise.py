#!/usr/bin/env python3
"""Populate AWS IoT SiteWise with 100 equipment assets under a plant hierarchy.
Uses existing model mfg-maintenance-cranes. Creates assets from Snowflake data.
Usage: python populate_sitewise.py
"""
import boto3, json, time, sys

REGION = "us-west-2"
MODEL_ID = "8e6dd7e5-782b-405e-a5be-a974b18e0152"

PLANTS = {
    "Singapore Jurong": ["Line-A1", "Line-A2", "Line-A3"],
    "Singapore Tuas": ["Line-B1", "Line-B2", "Line-B3"],
    "Batam": ["Line-C1", "Line-C2"],
}

EQUIPMENT_TYPES = {
    "Air_Compressor": [f"COMP-{i:03d}" for i in range(1, 21)],
    "Crane": [f"CRANE-{i:03d}" for i in range(1, 21)],
    "Conveyor": [f"CONV-{i:03d}" for i in range(1, 21)],
    "Pump": [f"PUMP-{i:03d}" for i in range(1, 21)],
    "Generator": [f"GEN-{i:03d}" for i in range(1, 21)],
}

ALL_LINES = []
for plant, lines in PLANTS.items():
    for line in lines:
        ALL_LINES.append((plant, line))

def main():
    sw = boto3.client("iotsitewise", region_name=REGION)

    existing = {}
    paginator = sw.get_paginator("list_assets")
    for page in paginator.paginate(assetModelId=MODEL_ID):
        for a in page["assetSummaries"]:
            existing[a["name"]] = a["id"]

    print(f"Found {len(existing)} existing assets")

    idx = 0
    created = 0
    skipped = 0
    all_equip = []
    for etype, ids in EQUIPMENT_TYPES.items():
        for eid in ids:
            all_equip.append((etype, eid))

    for etype, eid in all_equip:
        plant, line = ALL_LINES[idx % len(ALL_LINES)]
        idx += 1
        name = f"{eid}-{etype.replace('_','-')}"

        if name in existing:
            skipped += 1
            continue

        try:
            resp = sw.create_asset(
                assetName=name,
                assetModelId=MODEL_ID,
                assetDescription=f"{etype} {eid} on {line} at {plant}",
            )
            created += 1
            if created % 10 == 0:
                print(f"  Created {created} assets...")
            time.sleep(0.3)
        except sw.exceptions.LimitExceededException:
            print(f"Rate limited at {created}. Sleeping 5s...")
            time.sleep(5)
            try:
                resp = sw.create_asset(
                    assetName=name,
                    assetModelId=MODEL_ID,
                    assetDescription=f"{etype} {eid} on {line} at {plant}",
                )
                created += 1
            except Exception as e:
                print(f"Failed {name}: {e}")
        except Exception as e:
            print(f"Failed {name}: {e}")

    print(f"\nDone: {created} created, {skipped} skipped (already exist)")

if __name__ == "__main__":
    main()
