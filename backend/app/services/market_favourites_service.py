from fastapi import HTTPException, status

from app.core.firebase import get_firestore_client
from app.models.skill_intelligence import FavouriteEntityIdsResponse, FavouriteEntityIdsUpdateRequest


def update_market_favourites(uid: str, request: FavouriteEntityIdsUpdateRequest) -> FavouriteEntityIdsResponse:
    from app.services.intelligence_catalog_service import get_market_catalog

    catalog = get_market_catalog(uid)
    supported = {item.get("entity_id") for item in catalog.get("companies_with_job_evidence", [])}
    supported.update(item.get("skill_id") for item in catalog.get("technologies", []))
    registered = catalog.get("registered_company")
    if registered:
        supported.add(registered.get("entity_id"))
    seen: set[str] = set()
    ids: list[str] = []
    for entity_id in request.entity_ids:
        if entity_id not in supported:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Unsupported market entity ID: {entity_id}")
        if entity_id not in seen:
            ids.append(entity_id)
            seen.add(entity_id)
    try:
        client = get_firestore_client()
        document = client.collection("users").document(uid)
        snapshot = document.get()
        record = snapshot.to_dict() if snapshot.exists else {}
        if (record or {}).get("user_type") not in (None, "individual"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Market favourites are available to Individual profiles.")
        document.set({"uid": uid, "preferences": {"favorite_market_entity_ids": ids}}, merge=True)
        return FavouriteEntityIdsResponse(entity_ids=ids)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Your market favourites could not be updated.") from None
