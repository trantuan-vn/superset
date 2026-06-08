# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.
"""Generate CSV/PDF export files from preview data."""

from __future__ import annotations

import csv
import io
from typing import Any


def _escape_pdf_text(value: str) -> str:
    return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def rows_to_csv(columns: list[str], rows: list[dict[str, Any]]) -> bytes:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({column: row.get(column, "") for column in columns})
    return buffer.getvalue().encode("utf-8-sig")


def rows_to_pdf(columns: list[str], rows: list[dict[str, Any]], *, title: str) -> bytes:
    """Minimal PDF table for approved export downloads."""
    lines: list[str] = [_escape_pdf_text(title), ""]
    header = " | ".join(columns)
    lines.append(_escape_pdf_text(header))
    lines.append(_escape_pdf_text("-" * min(len(header), 80)))
    for row in rows:
        line = " | ".join(str(row.get(column, "")) for column in columns)
        lines.append(_escape_pdf_text(line[:200]))

    content_stream = "BT\n/F1 10 Tf\n50 750 Td\n"
    for index, line in enumerate(lines):
        if index > 0:
            content_stream += "0 -14 Td\n"
        content_stream += f"({line}) Tj\n"
    content_stream += "ET"

    stream_bytes = content_stream.encode("latin-1", errors="replace")
    objects = [
        b"1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj\n",
        b"2 0 obj<< /Type /Pages /Kids [3 0 R] /Count 1 >>endobj\n",
        b"3 0 obj<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Contents 4 0 R /Resources<< /Font<< /F1 5 0 R >> >> >>endobj\n",
        f"4 0 obj<< /Length {len(stream_bytes)} >>stream\n".encode()
        + stream_bytes
        + b"\nendstream\nendobj\n",
        b"5 0 obj<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>endobj\n",
    ]
    pdf = b"%PDF-1.4\n"
    offsets = [0]
    for obj in objects:
        offsets.append(len(pdf))
        pdf += obj
    xref_start = len(pdf)
    pdf += f"xref\n0 {len(offsets)}\n".encode()
    pdf += b"0000000000 65535 f \n"
    for offset in offsets[1:]:
        pdf += f"{offset:010d} 00000 n \n".encode()
    pdf += b"trailer<< /Size 6 /Root 1 0 R >>\nstartxref\n"
    pdf += f"{xref_start}\n%%EOF".encode()
    return pdf


def export_bytes(
    *,
    columns: list[str],
    rows: list[dict[str, Any]],
    export_format: str,
    title: str,
) -> tuple[bytes, str, str]:
    """Return file bytes, media type, and filename extension."""
    normalized = export_format.lower()
    if normalized == "pdf":
        return rows_to_pdf(columns, rows, title=title), "application/pdf", "pdf"
    return rows_to_csv(columns, rows), "text/csv; charset=utf-8", "csv"
