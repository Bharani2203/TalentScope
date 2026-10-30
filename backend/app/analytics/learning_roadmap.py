"""Small deterministic practice-roadmap generator; it creates no course claims."""

from __future__ import annotations

from typing import Any


def _practice_for(skill: str, role: str) -> tuple[str, str, str]:
    label = skill.casefold()
    if label in {"c", "c programming", "c language", "c programming language"}:
        return (
            "Write a small C program that reads input, uses a condition and a loop, and prints a result.",
            "A C source file with sample input/output and a short note explaining the logic.",
            "Compile and run the program with a normal case and an edge case; compare both outputs with your expected results.",
        )
    if "sql" in label or "query language" in label or "database" in label:
        return (
            "Write SQL queries over a small sample schema: filter rows, group results, and join two tables.",
            "A saved set of queries with sample outputs and a short explanation of each result.",
            "Check that filters, grouping, and joins return the expected rows on a hand-checked sample.",
        )
    if "python" in label or "programming" in label:
        return (
            "Write a small script that reads a CSV, handles missing values, and summarizes selected columns.",
            "A runnable script and a short README describing its inputs, outputs, and assumptions.",
            "Run it against a tiny known CSV and confirm row counts and summary values manually.",
        )
    if "spreadsheet" in label or "excel" in label:
        return (
            "Clean a small spreadsheet dataset, apply formulas, and create a summary table or chart.",
            "A workbook or equivalent exported result with documented formulas and summary findings.",
            "Recalculate a few cells by hand and verify that the summary uses the intended source range.",
        )
    if "data analysis" in label or "statistical" in label or "analytics" in label:
        return (
            "Analyze a small dataset, state one question, document cleaning choices, and summarize the result with a chart.",
            "A short analysis note with reproducible steps, one chart, and a conclusion tied to the data.",
            "Check that the chart and conclusion agree with a manually inspected sample and stated assumptions.",
        )
    return (
        f"Complete a small {skill} exercise using a public or locally supplied practice dataset relevant to {role}.",
        f"A small artifact demonstrating how {skill} was applied to a {role}-related task.",
        f"Compare the artifact with the task requirements and explain what it demonstrates and what remains uncertain about {skill} proficiency.",
    )


def build_learning_roadmap(gap_result: dict[str, Any], *, limit: int = 10) -> dict[str, Any]:
    """Turn verified reference gaps into suggested practice tasks, not courses."""
    occupation = gap_result.get("occupation") or {}
    role = str(occupation.get("label") or "the selected occupation")
    missing = list(gap_result.get("missing") or [])
    ordered = sorted(
        missing,
        key=lambda item: (
            {"essential": 0, "optional": 1, None: 2}.get(item.get("classification"), 2),
            str(item.get("label", "")).casefold(),
            str(item.get("taxonomy_id", "")),
        ),
    )
    roadmap = []
    for rank, item in enumerate(ordered[: max(1, min(limit, 20))], start=1):
        task, outcome, self_check = _practice_for(item["label"], role)
        roadmap.append({
            "priority": rank,
            "priority_group": item.get("classification") or "unranked_reference_gap",
            "target_skill": item["label"],
            "taxonomy": item.get("taxonomy"),
            "taxonomy_id": item.get("taxonomy_id"),
            "why_relevant": item.get("priority_rationale"),
            "prerequisites": [],
            "prerequisite_evidence_available": False,
            "suggested_task": task,
            "tangible_outcome": outcome,
            "self_check_criterion": self_check,
            "source_record_id": item.get("source_record_id"),
            "source": item.get("source"),
            "suggestion_origin": "platform_generated_practice_suggestion",
            "progress_state": "not_started",
            "assessment_status": "not_assessed",
            "proficiency_verified": False,
        })
    return {
        "occupation": occupation,
        "steps": roadmap,
        "total_missing_reference_skills": len(missing),
        "omitted_step_count": max(0, len(missing) - len(roadmap)),
        "progress_persistence": "not_configured",
        "limitations": [
            "Practice tasks are generated suggestions, not verified courses or externally validated learning materials.",
            "Self-check is self-assessment only; practice completion does not establish verified proficiency.",
            "No prerequisite relationships, study duration, or expected learning outcomes are inferred without source evidence.",
        ],
    }
