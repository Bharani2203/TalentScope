"""Build user-facing structured blocks from already retrieved answer facts."""

from __future__ import annotations

import re
from typing import Any, Iterable


def infer_assistant_domain(intent: str) -> str:
    """Map a rule-selected intent to its response domain for auto routing."""
    if intent in {
        "search_jobs", "aggregate_posting_skills", "hiring_demand_trends",
    }:
        return "job"
    if intent in {
        "retrieve_snapshot", "lookup_github_adoption", "analyze_company_workforce",
        "rank_skill_trends", "market_tech_signals", "market_trend_velocity",
    }:
        return "market"
    return "skill"


def _get(value: Any, key: str, default: Any = None) -> Any:
    return value.get(key, default) if isinstance(value, dict) else getattr(value, key, default)


def _details(fact: Any) -> dict[str, Any]:
    value = _get(fact, "details", {})
    return value if isinstance(value, dict) else {}


def _first_sentence(text: str) -> str:
    sentence = re.split(r"(?<=[.!?])\s+|\n", text.strip(), maxsplit=1)[0].strip()
    return sentence


def _matching_skill(message: str, skill_rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    folded = message.casefold()
    candidates = sorted(skill_rows, key=lambda row: len(str(row.get("skill") or "")), reverse=True)
    for row in candidates:
        name = str(row.get("skill") or "").strip()
        if name and re.search(rf"(?<!\w){re.escape(name.casefold())}(?!\w)", folded):
            return row
    return None


def _adoption_label(details: dict[str, Any]) -> str:
    label = str(details.get("adoption_label") or "Not enough data")
    if label.casefold() != "flat or declining":
        return label
    direction = str(details.get("adoption_direction") or "").casefold()
    growth = details.get("adoption_growth")
    if direction in {"up", "down", "flat"} and isinstance(growth, (int, float)):
        direction_word = {"up": "increased", "down": "decreased", "flat": "was unchanged"}[direction]
        return f"{label} ({direction_word} {abs(growth):.1%})"
    return label


def build_answer_block(
    *,
    intent: str,
    user_message: str,
    answer: str,
    facts: Iterable[Any],
    evidence: Iterable[Any] = (),
    limitations: Iterable[str] = (),
) -> dict[str, Any]:
    """Format existing facts only; this function performs no storage reads."""
    fact_list = list(facts or [])
    evidence_list = list(evidence or [])
    summary_fact = next(
        (fact for fact in fact_list if _get(fact, "fact_type") == "collected_posting_skills_summary"),
        None,
    )
    postings_fact = next(
        (fact for fact in fact_list if _get(fact, "fact_type") == "stored_job_postings"),
        None,
    )

    verdict = _first_sentence(answer) or "The result is based on the available evidence."
    summary = answer.strip()
    table: dict[str, Any] | None = None
    disclosures: list[str] = []
    sources: list[str] = []
    bullets: list[str] = []

    if summary_fact is not None:
        detail = _details(summary_fact)
        total = int(_get(summary_fact, "metric_value", 0) or 0)
        skill_rows = detail.get("skill_counts")
        if not isinstance(skill_rows, list):
            skill_rows = []
        requested = _matching_skill(user_message, skill_rows)
        display_rows = [requested] if requested else skill_rows[:20]
        rendered_rows = []
        for row in display_rows:
            count = int(row.get("count") or 0)
            company_count = int(row.get("company_count") or 0)
            share = row.get("share")
            level = str(row.get("verdict") or "Not enough data")
            rendered_rows.append({
                "Skill": str(row.get("skill") or ""),
                "Postings": count,
                "Share": f"{share:.1%}" if isinstance(share, (int, float)) and total >= 30 and count >= 5 else "Not shown",
                "Companies": company_count,
                "Demand": level,
            })
            if requested is row:
                if level.casefold() == "not enough data":
                    verdict = f"{row.get('skill')} — Not enough data ({count} of {total})"
                else:
                    verdict = f"{row.get('skill')} — {level} demand in collected postings ({count} of {total})"
                if row.get("limited_evidence"):
                    verdict += "; limited evidence: mostly one or two employers"
                summary = (
                    "Current snapshot only. It does not show change over time; a posting-based trend requires the four-month evidence gate."
                )
        if rendered_rows:
            table = {
                "columns": ["Skill", "Postings", "Share", "Companies", "Demand"],
                "rows": rendered_rows,
            }
        disclosures.append(
            f"Sample size: N={total} all stored India postings after source and provider-job-ID deduplication; this is not the whole Indian market."
        )

    if postings_fact is not None:
        detail = _details(postings_fact)
        posting_rows = detail.get("postings")
        if isinstance(posting_rows, list):
            allowed = (
                ("title", "Title"),
                ("company_name", "Company"),
                ("location", "Location"),
                ("posted_at", "Posted date"),
                ("source_url", "Source"),
            )
            present = [pair for pair in allowed if any(_get(row, pair[0]) for row in posting_rows)]
            table = {
                "columns": [label for _, label in present],
                "rows": [
                    {label: _get(row, key) for key, label in present if _get(row, key) is not None}
                    for row in posting_rows
                ],
            }
            table["rows"] = [row for row in table["rows"] if row]
            if table["rows"]:
                verdict = f"{len(table['rows'])} stored job postings match."
            else:
                verdict = "No matching postings were found in the collected records."
                summary = "The requested filters did not match a stored posting."
                alternatives = detail.get("no_match_alternatives") or []
                bullets.extend(str(item) for item in alternatives[:3])

    if any(
        "o*net" in text.casefold() or "occupation mapping" in text.casefold()
        for text in list(limitations or [])
    ):
        disclosures.append(
            "O*NET mappings are static occupational context, not mandatory qualifications or current hiring evidence."
        )
    for fact in fact_list:
        detail = _details(fact)
        mapping_disclosure = detail.get("mapping_disclosure")
        if mapping_disclosure:
            disclosures.append(str(mapping_disclosure))
        signal_type = detail.get("signal_type") or _get(fact, "signal_type")
        if signal_type == "adoption":
            disclosures.append("Developer adoption measures developer activity, not hiring demand.")

    for item in evidence_list:
        source = str(_get(item, "source") or "").strip()
        description = str(_get(item, "description") or "").strip()
        if source and source not in sources:
            sources.append(source)
        if "not hiring demand" in description.casefold():
            disclosures.append("Developer adoption, not hiring demand.")
        if "o*net" in description.casefold():
            disclosures.append(
                "O*NET mappings are static occupational context, not mandatory qualifications or current hiring evidence."
            )

    if "market intelligence snapshot" in summary.casefold() and "not hiring demand" in summary.casefold():
        summary = re.sub(r"\s*;?\s*this is not hiring demand\.?", "", summary, flags=re.IGNORECASE)
        disclosures.append("The snapshot measures quarterly developer adoption, not employer hiring demand.")

    unique_disclosures = list(dict.fromkeys(item.strip() for item in disclosures if item and item.strip()))
    if summary_fact is not None and requested is not None:
        skill = str(requested.get("skill") or "")
        adoption_fact = next(
            (
                fact for fact in fact_list
                if (_details(fact).get("signal_type") or _get(fact, "signal_type")) == "adoption"
                and str(_get(fact, "entity_name") or "").casefold() == skill.casefold()
            ),
            None,
        )
        if adoption_fact is not None:
            adoption_detail = _details(adoption_fact)
            direction = _adoption_label(adoption_detail)
            if direction.casefold() in {"rising", "growing slowly", "flat or declining"}:
                verdict = f"{verdict}; developer adoption {direction.casefold()}"
            table = table or {"columns": ["Signal", "Result"], "rows": []}
            table["columns"] = ["Signal", "Result"]
            table["rows"] = [
                {"Signal": "Collected postings — hiring demand", "Result": requested.get("verdict")},
                {"Signal": "Developer adoption, not hiring demand", "Result": direction},
            ]
            unique_disclosures.append("Developer adoption measures developer activity, not hiring demand.")

    if summary_fact is None:
        adoption_fact = next(
            (
                fact for fact in fact_list
                if (_details(fact).get("signal_type") or _get(fact, "signal_type")) == "adoption"
                and _details(fact).get("adoption_label")
            ),
            None,
        )
        if adoption_fact is not None:
            adoption_detail = _details(adoption_fact)
            direction = _adoption_label(adoption_detail)
            entity = str(_get(adoption_fact, "entity_name") or "Developer activity")
            verdict = f"{entity} — Developer adoption, not hiring demand: {direction}"
            summary = "This signal measures historical developer activity over consecutive quarters."
            table = {
                "columns": ["Signal", "Result"],
                "rows": [{"Signal": "Developer adoption, not hiring demand", "Result": direction}],
            }
            unique_disclosures.append("Developer adoption measures growth in historical GitHub activity, not hiring demand.")

    return {
        "verdict": verdict,
        "summary": summary,
        "table": table,
        "bullets": bullets,
        "footer": {
            "based_on": ", ".join(sources) if sources else None,
            "disclosures": list(dict.fromkeys(unique_disclosures)),
        },
    }
