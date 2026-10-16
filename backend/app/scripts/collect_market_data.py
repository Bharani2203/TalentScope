import argparse
import asyncio
import json

from app.models.skill_intelligence import MarketCollectionRequest
from app.services.market_collection_service import collect_market_data


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect one market-data snapshot.")
    parser.add_argument("--location", help="Optional city/location filter for job-market sources.")
    parser.add_argument("--country", help="Optional two-letter country code, such as in.")
    args = parser.parse_args()
    try:
        request = MarketCollectionRequest(location=args.location, country=args.country)
    except ValueError as error:
        parser.error(str(error))
        return 2
    if request.country:
        request.country = request.country.lower()
    result = asyncio.run(collect_market_data(
        location=request.location,
        country=request.country,
    ))
    print(json.dumps(result.model_dump(mode="json"), indent=2))
    return 0 if result.status in {"success", "partial_failure"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
