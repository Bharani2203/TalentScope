import hashlib
import re
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from firebase_admin import firestore

from app.core.firebase import get_firestore_client
from app.models.auth import AuthenticatedUser
from app.models.company import CompanyConnectionReviewResponse, CompanyInvitationCreate


def create_invitation(user: AuthenticatedUser, request: CompanyInvitationCreate) -> dict:
    email = request.email.strip().casefold()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise HTTPException(status_code=422, detail="Enter a valid employee email address.")
    client = get_firestore_client()
    admin = client.collection("users").document(user.uid).get().to_dict() or {}
    company_id = admin.get("company_id")
    company_ref = client.collection("companies").document(company_id or "__missing__")
    company = company_ref.get().to_dict() or {}
    if admin.get("user_type") != "company" or not company_id or company.get("owner_uid") != user.uid:
        raise HTTPException(status_code=403, detail="Only the verified company owner can invite employees.")
    connected = list(client.collection("users").where("email", "==", email).limit(10).stream())
    if any((row.to_dict() or {}).get("company_id") == company_id for row in connected):
        raise HTTPException(status_code=409, detail="This employee is already connected to your company.")
    # Use the single-field company query and apply the remaining checks locally;
    # this does not require a new composite Firestore index for invitation writes.
    existing = client.collection("company_invitations").where("company_id", "==", company_id).stream()
    now = datetime.now(timezone.utc)
    for row in existing:
        invitation = row.to_dict() or {}
        if invitation.get("intended_email") != email or invitation.get("status") != "invited":
            continue
        expiry = invitation.get("expires_at")
        if isinstance(expiry, datetime) and expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=timezone.utc)
        if isinstance(expiry, datetime) and expiry > now:
            raise HTTPException(status_code=409, detail="An active invitation already exists for this email.")
    token = secrets.token_urlsafe(32)
    expires_at = now + timedelta(days=7)
    ref = client.collection("company_invitations").document()
    ref.set({
        "invitation_id": ref.id,
        "token_hash": hashlib.sha256(token.encode()).hexdigest(),
        "company_id": company_id,
        "created_by": user.uid,
        "intended_email": email,
        "role": request.role,
        "team": request.team,
        "status": "invited",
        "expires_at": expires_at,
        "created_at": firestore.SERVER_TIMESTAMP,
        "accepted_by": None,
        "accepted_at": None,
        "declined_at": None,
    })
    return {"invitation_id": ref.id, "token": token, "expires_at": expires_at, "status": "invited"}


def list_company_invitations(user: AuthenticatedUser) -> list[dict]:
    """List safe invitation metadata for the authenticated company owner."""
    client = get_firestore_client()
    admin = client.collection("users").document(user.uid).get().to_dict() or {}
    company_id = admin.get("company_id")
    company = client.collection("companies").document(company_id or "__missing__").get().to_dict() or {}
    if admin.get("user_type") != "company" or not company_id or company.get("owner_uid") != user.uid:
        raise HTTPException(status_code=403, detail="Only the verified company owner can list invitations.")

    now = datetime.now(timezone.utc)
    results = []
    snapshots = client.collection("company_invitations").where(
        "company_id", "==", company_id,
    ).limit(100).stream()
    for snapshot in snapshots:
        record = snapshot.to_dict() or {}
        if record.get("company_id") != company_id:
            continue
        expiry = record.get("expires_at")
        comparable_expiry = expiry
        if isinstance(expiry, datetime) and expiry.tzinfo is None:
            comparable_expiry = expiry.replace(tzinfo=timezone.utc)
        status_value = record.get("status")
        results.append({
            "invitation_id": record.get("invitation_id") or snapshot.id,
            "company_id": company_id,
            "intended_email": record.get("intended_email"),
            "role": record.get("role"),
            "team": record.get("team"),
            "status": status_value if status_value in {"invited", "accepted", "declined"} else None,
            "expired": (
                status_value == "invited" and isinstance(comparable_expiry, datetime)
                and comparable_expiry <= now
            ) if isinstance(expiry, datetime) else None,
            "created_at": record.get("created_at"),
            "expires_at": expiry,
            "accepted_at": record.get("accepted_at"),
            "declined_at": record.get("declined_at"),
        })
    def created_sort_key(item: dict):
        value = item["created_at"]
        if not isinstance(value, datetime):
            return 0.0
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.timestamp()

    results.sort(key=created_sort_key, reverse=True)
    return results


