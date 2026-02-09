"""Script to replace MotorLimitTypes.* usages with MotorLimit.LIMIT_* across src files.

This script modifies files in-place and does NOT perform any git operations.
Run locally from project root: python scripts/replace_motorlimittypes.py
"""

import os
import re

ROOT = os.path.join(os.path.dirname(__file__), "..", "src", "leropilot")
changed = []
for dirpath, _, files in os.walk(ROOT):
    for fn in files:
        if not fn.endswith(".py"):
            continue
        fp = os.path.join(dirpath, fn)
        with open(fp, encoding="utf-8") as f:
            s = f.read()
        orig = s
        # Replace MotorLimitTypes.<NAME> -> MotorLimit.LIMIT_<NAME>
        s = re.sub(
            r"MotorLimitTypes\.(VOLTAGE_MIN|VOLTAGE_MAX|CURRENT_MAX_MA|TEMPERATURE_MAX_C|TORQUE_MAX_NM)",
            lambda m: "MotorLimit.LIMIT_" + m.group(1),
            s,
        )
        # Replace imports that explicitly import MotorLimitTypes
        s = re.sub(
            r"from\s+leropilot\.models\.hardware\s+import\s+([^\n]*?)\bMotorLimitTypes\b(,?\s*[^\n]*)?",
            lambda m: "from leropilot.models.hardware import "
            + (m.group(1) + (m.group(2) or "")).replace(",,", ",").replace(", ,", ","),
            s,
        )
        # If a line imports only MotorLimitTypes, replace it with MotorLimit
        s = re.sub(
            r"from\s+leropilot\.models\.hardware\s+import\s+MotorLimitTypes\b",
            "from leropilot.models.hardware import MotorLimit",
            s,
        )
        if s != orig:
            with open(fp, "w", encoding="utf-8") as f:
                f.write(s)
            changed.append(fp)
            print("Patched", fp)

print("\nTotal files changed:", len(changed))
print("Done.")
