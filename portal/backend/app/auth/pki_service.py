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
"""PKI challenge/verify orchestration — Phase 3."""

from __future__ import annotations

import json
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit.service import write_audit_log
from cryptography import x509

from app.auth.pki_verify import (
    PkiVerifyError,
    VerifiedCertificate,
    certificate_matches_user,
    parse_and_verify_certificate,
    verify_signature,
)
from app.auth.pki_policy import pki_required_for_tenant
from app.auth.service import AuthError
from app.auth.session import SessionData, get_redis_client, update_session
from app.models.tenant import TenantSettings
from app.models.user import User
from app.models.user_certificate import UserCertificate

PKI_CHALLENGE_PREFIX = "portal:pki_challenge:"
PKI_CHALLENGE_TTL = 300


@dataclass
class PkiChallengeResult:
    nonce: str
    expires_in_seconds: int


@dataclass
class PkiVerifyResult:
    cert_serial: str
    subject_dn: str


def _challenge_key(session_id: str) -> str:
    return f"{PKI_CHALLENGE_PREFIX}{session_id}"


def session_needs_pki(session: SessionData) -> bool:
    return session.pki_required and not session.pki_verified


def reconcile_session_pki_with_tenant(
    session: SessionData,
    session_id: str,
    settings: TenantSettings,
) -> SessionData:
    """Drop a stale PKI gate when the tenant has disabled digital signature."""
    if (
        not pki_required_for_tenant(settings)
        and session.pki_required
        and not session.pki_verified
    ):
        updated = update_session(
            session_id,
            pki_required=False,
            pki_verified=True,
        )
        return updated or session
    return session


def create_pki_challenge(session: SessionData) -> PkiChallengeResult:
    """Issue a one-time nonce for the client to sign."""
    if not session.pki_required:
        raise AuthError("PKI verification is not required", status_code=400)
    if session.pki_verified:
        raise AuthError("PKI verification already completed", status_code=400)

    nonce = secrets.token_urlsafe(32)
    payload = json.dumps({"nonce": nonce, "session_id": session.session_id})
    get_redis_client().setex(_challenge_key(session.session_id), PKI_CHALLENGE_TTL, payload)
    return PkiChallengeResult(nonce=nonce, expires_in_seconds=PKI_CHALLENGE_TTL)


def _consume_challenge(session_id: str) -> str:
    key = _challenge_key(session_id)
    client = get_redis_client()
    raw = client.get(key)
    if not raw:
        raise AuthError("Challenge expired or not found", status_code=400)
    client.delete(key)
    data = json.loads(raw)
    return str(data["nonce"])


def _upsert_user_certificate(
    db: Session,
    user: User,
    verified: VerifiedCertificate,
) -> UserCertificate:
    record = db.scalar(
        select(UserCertificate).where(
            UserCertificate.user_id == user.id,
            UserCertificate.serial_number == verified.serial_number,
        )
    )
    if record is None:
        record = UserCertificate(
            user_id=user.id,
            serial_number=verified.serial_number,
            subject_dn=verified.subject_dn,
            issuer_dn=verified.issuer_dn,
            not_before=verified.not_before,
            not_after=verified.not_after,
            is_active=True,
        )
        db.add(record)
    else:
        record.subject_dn = verified.subject_dn
        record.issuer_dn = verified.issuer_dn
        record.not_before = verified.not_before
        record.not_after = verified.not_after
        record.is_active = True
    return record


def verify_pki_login(
    db: Session,
    *,
    session: SessionData,
    user: User,
    settings: TenantSettings,
    certificate_pem: str,
    signature: str,
    ip_address: str | None = None,
) -> PkiVerifyResult:
    """Verify signed challenge and mark session PKI-complete."""
    if not session.pki_required:
        raise AuthError("PKI verification is not required", status_code=400)
    if session.pki_verified:
        raise AuthError("PKI verification already completed", status_code=400)

    pki_config = settings.pki_config or {}
    nonce = _consume_challenge(session.session_id)

    try:
        verified = parse_and_verify_certificate(certificate_pem, pki_config)
        cert = x509.load_pem_x509_certificate(certificate_pem.encode("utf-8"))
        verify_signature(cert, nonce, signature)
    except PkiVerifyError as exc:
        write_audit_log(
            db,
            tenant_id=user.tenant_id,
            action="AUTH_PKI_FAILED",
            entity_type="user",
            entity_id=str(user.id),
            actor_id=user.id,
            payload={"reason": str(exc)},
            ip_address=ip_address,
        )
        raise AuthError(str(exc), status_code=403) from exc

    if not certificate_matches_user(
        verified, username=user.username, email=user.email
    ):
        write_audit_log(
            db,
            tenant_id=user.tenant_id,
            action="AUTH_PKI_FAILED",
            entity_type="user",
            entity_id=str(user.id),
            actor_id=user.id,
            payload={"reason": "cert_user_mismatch", "serial": verified.serial_number},
            ip_address=ip_address,
        )
        raise AuthError(
            "Certificate does not match the authenticated user",
            status_code=403,
        )

    _upsert_user_certificate(db, user, verified)
    db.commit()

    updated = update_session(
        session.session_id,
        pki_verified=True,
        cert_serial=verified.serial_number,
    )
    if updated is None:
        raise AuthError("Session expired", status_code=401)

    write_audit_log(
        db,
        tenant_id=user.tenant_id,
        action="AUTH_PKI_SUCCESS",
        entity_type="user",
        entity_id=str(user.id),
        actor_id=user.id,
        payload={
            "serial": verified.serial_number,
            "subject_dn": verified.subject_dn,
        },
        ip_address=ip_address,
    )

    return PkiVerifyResult(
        cert_serial=verified.serial_number,
        subject_dn=verified.subject_dn,
    )
