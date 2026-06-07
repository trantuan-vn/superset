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
"""X.509 certificate verification helpers — Phase 3 PKI."""

from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cryptography import x509
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, padding, rsa
from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature
from cryptography.x509.oid import ExtendedKeyUsageOID, ExtensionOID

from app.auth.secrets import resolve_secret_ref
from app.config import get_settings


class PkiVerifyError(Exception):
    """Certificate or signature verification failure."""


@dataclass
class VerifiedCertificate:
    serial_number: str
    subject_dn: str
    issuer_dn: str
    not_before: datetime
    not_after: datetime
    common_name: str | None
    san_emails: list[str]


def _load_trusted_ca_pems(pki_config: dict[str, Any]) -> list[bytes]:
    """Load trusted CA certificate PEM bytes from tenant DB, secret ref, or env."""
    settings = get_settings()
    pem_sources: list[str] = []

    uploaded_ca = pki_config.get("ca_certificate_pem")
    if uploaded_ca:
        pem_sources.append(str(uploaded_ca))

    trust_ref = pki_config.get("trust_store_ref")
    if trust_ref:
        resolved = resolve_secret_ref(str(trust_ref))
        if resolved:
            resolved_path = Path(resolved)
            if resolved_path.is_file():
                pem_sources.append(resolved_path.read_text(encoding="utf-8"))
            else:
                pem_sources.append(resolved)

    if settings.pki_root_ca_path:
        path = Path(settings.pki_root_ca_path)
        if path.is_file():
            pem_sources.append(path.read_text(encoding="utf-8"))

    if not pem_sources:
        raise PkiVerifyError(
            "PKI root CA is not configured — upload root_ca.crt in tenant settings"
        )

    result: list[bytes] = []
    for source in pem_sources:
        result.append(source.encode("utf-8") if isinstance(source, str) else source)
    return result


def _parse_certificate(pem: str) -> x509.Certificate:
    try:
        return x509.load_pem_x509_certificate(pem.encode("utf-8"))
    except ValueError as exc:
        raise PkiVerifyError("Invalid certificate PEM") from exc


def _extract_common_name(subject: x509.Name) -> str | None:
    try:
        attrs = subject.get_attributes_for_oid(x509.oid.NameOID.COMMON_NAME)
        return str(attrs[0].value) if attrs else None
    except IndexError:
        return None


def _extract_san_emails(cert: x509.Certificate) -> list[str]:
    try:
        san_ext = cert.extensions.get_extension_for_oid(
            ExtensionOID.SUBJECT_ALTERNATIVE_NAME
        )
    except x509.ExtensionNotFound:
        return []
    emails: list[str] = []
    for name in san_ext.value:
        if isinstance(name, x509.RFC822Name):
            emails.append(str(name.value).lower())
    return emails


def _parse_pem_certificates(trusted_pems: list[bytes]) -> list[x509.Certificate]:
    """Parse one or more PEM-encoded X.509 certificates from byte blobs."""
    certs: list[x509.Certificate] = []
    for pem in trusted_pems:
        for block in pem.split(b"-----END CERTIFICATE-----"):
            block = block.strip()
            if not block:
                continue
            block = block + b"-----END CERTIFICATE-----"
            if b"-----BEGIN CERTIFICATE-----" not in block:
                block = b"-----BEGIN CERTIFICATE-----\n" + block
            try:
                certs.append(x509.load_pem_x509_certificate(block))
            except ValueError:
                continue
    return certs


def _verify_cert_signed_by(
    cert: x509.Certificate, issuer: x509.Certificate
) -> None:
    """Cryptographically verify that cert was signed by issuer."""
    sig_hash = cert.signature_hash_algorithm
    if sig_hash is None:
        raise PkiVerifyError("Certificate has no signature algorithm")

    public_key = issuer.public_key()
    try:
        if isinstance(public_key, rsa.RSAPublicKey):
            public_key.verify(
                cert.signature,
                cert.tbs_certificate_bytes,
                padding.PKCS1v15(),
                sig_hash,
            )
        elif isinstance(public_key, ec.EllipticCurvePublicKey):
            public_key.verify(
                cert.signature,
                cert.tbs_certificate_bytes,
                ec.ECDSA(sig_hash),
            )
        else:
            raise PkiVerifyError("Unsupported issuer key type")
    except InvalidSignature as exc:
        raise PkiVerifyError("Certificate is not signed by a trusted CA") from exc


def _verify_chain(cert: x509.Certificate, trusted_pems: list[bytes]) -> None:
    """Verify certificate chain to a trust anchor (supports root + intermediate bundle)."""
    store = _parse_pem_certificates(trusted_pems)
    if not store:
        raise PkiVerifyError("No valid CA certificates in trust store")

    by_subject = {ca.subject: ca for ca in store}
    current = cert
    for _ in range(10):
        signer = by_subject.get(current.issuer)
        if signer is None:
            raise PkiVerifyError("Certificate is not signed by a trusted CA")
        _verify_cert_signed_by(current, signer)
        if signer.subject == signer.issuer:
            return
        current = signer
    raise PkiVerifyError("Certificate chain too deep")


