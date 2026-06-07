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
"""Per-tenant PKI root CA storage in tenant_settings.pki_config."""

from __future__ import annotations

import copy
from datetime import datetime, timezone
from typing import Any

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.x509.oid import ExtensionOID

from app.auth.pki_verify import PkiVerifyError, _parse_pem_certificates


def _validate_ca_certificate(cert: x509.Certificate) -> None:
    try:
        bc = cert.extensions.get_extension_for_oid(ExtensionOID.BASIC_CONSTRAINTS)
        if not bc.value.ca:
            raise PkiVerifyError("Certificate is not a CA (BasicConstraints CA=false)")
    except x509.ExtensionNotFound as exc:
        raise PkiVerifyError("Certificate missing BasicConstraints extension") from exc


def parse_ca_certificate_pem(pem: str) -> tuple[str, str, str, int]:
    """Validate PEM bundle and return (normalized_pem, anchor_subject_dn, fingerprint, count)."""
    text = pem.strip()
    if "-----BEGIN CERTIFICATE-----" not in text:
        raise PkiVerifyError("File must be a PEM-encoded X.509 certificate")

    certs = _parse_pem_certificates([text.encode("utf-8")])
    if not certs:
        raise PkiVerifyError("Invalid certificate PEM")

    for cert in certs:
        _validate_ca_certificate(cert)

    normalized = "".join(
        cert.public_bytes(serialization.Encoding.PEM).decode("utf-8") for cert in certs
    )
    anchor = next((cert for cert in certs if cert.subject == cert.issuer), certs[-1])
    fingerprint = anchor.fingerprint(hashes.SHA256()).hex()
    return normalized, anchor.subject.rfc4514_string(), fingerprint, len(certs)


def store_ca_in_pki_config(
    pki_config: dict[str, Any] | None, *, certificate_pem: str
) -> dict[str, Any]:
    """Merge uploaded CA PEM bundle into tenant pki_config."""
    normalized, subject_dn, fingerprint, count = parse_ca_certificate_pem(certificate_pem)
    merged = copy.deepcopy(pki_config or {})
    merged["ca_certificate_pem"] = normalized
    merged["ca_subject_dn"] = subject_dn
    merged["ca_fingerprint"] = fingerprint
    merged["ca_certificate_count"] = count
    merged["ca_uploaded_at"] = datetime.now(timezone.utc).isoformat()
    merged.pop("trust_store_ref", None)
    return merged


def remove_ca_from_pki_config(pki_config: dict[str, Any] | None) -> dict[str, Any]:
    merged = copy.deepcopy(pki_config or {})
    for key in (
        "ca_certificate_pem",
        "ca_subject_dn",
        "ca_fingerprint",
        "ca_certificate_count",
        "ca_uploaded_at",
    ):
        merged.pop(key, None)
    return merged


def mask_pki_config_for_api(pki_config: dict[str, Any] | None) -> dict[str, Any] | None:
    """Hide raw PEM from API responses."""
    if not pki_config:
        return None
    masked = copy.deepcopy(pki_config)
    if masked.get("ca_certificate_pem"):
        masked["ca_certificate_pem"] = None
        masked["ca_certificate_uploaded"] = True
    else:
        masked["ca_certificate_uploaded"] = False
    return masked


def pki_has_trusted_ca(pki_config: dict[str, Any] | None) -> bool:
    if not pki_config:
        return False
    if pki_config.get("ca_certificate_pem"):
        return True
    return bool(pki_config.get("trust_store_ref"))
