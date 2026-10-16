"""Helper script to mint real Firebase ID tokens and custom tokens for browser integration testing.

Outputs tokens as JSON to an output file specified in arguments.
Does not print token contents directly to console.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path

from dotenv import load_dotenv
import os

backend_dir = Path(__file__).resolve().parent.parent
load_dotenv(backend_dir / ".env")
if os.environ.get("GOOGLE_APPLICATION_CREDENTIALS") and not Path(os.environ["GOOGLE_APPLICATION_CREDENTIALS"]).is_absolute():
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str((backend_dir / os.environ["GOOGLE_APPLICATION_CREDENTIALS"]).resolve())

sys.path.insert(0, str(backend_dir))

from app.core.firebase import get_firebase_app, get_firestore_client
from firebase_admin import auth


def ensure_user(uid: str, email: str, claims: dict, profile: dict | None = None) -> None:
    app = get_firebase_app()
    try:
        auth.update_user(uid, email=email, email_verified=True, app=app)
    except auth.UserNotFoundError:
        auth.create_user(uid=uid, email=email, email_verified=True, app=app)
    auth.set_custom_user_claims(uid, claims, app=app)

    db = get_firestore_client()
    doc_ref = db.collection("users").document(uid)
    doc_data = {
        "uid": uid,
        "email": email,
        "email_verified": True,
        "onboarding_completed": True,
        "user_type": claims.get("user_type"),
        "created_at": "2026-01-01T00:00:00Z",
    }
    if profile:
        doc_data.update(profile)
    doc_ref.set(doc_data, merge=True)


def mint_tokens_for_user(uid: str, email: str, claims: dict, profile: dict | None = None) -> dict:
    ensure_user(uid, email, claims, profile)
    app = get_firebase_app()
    custom_token = auth.create_custom_token(uid, claims, app=app).decode("utf-8")
    api_key = "AIzaSyD5h3VUZkFevzyFfh9DO6TBK8nfTkCoQqA"
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithCustomToken?key={api_key}"
    req = urllib.request.Request(
        url,
        data=json.dumps({"token": custom_token, "returnSecureToken": True}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    resp = urllib.request.urlopen(req)
    data = json.loads(resp.read().decode("utf-8"))
    return {
        "uid": uid,
        "email": email,
        "custom_token": custom_token,
        "id_token": data["idToken"],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=str, required=True, help="Path to write tokens JSON")
    args = parser.parse_args()

    tokens = {
        "individual": mint_tokens_for_user(
            "dev_browser_indiv",
            "individual@talentscope.ai",
            {"user_type": "individual", "email_verified": True},
            {"display_name": "Alex Rivera", "user_type": "individual"},
        ),
        "employee": mint_tokens_for_user(
            "dev_browser_employee",
            "employee@talentscope.ai",
            {"user_type": "employee", "company_id": "nvidia", "email_verified": True},
            {"display_name": "Sarah Jenkins", "user_type": "employee", "employee_type": "company-connected", "company_id": "nvidia", "company_name": "NVIDIA"},
        ),
        "nvidia": mint_tokens_for_user(
            "dev_browser_nvidia",
            "nvidia_admin@talentscope.ai",
            {"user_type": "company", "company_id": "nvidia", "email_verified": True},
            {"display_name": "NVIDIA Admin", "user_type": "company", "company_id": "nvidia", "company_name": "NVIDIA"},
        ),
        "google": mint_tokens_for_user(
            "dev_browser_google",
            "google_admin@talentscope.ai",
            {"user_type": "company", "company_id": "google", "email_verified": True},
            {"display_name": "Google Admin", "user_type": "company", "company_id": "google", "company_name": "Google"},
        ),
    }

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(tokens), encoding="utf-8")
    print(f"Tokens written securely to {out_path} ({len(tokens)} identities)")


if __name__ == "__main__":
    main()