def _check_validity(cert: x509.Certificate, *, reject_expired: bool) -> None:
    now = datetime.now(timezone.utc)
    not_before = cert.not_valid_before_utc
    not_after = cert.not_valid_after_utc
    if now < not_before:
        raise PkiVerifyError("Certificate is not yet valid")
    if reject_expired and now > not_after:
        raise PkiVerifyError("Certificate has expired")


def _check_eku(cert: x509.Certificate, allowed_eku: list[str]) -> None:
    if not allowed_eku:
        return
    try:
        eku_ext = cert.extensions.get_extension_for_oid(
            ExtensionOID.EXTENDED_KEY_USAGE
        )
    except x509.ExtensionNotFound:
        raise PkiVerifyError("Certificate missing extended key usage") from None

    oid_map = {
        "clientAuth": ExtendedKeyUsageOID.CLIENT_AUTH,
        "emailProtection": ExtendedKeyUsageOID.EMAIL_PROTECTION,
    }
    allowed_oids = {oid_map[name] for name in allowed_eku if name in oid_map}
    cert_oids = set(eku_ext.value)
    if not cert_oids.intersection(allowed_oids):
        raise PkiVerifyError("Certificate extended key usage is not permitted")


def check_ocsp_revocation(
    serial_number: str,
    pki_config: dict[str, Any],
    *,
    revoked_serials: set[str] | None = None,
) -> None:
    """OCSP/CRL check — mock for dev; uses revoked_serials override in tests."""
    if not pki_config.get("reject_revoked", True):
        return

    ocsp_enabled = bool(pki_config.get("ocsp_enabled", False))
    if not ocsp_enabled:
        return

    revoked = revoked_serials or set()
    mock_revoked = pki_config.get("mock_revoked_serials") or []
    revoked.update(str(s) for s in mock_revoked)

    if serial_number in revoked:
        raise PkiVerifyError("Certificate has been revoked (OCSP)")


def _normalize_ecdsa_signature(
    signature: bytes, public_key: ec.EllipticCurvePublicKey
) -> bytes:
    """Convert IEEE P1363 (r||s) to ASN.1 DER when needed.

    Web Crypto ECDSA returns fixed-length raw coordinates; Python cryptography
    expects DER-encoded ECDSA signatures (same as OpenSSL).
    """
    if signature[:1] == b"\x30":
        return signature
    curve_size = (public_key.curve.key_size + 7) // 8
    if len(signature) != 2 * curve_size:
        return signature
    r = int.from_bytes(signature[:curve_size], "big")
    s = int.from_bytes(signature[curve_size:], "big")
    return encode_dss_signature(r, s)


def verify_signature(
    cert: x509.Certificate, nonce: str, signature_b64: str
) -> None:
    """Verify RSA/ECDSA signature over the challenge nonce."""
    try:
        signature = base64.b64decode(signature_b64)
    except Exception as exc:
        raise PkiVerifyError("Invalid signature encoding") from exc

    data = nonce.encode("utf-8")
    public_key = cert.public_key()

    try:
        if isinstance(public_key, rsa.RSAPublicKey):
            public_key.verify(
                signature,
                data,
                padding.PKCS1v15(),
                hashes.SHA256(),
            )
        elif isinstance(public_key, ec.EllipticCurvePublicKey):
            der_signature = _normalize_ecdsa_signature(signature, public_key)
            public_key.verify(der_signature, data, ec.ECDSA(hashes.SHA256()))
        else:
            raise PkiVerifyError("Unsupported certificate key type")
    except InvalidSignature as exc:
        raise PkiVerifyError("Signature verification failed") from exc


def parse_and_verify_certificate(
    certificate_pem: str,
    pki_config: dict[str, Any],
    *,
    revoked_serials: set[str] | None = None,
) -> VerifiedCertificate:
    """Validate an X.509 client certificate against tenant PKI policy."""
    cert = _parse_certificate(certificate_pem)
    trusted_pems = _load_trusted_ca_pems(pki_config)
    _verify_chain(cert, trusted_pems)
    _check_validity(cert, reject_expired=bool(pki_config.get("reject_expired", True)))

    allowed_eku = pki_config.get("allowed_eku") or ["clientAuth"]
    _check_eku(cert, list(allowed_eku))

    serial = format(cert.serial_number, "x")
    check_ocsp_revocation(serial, pki_config, revoked_serials=revoked_serials)

    return VerifiedCertificate(
        serial_number=serial,
        subject_dn=cert.subject.rfc4514_string(),
        issuer_dn=cert.issuer.rfc4514_string(),
        not_before=cert.not_valid_before_utc,
        not_after=cert.not_valid_after_utc,
        common_name=_extract_common_name(cert.subject),
        san_emails=_extract_san_emails(cert),
    )


def certificate_matches_user(
    verified: VerifiedCertificate, *, username: str, email: str
) -> bool:
    """Ensure the certificate identity matches the authenticated Portal user."""
    email_lower = email.strip().lower()
    username_lower = username.strip().lower()
    username_local = username_lower.split("@", 1)[0]

    if verified.common_name:
        cn = verified.common_name.strip().lower()
        if cn == username_local or cn == username_lower or cn == email_lower:
            return True

    for san in verified.san_emails:
        if san == email_lower:
            return True
        if san.split("@", 1)[0] == username_local:
            return True

    return False
