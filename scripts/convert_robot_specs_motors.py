#!/usr/bin/env python3
"""Convert motors lists to dicts keyed by motor name in robot_specs.json.

Backs up the original file to robot_specs.json.bak on first run.
"""
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
SPEC_PATH = ROOT / "src" / "leropilot" / "resources" / "robot_specs.json"
BACKUP_PATH = SPEC_PATH.with_suffix(".json.bak")

if not SPEC_PATH.exists():
    raise SystemExit(f"Spec file not found: {SPEC_PATH}")

# Backup on first run
if not BACKUP_PATH.exists():
    BACKUP_PATH.write_text(SPEC_PATH.read_text(encoding="utf-8"), encoding="utf-8")

raw = SPEC_PATH.read_text(encoding="utf-8")
# preserve existing JSON structure
data = json.loads(raw)

converted = []
skipped = []
warnings = []

for robot in data.get("robots", []):
    r_id = robot.get("id")
    motor_buses = robot.get("motor_buses", {})
    for bus_name, bus in motor_buses.items():
        motors = bus.get("motors")
        if isinstance(motors, list):
            new_motors = {}
            for i, m in enumerate(motors):
                if not isinstance(m, dict):
                    warnings.append(f"robot={r_id} bus={bus_name} index={i} motor not dict: {m}")
                    continue
                key = m.get("name")
                if not key:
                    key = f"__index_{i}"
                    # keep name field as required by the new spec
                    m["name"] = key
                    warnings.append(f"robot={r_id} bus={bus_name} index={i} had no name; set to {key}")
                if key in new_motors:
                    # avoid collision by making unique
                    uniq = f"{key}_{i}"
                    warnings.append(f"duplicate motor name '{key}' in robot={r_id} bus={bus_name}; using '{uniq}'")
                    new_motors[uniq] = m
                else:
                    new_motors[key] = m
            bus["motors"] = new_motors
            converted.append((r_id, bus_name, len(motors)))
        else:
            skipped.append((r_id, bus_name))

# Write back
SPEC_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=4) + "\n", encoding="utf-8")

# Report
print("Conversion complete.")
print()
print(f"Total robot buses converted: {len(converted)}")
for r, b, n in converted:
    print(f" - robot={r} bus={b} motors_converted={n}")
if skipped:
    print()
    print(f"Buses already in dict form (skipped): {len(skipped)}")
    for r, b in skipped:
        print(f" - robot={r} bus={b}")
if warnings:
    print()
    print("Warnings:")
    for w in warnings:
        print(f" - {w}")

# Sanity check: ensure no motors remain as list
remaining = []
for robot in data.get("robots", []):
    r_id = robot.get("id")
    for bus_name, bus in robot.get("motor_buses", {}).items():
        if isinstance(bus.get("motors"), list):
            remaining.append((r_id, bus_name))

if remaining:
    print()
    print("Error: some motor lists remain:")
    for r, b in remaining:
        print(f" - robot={r} bus={b}")
    raise SystemExit("Conversion incomplete; see above")
else:
    print()
    print("Sanity check passed: no motor lists remain.")
