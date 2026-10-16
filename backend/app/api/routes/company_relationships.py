from fastapi import APIRouter, Depends, Query

from app.api.dependencies import get_current_user
from app.models.auth import AuthenticatedUser
from app.models.company import (CompanyConnectionRequest, CompanyConnectionReview,
    CompanyConnectionReviewResponse, CompanyInvitationCreate, CompanyInvitationCreated,
    CompanyInvitationToken, CompanyDirectoryEntry, CompanyConnectionRequestItem,
    CompanyInvitationSummary)
from app.services.company_relationship_service import (
    change_invitation, create_invitation, list_company_invitations,
    request_company_connection, review_company_connection,
    set_independent, search_companies, list_pending_connection_requests,
)

router = APIRouter(prefix="/company-relationships", tags=["company relationships"])


@router.get("/companies", response_model=list[CompanyDirectoryEntry])
def company_directory(query: str = Query(min_length=2, max_length=120), user: AuthenticatedUser = Depends(get_current_user)):
    return search_companies(user, query)


@router.get("/connection-requests", response_model=list[CompanyConnectionRequestItem])
def pending_connection_requests(user: AuthenticatedUser = Depends(get_current_user)):
    return list_pending_connection_requests(user)


@router.post("/invitations", response_model=CompanyInvitationCreated)
def issue_invitation(request: CompanyInvitationCreate, user: AuthenticatedUser = Depends(get_current_user)):
    return create_invitation(user, request)


@router.get("/invitations", response_model=list[CompanyInvitationSummary])
def sent_invitations(user: AuthenticatedUser = Depends(get_current_user)):
    return list_company_invitations(user)


@router.post("/invitations/accept")
def accept_invitation(request: CompanyInvitationToken, user: AuthenticatedUser = Depends(get_current_user)):
    return change_invitation(user, request.token, accept=True)


@router.post("/invitations/decline")
def decline_invitation(request: CompanyInvitationToken, user: AuthenticatedUser = Depends(get_current_user)):
    return change_invitation(user, request.token, accept=False)


@router.post("/connection-requests")
def request_connection(request: CompanyConnectionRequest, user: AuthenticatedUser = Depends(get_current_user)):
    return request_company_connection(user, request.company_id)


@router.put("/connection-requests/{employee_uid}", response_model=CompanyConnectionReviewResponse)
def review_connection_request(
    employee_uid: str,
    request: CompanyConnectionReview,
    user: AuthenticatedUser = Depends(get_current_user),
):
    return review_company_connection(user, employee_uid, request.decision)


@router.put("/independent")
def mark_independent(user: AuthenticatedUser = Depends(get_current_user)):
    return set_independent(user)
