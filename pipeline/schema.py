"""Print the analytical schema the scripts should use (scripts\\_common.ps1 Resolve-VoltProofSchema):
VOLTPROOF_SCHEMA if set; else VOLTPROOF (real data) if built; else VOLTPROOF_DEMO (synthetic) if built."""

import sys

from pipeline.db import resolve_schema

if __name__ == "__main__":
    print(resolve_schema())
    sys.exit(0)
