from datetime import datetime, timedelta, timezone

import pytest

from app.models.skill_intelligence import MarketObservation


@pytest.mark.integration
def test_firestore_emulator_reads_observation_documents(live_firestore_store):
    observations = live_firestore_store.get_observations(
        cutoff=datetime.now(timezone.utc) - timedelta(days=30)
    )

    assert all(isinstance(item, MarketObservation) for item in observations)