def change_invitation(user: AuthenticatedUser, token: str, *, accept: bool) -> dict:
    if not user.email_verified or not user.email:
        raise HTTPException(status_code=403, detail="A verified email is required to use this invitation.")
    client = get_firestore_client()
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    matches = list(client.collection("company_invitations").where("token_hash", "==", token_hash).limit(1).stream())
    if not matches:
        raise HTTPException(status_code=404, detail="Invitation is invalid or expired.")
    ref = client.collection("company_invitations").document(matches[0].id)
    user_ref = client.collection("users").document(user.uid)
    transaction = client.transaction()

    @firestore.transactional
    def commit(tx):
        snapshot = ref.get(transaction=tx)
        invitation = snapshot.to_dict() or {}
        expiry = invitation.get("expires_at")
        if not isinstance(expiry, datetime) or expiry <= datetime.now(timezone.utc):
            raise HTTPException(status_code=410, detail="Invitation is invalid or expired.")
        if invitation.get("status") != "invited" or invitation.get("intended_email") != user.email.casefold():
            raise HTTPException(status_code=409, detail="Invitation is already used or belongs to another email.")
        status_value = "accepted" if accept else "declined"
        tx.update(ref, {
            "status": status_value,
            "accepted_by": user.uid if accept else None,
            "accepted_at": firestore.SERVER_TIMESTAMP if accept else None,
            "declined_at": firestore.SERVER_TIMESTAMP if not accept else None,
        })
        if accept:
            company_id = invitation["company_id"]
            employee_snapshot = user_ref.get(transaction=tx)
            employee = employee_snapshot.to_dict() or {}
            if employee.get("user_type") != "employee":
                raise HTTPException(status_code=403, detail="Only Employee profiles can accept company invitations.")
            existing_company_id = employee.get("company_id")
            if existing_company_id and existing_company_id != company_id:
                raise HTTPException(status_code=409, detail="This employee is already connected to another company.")
            member_ref = client.collection("companies").document(company_id).collection("members").document(user.uid)
            tx.update(user_ref, {"company_id": company_id,
                                 "company_connection": {"status": "connected", "company_id": company_id}})
            tx.set(member_ref, {
                "uid": user.uid, "email": user.email.casefold(), "status": "connected",
                "role": invitation.get("role"), "team": invitation.get("team"),
                "joined_at": firestore.SERVER_TIMESTAMP,
            }, merge=True)
        return {"status": status_value, "company_id": invitation["company_id"]}

    return commit(transaction)


def request_company_connection(user: AuthenticatedUser, company_id: str) -> dict:
    client = get_firestore_client()
    employee_ref = client.collection("users").document(user.uid)
    company_ref = client.collection("companies").document(company_id)
    request_ref = company_ref.collection("connection_requests").document(user.uid)
    transaction = client.transaction()

    @firestore.transactional
    def commit(tx):
        employee = employee_ref.get(transaction=tx).to_dict() or {}
        company = company_ref.get(transaction=tx).to_dict() or {}
        existing = request_ref.get(transaction=tx).to_dict() or {}
        if employee.get("user_type") != "employee" or company.get("status") != "active":
            raise HTTPException(status_code=403, detail="Employee or company profile is unavailable.")
        linked_company = employee.get("company_id")
        connection = employee.get("company_connection") or {}
        if connection.get("status") == "connected" and linked_company == company_id:
            return {"status": "connected", "company_id": company_id, "request_status": "approved"}
        if linked_company and linked_company != company_id:
            raise HTTPException(status_code=409, detail="This employee is already connected to another company.")
        if existing.get("status") == "pending":
            return {"status": "requesting", "company_id": company_id, "request_status": "pending"}
        now = datetime.now(timezone.utc)
        tx.set(request_ref, {
            "employee_uid": user.uid, "email": user.email, "company_id": company_id,
            "status": "pending", "created_at": now, "reviewed_at": None, "reviewed_by": None,
        }, merge=True)
        tx.set(employee_ref, {
            "company_connection": {"status": "requesting", "company_id": company_id},
        }, merge=True)
        return {"status": "requesting", "company_id": company_id, "request_status": "pending"}

    return commit(transaction)


