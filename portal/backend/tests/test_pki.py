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
"""PKI authentication tests — Phase 3."""

import base64
import json
import uuid
from collections.abc import Generator
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID
from fastapi.testclient import TestClient

from app.auth.dependencies import get_current_user, get_session_data, get_session_id
from app.auth.pki_verify import (
    PkiVerifyError,
    certificate_matches_user,
    check_ocsp_revocation,
    parse_and_verify_certificate,
    verify_signature,
)
from app.auth.session import SessionData
from app.main import app
from app.models.tenant import Tenant, TenantSettings, TenantStatus
from app.models.user import SystemRole, User, UserStatus
from app.seed import DEMO_TENANT_ID

client = TestClient(app)


def _generate_test_ca_and_cert(
    *,
    common_name: str = "cntt.cv",
    expired: bool = False,
) -> tuple[str, str, rsa.RSAPrivateKey, str]:
    """Return (ca_pem, cert_pem, private_key, serial_hex)."""
    ca_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    ca_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Test CA")])
    now = datetime.now(timezone.utc)
    ca_cert = (
        x509.CertificateBuilder()
        .subject_name(ca_name)
        .issuer_name(ca_name)
        .public_key(ca_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=365))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(ca_key, hashes.SHA256())
    )
    ca_pem = ca_cert.public_bytes(serialization.Encoding.PEM).decode()

    user_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name)])
    not_before = now - timedelta(days=1)
    not_after = now - timedelta(hours=1) if expired else now + timedelta(days=30)
    cert_builder = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(ca_name)
        .public_key(user_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(not_before)
        .not_valid_after(not_after)
        .add_extension(
            x509.ExtendedKeyUsage([ExtendedKeyUsageOID.CLIENT_AUTH]),
            critical=False,
        )
    )
    user_cert = cert_builder.sign(ca_key, hashes.SHA256())
    cert_pem = user_cert.public_bytes(serialization.Encoding.PEM).decode()
    serial_hex = format(user_cert.serial_number, "x")
    return ca_pem, cert_pem, user_key, serial_hex


def _sign_nonce(private_key: rsa.RSAPrivateKey, nonce: str) -> str:
    from cryptography.hazmat.primitives.asymmetric import padding

    signature = private_key.sign(
        nonce.encode("utf-8"),
        padding.PKCS1v15(),
        hashes.SHA256(),
    )
    return base64.b64encode(signature).decode()


def _demo_user() -> User:
    return User(
        id=uuid.uuid4(),
        tenant_id=DEMO_TENANT_ID,
        username="cntt.cv@demo-corp.local",
        email="cntt.cv@demo-corp.local",
        display_name="CNTT CV",
        password_hash="hashed",
        system_role=SystemRole.CNTT_CHUYENVIEN,
        status=UserStatus.ACTIVE,
    )


def _demo_tenant() -> Tenant:
    return Tenant(
        id=DEMO_TENANT_ID,
        slug="demo-corp",
        name="Demo Corporation",
        status=TenantStatus.ACTIVE,
    )


def _pki_settings(ca_pem: str) -> TenantSettings:
    return TenantSettings(
        tenant_id=DEMO_TENANT_ID,
        digital_signature_enabled=True,
        pki_config={
            "ca_provider": "test",
            "ca_certificate_pem": ca_pem,
            "ocsp_enabled": False,
            "reject_expired": True,
            "reject_revoked": True,
            "allowed_eku": ["clientAuth"],
        },
    )


@pytest.fixture
def fake_redis() -> Generator[MagicMock, None, None]:
    store: dict[str, str] = {}
    mock = MagicMock()

    def _get(key: str) -> str | None:
        return store.get(key)

    def _setex(key: str, ttl: int, value: str) -> None:
        store[key] = value

    def _delete(key: str) -> None:
        store.pop(key, None)

    mock.get.side_effect = _get
    mock.setex.side_effect = _setex
    mock.delete.side_effect = _delete
    with patch("app.auth.session.get_redis_client", return_value=mock):
        with patch("app.auth.pki_service.get_redis_client", return_value=mock):
            yield mock


def test_load_trusted_ca_from_uploaded_pem() -> None:
    from app.auth.pki_verify import _load_trusted_ca_pems

    ca_pem, _, _, _ = _generate_test_ca_and_cert()
    loaded = _load_trusted_ca_pems({"ca_certificate_pem": ca_pem})
    assert loaded == [ca_pem.encode()]


def test_ecdsa_p1363_signature_verified() -> None:
    """Web Crypto ECDSA uses IEEE P1363 (r||s); backend must accept it."""
    from cryptography.hazmat.primitives.asymmetric import ec, utils

    key = ec.generate_private_key(ec.SECP256R1())
    nonce = "portal-pki-challenge-nonce"
    der_sig = key.sign(nonce.encode("utf-8"), ec.ECDSA(hashes.SHA256()))
    r, s = utils.decode_dss_signature(der_sig)
    curve_size = 32
    p1363 = r.to_bytes(curve_size, "big") + s.to_bytes(curve_size, "big")

    now = datetime.now(timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(
            x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "admin")])
        )
        .issuer_name(
            x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Test CA")])
        )
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=30))
        .sign(key, hashes.SHA256())
    )
    verify_signature(cert, nonce, base64.b64encode(p1363).decode())


