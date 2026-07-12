#!/usr/bin/env python3
"""Print the registered Flask routes as stable JSON for contract comparison."""

from __future__ import annotations

import json

from app import create_app


def main() -> None:
    app = create_app()
    rows = []
    for rule in sorted(app.url_map.iter_rules(), key=lambda item: (item.rule, item.endpoint)):
        if rule.endpoint == "static":
            continue
        rows.append(
            {
                "path": rule.rule,
                "methods": sorted(rule.methods - {"HEAD", "OPTIONS"}),
                "endpoint": rule.endpoint,
            }
        )
    print(json.dumps(rows, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
