#!/usr/bin/env python3
"""Validate .coderabbit.yaml against the CodeRabbit schema and assert quiet settings."""
import json
import sys
import urllib.request

import jsonschema
import yaml

SCHEMA_URL = "https://coderabbit.ai/integrations/schema.v2.json"
QUIET = {
    ("reviews", "auto_review", "enabled"): False,
    ("reviews", "high_level_summary"): False,
    ("reviews", "review_status"): False,
    ("reviews", "poem"): False,
    ("chat", "auto_reply"): False,
}


def main() -> int:
    with open(".coderabbit.yaml", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    with urllib.request.urlopen(SCHEMA_URL, timeout=30) as r:
        schema = json.load(r)
    errors = [f"schema: {'/'.join(map(str, e.path))}: {e.message}"
              for e in jsonschema.Draft7Validator(schema).iter_errors(config)]
    for path, want in QUIET.items():
        node = config
        for key in path:
            node = node.get(key) if isinstance(node, dict) else None
        if node is not want:
            errors.append(f"quiet: {'.'.join(path)} must be {want}, got {node!r}")
    for e in errors:
        print(f"::error file=.coderabbit.yaml::{e}")
    print("OK" if not errors else f"{len(errors)} error(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
