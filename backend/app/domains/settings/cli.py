from __future__ import annotations

import argparse
import json

from app import create_app
from app.domains.settings.service import active_system_settings, legacy_settings, publish_settings


def main() -> None:
    parser = argparse.ArgumentParser(description="PathFy layered settings")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("show-effective", help="print the active non-secret settings")
    sub.add_parser("import-env", help="publish legacy non-secret environment overrides as a new revision")
    args = parser.parse_args(); app = create_app()
    with app.app_context():
        active = active_system_settings()
        if args.command == "show-effective":
            print(json.dumps(active, ensure_ascii=False, indent=2, default=str)); return
        values = legacy_settings()
        if active.get("settings") == values:
            print(json.dumps({"revision": active.get("revision"), "status": "unchanged"}, ensure_ascii=False, indent=2))
            return
        result = publish_settings(values, base_revision=active.get("revision"), user_id=None)
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__": main()