def review_company_connection(
    user: AuthenticatedUser,
    employee_uid: str,
    decision: str,
) -> CompanyConnectionReviewResponse:
    if user.uid == employee_uid:
        raise HTTPException(status_code=403, detail="Employees cannot review their own company connection request.")
    if decision not in {"approve", "decline"}:
        raise HTTPException(status_code=422, detail={"error_code": "invalid_filter"})
    client = get_firestore_client()
    admin_ref = client.collection("users").document(user.uid)
    admin = admin_ref.get().to_dict() or {}
    company_id = admin.get("company_id")
    if admin.get("user_type") != "company" or not company_id:
        raise HTTPException(status_code=403, detail="A company admin profile is required.")
    company_ref = client.collection("companies").document(company_id)
    company = company_ref.get().to_dict() or {}
    if company.get("owner_uid") != user.uid:
        raise HTTPException(status_code=403, detail="Only an authorized admin of this company can review requests.")
    request_ref = company_ref.collection("connection_requests").document(employee_uid)
    employee_ref = client.collection("users").document(employee_uid)
    transaction = client.transaction()

    @firestore.transactional
    def commit(tx):
        request = request_ref.get(transaction=tx).to_dict() or {}
        employee = employee_ref.get(transaction=tx).to_dict() or {}
        if request.get("company_id") != company_id or request.get("employee_uid") != employee_uid:
            raise HTTPException(status_code=404, detail="Company connection request was not found.")
        if employee.get("user_type") != "employee":
            raise HTTPException(status_code=409, detail="The requested account is not an Employee profile.")
        if request.get("status") in {"approved", "declined"}:
            if request.get("reviewed_by") == user.uid and request.get("status") == ("approved" if decision == "approve" else "declined"):
                reviewed_at = request.get("reviewed_at") or datetime.now(timezone.utc)
                return CompanyConnectionReviewResponse(employee_uid=employee_uid, company_id=company_id,
                    status=request["status"], reviewed_by=user.uid, reviewed_at=reviewed_at)
            raise HTTPException(status_code=409, detail="Company connection request has already been reviewed.")
        if request.get("status") != "pending":
            raise HTTPException(status_code=409, detail="Company connection request is not pending.")
        linked_company = employee.get("company_id")
        if decision == "approve" and linked_company and linked_company != company_id:
            raise HTTPException(status_code=409, detail="The employee is already connected to another company.")
        reviewed_at = datetime.now(timezone.utc)
        status_value = "approved" if decision == "approve" else "declined"
        tx.update(request_ref, {"status": status_value, "reviewed_at": reviewed_at, "reviewed_by": user.uid})
        if decision == "approve":
            member_ref = company_ref.collection("members").document(employee_uid)
            tx.set(employee_ref, {"company_id": company_id,
                "company_connection": {"status": "connected", "company_id": company_id}}, merge=True)
            tx.set(member_ref, {"uid": employee_uid, "email": employee.get("email"),
                "status": "connected", "joined_at": reviewed_at}, merge=True)
        else:
            current = employee.get("company_connection") or {}
            if current.get("status") == "requesting" and current.get("company_id") == company_id:
                tx.set(employee_ref, {"company_id": None,
                    "company_connection": {"status": "independent", "company_id": None}}, merge=True)
        return CompanyConnectionReviewResponse(employee_uid=employee_uid, company_id=company_id,
            status=status_value, reviewed_by=user.uid, reviewed_at=reviewed_at)

    return commit(transaction)


def set_independent(user: AuthenticatedUser) -> dict:
    ref = get_firestore_client().collection("users").document(user.uid)
    stored = ref.get().to_dict() or {}
    if stored.get("user_type") != "employee":
        raise HTTPException(status_code=403, detail="This connection state is for Employee profiles.")
    value = {"status": "independent", "company_id": None}
    ref.update({"company_connection": value, "company_id": None})
    return value


def search_companies(user: AuthenticatedUser, query: str) -> list[dict]:
    """Return a small authenticated directory of active companies for employee requests."""
    client = get_firestore_client()
    profile = client.collection("users").document(user.uid).get().to_dict() or {}
    if profile.get("user_type") != "employee":
        raise HTTPException(status_code=403, detail="Only Employee profiles can search companies.")
    needle = query.strip().casefold()
    if len(needle) < 2:
        return []
    companies = client.collection("companies").where("status", "==", "active").limit(100).stream()
    matches = []
    for snapshot in companies:
        record = snapshot.to_dict() or {}
        name = record.get("company_name")
        if isinstance(name, str) and needle in name.casefold():
            matches.append({
                "company_id": record.get("company_id") or snapshot.id,
                "company_name": name,
                "industry": record.get("industry"),
                "hq_region": record.get("hq_region") if isinstance(record.get("hq_region"), dict) else None,
            })
    return matches[:20]


def list_pending_connection_requests(user: AuthenticatedUser) -> list[dict]:
    client = get_firestore_client()
    admin = client.collection("users").document(user.uid).get().to_dict() or {}
    company_id = admin.get("company_id")
    company_ref = client.collection("companies").document(company_id or "__missing__")
    company = company_ref.get().to_dict() or {}
    if admin.get("user_type") != "company" or not company_id or company.get("owner_uid") != user.uid:
        raise HTTPException(status_code=403, detail="Only the verified company owner can review requests.")
    rows = company_ref.collection("connection_requests").where("status", "==", "pending").limit(100).stream()
    return [
        {
            "employee_uid": row.get("employee_uid"),
            "company_id": company_id,
            "email": row.get("email"),
            "status": "pending",
            "created_at": row.get("created_at"),
        }
        for snapshot in rows
        if (row := snapshot.to_dict() or {}).get("employee_uid")
    ]
