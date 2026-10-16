"""Stable identity shared by transitional and canonical observation stores."""

import hashlib

from app.analytics.skill_registry import normalize_skill
from app.models.skill_intelligence import MarketObservation


def stable_observation_id(observation: MarketObservation) -> str:
    observed_at = observation.observed_at
    period = observation.period or observed_at.strftime("%Y-%m")
    canonical_name = normalize_skill(observation.skill)
    stable_data = "|".join((
        observation.source.casefold(),
        observation.posting_id or "",
        canonical_name.casefold(),
        period,
        observation.scope,
        (observation.location or "").casefold(),
        observation.signal_type,
    ))
    return observation.id or hashlib.sha256(stable_data.encode("utf-8")).hexdigest()
