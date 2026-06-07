#!/usr/bin/env python3
"""One-shot: create portal_provisioner Superset user + API key (Phase 5 local deploy)."""

from __future__ import annotations

from superset.app import create_app
from superset.extensions import db


def main() -> None:
    app = create_app()
    with app.app_context():
        sm = app.appbuilder.sm
        print("FAB_API_KEY_ENABLED:", app.config.get("FAB_API_KEY_ENABLED"))

        user = sm.find_user(username="portal_provisioner")
        if user is None:
            raise SystemExit(
                "portal_provisioner not found — run: "
                "superset fab create-user --username portal_provisioner "
                "--role Admin ..."
            )
        print("User portal_provisioner id:", user.id)

        result = sm.create_api_key(user, name="portal-phase5-deploy")
        db.session.commit()
        if not result:
            raise SystemExit("Failed to create API key")
        token = result.get("key") or result.get("token") or result.get("api_key")
        if not token:
            raise SystemExit(f"Unexpected create_api_key response: {result}")
        print(f"SUPERSET_SERVICE_API_KEY={token}")


if __name__ == "__main__":
    main()