def test_intermediate_chain_with_root_and_intermediate_bundle() -> None:
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import NameOID

    now = datetime.now(timezone.utc)
    root_key = ec.generate_private_key(ec.SECP256R1())
    root_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Test Root")])
    root_cert = (
        x509.CertificateBuilder()
        .subject_name(root_name)
        .issuer_name(root_name)
        .public_key(root_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=365))
        .add_extension(x509.BasicConstraints(ca=True, path_length=1), critical=True)
        .sign(root_key, hashes.SHA256())
    )

    inter_key = ec.generate_private_key(ec.SECP256R1())
    inter_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Test Intermediate")])
    inter_cert = (
        x509.CertificateBuilder()
        .subject_name(inter_name)
        .issuer_name(root_name)
        .public_key(inter_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=180))
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .sign(root_key, hashes.SHA256())
    )

    leaf_key = ec.generate_private_key(ec.SECP256R1())
    leaf_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "admin")])
    leaf_cert = (
        x509.CertificateBuilder()
        .subject_name(leaf_name)
        .issuer_name(inter_name)
        .public_key(leaf_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=30))
        .add_extension(
            x509.ExtendedKeyUsage([ExtendedKeyUsageOID.CLIENT_AUTH]),
            critical=False,
        )
        .sign(inter_key, hashes.SHA256())
    )

    bundle_pem = (
        inter_cert.public_bytes(serialization.Encoding.PEM).decode()
        + root_cert.public_bytes(serialization.Encoding.PEM).decode()
    )
    leaf_pem = leaf_cert.public_bytes(serialization.Encoding.PEM).decode()
    verified = parse_and_verify_certificate(
        leaf_pem,
        {
            "ca_certificate_pem": bundle_pem,
            "allowed_eku": ["clientAuth"],
            "reject_expired": True,
        },
    )
    assert verified.common_name == "admin"


def test_certificate_matches_user_cn() -> None:
    ca_pem, cert_pem, _, _ = _generate_test_ca_and_cert(common_name="cntt.cv")
    verified = parse_and_verify_certificate(
        cert_pem,
        {
            "ca_certificate_pem": ca_pem,
            "allowed_eku": ["clientAuth"],
            "reject_expired": True,
        },
    )
    assert certificate_matches_user(
        verified,
        username="cntt.cv@demo-corp.local",
        email="cntt.cv@demo-corp.local",
    )


def test_expired_certificate_rejected() -> None:
    ca_pem, cert_pem, _, _ = _generate_test_ca_and_cert(expired=True)
    with patch(
        "app.auth.pki_verify._load_trusted_ca_pems",
        return_value=[ca_pem.encode()],
    ):
        with pytest.raises(PkiVerifyError, match="expired"):
            parse_and_verify_certificate(
                cert_pem,
                {"allowed_eku": ["clientAuth"], "reject_expired": True},
            )


def test_ocsp_revoked_serial_rejected() -> None:
    with pytest.raises(PkiVerifyError, match="revoked"):
        check_ocsp_revocation(
            "abc123",
            {"ocsp_enabled": True, "reject_revoked": True},
            revoked_serials={"abc123"},
        )


def test_pki_challenge_requires_pending_session(fake_redis: MagicMock) -> None:
    session = SessionData(
        session_id="sess-1",
        user_id=str(uuid.uuid4()),
        tenant_id=str(DEMO_TENANT_ID),
        created_at="2026-01-01T00:00:00+00:00",
        expires_at="2026-01-02T00:00:00+00:00",
        pki_required=True,
        pki_verified=False,
    )
    fake_redis.setex(
        "portal:session:sess-1",
        3600,
        json.dumps(
            {
                "session_id": "sess-1",
                "user_id": session.user_id,
                "tenant_id": session.tenant_id,
                "created_at": session.created_at,
                "expires_at": session.expires_at,
                "pki_required": True,
                "pki_verified": False,
            }
        ),
    )

    app.dependency_overrides[get_session_id] = lambda: "sess-1"
    app.dependency_overrides[get_session_data] = lambda: session

    try:
        response = client.post("/auth/pki/challenge")
        assert response.status_code == 200
        payload = response.json()
        assert "nonce" in payload
        assert payload["expires_in_seconds"] == 300
    finally:
        app.dependency_overrides.clear()


def test_pki_verify_service_success(fake_redis: MagicMock) -> None:
    from app.auth.pki_service import create_pki_challenge, verify_pki_login

    ca_pem, cert_pem, user_key, serial_hex = _generate_test_ca_and_cert()
    user = _demo_user()
    tenant = _demo_tenant()
    settings = _pki_settings(ca_pem)
    tenant.settings = settings
    user.tenant = tenant

    session = SessionData(
        session_id="sess-pki",
        user_id=str(user.id),
        tenant_id=str(DEMO_TENANT_ID),
        created_at="2026-01-01T00:00:00+00:00",
        expires_at="2026-01-02T00:00:00+00:00",
        pki_required=True,
        pki_verified=False,
    )

    fake_redis.setex(
        "portal:session:sess-pki",
        3600,
        json.dumps(
            {
                "session_id": "sess-pki",
                "user_id": str(user.id),
                "tenant_id": str(DEMO_TENANT_ID),
                "created_at": session.created_at,
                "expires_at": session.expires_at,
                "pki_required": True,
                "pki_verified": False,
            }
        ),
    )

    challenge = create_pki_challenge(session)
    signature = _sign_nonce(user_key, challenge.nonce)

    db = MagicMock()
    db.scalar.return_value = None

    with patch(
        "app.auth.pki_verify._load_trusted_ca_pems",
        return_value=[ca_pem.encode()],
    ):
        result = verify_pki_login(
            db,
            session=session,
            user=user,
            settings=settings,
            certificate_pem=cert_pem,
            signature=signature,
        )

    assert result.cert_serial == serial_hex
    updated_raw = fake_redis.get("portal:session:sess-pki")
    assert updated_raw is not None
    updated = json.loads(updated_raw)
    assert updated["pki_verified"] is True
    assert updated["cert_serial"] == serial_hex
