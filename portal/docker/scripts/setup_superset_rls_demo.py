#!/usr/bin/env python3
"""Create demo dataset with tenant_id/dept_code for Portal Phase 6 RLS testing.

Run inside Superset app container after examples DB is available::

    python /app/portal/docker/scripts/setup_superset_rls_demo.py

Or from repo root with local Superset::

    PYTHONPATH=. python portal/docker/scripts/setup_superset_rls_demo.py
"""

from __future__ import annotations

import os
import sys

TABLE_NAME = "portal_export_data"
SCHEMA = "public"


def main() -> None:
    from superset.app import create_app

    app = create_app()
    with app.app_context():
        from superset.connectors.sqla.models import SqlaTable, TableColumn
        from superset.extensions import db
        from superset.models.core import Database
        database = (
            db.session.query(Database)
            .filter(Database.database_name == "examples")
            .one_or_none()
        )
        if database is None:
            database = db.session.query(Database).first()
        if database is None:
            raise SystemExit("No Superset database connection found")

        with database.get_sqla_engine() as engine:
            with engine.begin() as conn:
                conn.exec_driver_sql(f"DROP TABLE IF EXISTS {SCHEMA}.{TABLE_NAME}")
                conn.exec_driver_sql(
                    f"""
                    CREATE TABLE {SCHEMA}.{TABLE_NAME} (
                        id SERIAL PRIMARY KEY,
                        tenant_id VARCHAR(128) NOT NULL,
                        dept_code VARCHAR(64) NOT NULL,
                        metric_name VARCHAR(128) NOT NULL,
                        metric_value NUMERIC(12, 2) NOT NULL
                    )
                    """
                )
                conn.exec_driver_sql(
                    f"""
                    INSERT INTO {SCHEMA}.{TABLE_NAME}
                        (tenant_id, dept_code, metric_name, metric_value)
                    VALUES
                        ('demo-corp', 'KETOAN', 'revenue', 1000.00),
                        ('demo-corp', 'KETOAN', 'expense', 400.00),
                        ('demo-corp', 'CNTT', 'revenue', 2500.00),
                        ('demo-corp', 'CNTT', 'expense', 900.00),
                        ('other-corp', 'KETOAN', 'revenue', 9999.00)
                    """
                )

        dataset = (
            db.session.query(SqlaTable)
            .filter(
                SqlaTable.table_name == TABLE_NAME,
                SqlaTable.schema == SCHEMA,
            )
            .one_or_none()
        )
        if dataset is None:
            dataset = SqlaTable(
                table_name=TABLE_NAME,
                schema=SCHEMA,
                database=database,
            )
            db.session.add(dataset)
            db.session.flush()

        column_specs = [
            ("id", "INTEGER", True),
            ("tenant_id", "VARCHAR(128)", True),
            ("dept_code", "VARCHAR(64)", True),
            ("metric_name", "VARCHAR(128)", True),
            ("metric_value", "NUMERIC", True),
        ]
        existing = {col.column_name for col in dataset.columns}
        for name, col_type, groupby in column_specs:
            if name in existing:
                continue
            db.session.add(
                TableColumn(
                    column_name=name,
                    type=col_type,
                    table=dataset,
                    is_dttm=False,
                    filterable=True,
                    groupby=groupby,
                )
            )

        db.session.commit()
        print(f"Dataset '{TABLE_NAME}' ready (id={dataset.id})")
        print("Columns: tenant_id, dept_code — required for Portal RLS macros")


if __name__ == "__main__":
    repo_root = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..")
    )
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    main()
