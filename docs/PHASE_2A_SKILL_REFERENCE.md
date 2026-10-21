# Phase 2A — Skill Reference implementation note

## Execution path

The existing Skill Intelligence feature registry in `src/pages/individual/ai-assistant/AIAssistant.js` selects `skill_technology_reference`. The question handler sends the original `message`, `domain`, selected `capability_id`, and conversation/request identifiers through `queryCoreIntelligenceAnswer`; the API client posts to the authenticated `/api/v1/intelligence/answer` route. The route validates `CoreIntelligenceAnswerResponse` and calls the same planner/orchestrator used by the rest of the assistant.

The planner resolves explicit ESCO taxonomy names using `EntityRegistryService`, constrained by taxonomy and entity family. The reference service reads `ref_esco_skills`, `ref_esco_occupations`, and `ref_esco_occupation_skill_relations` from the existing SQLite reference database. ESCO identities retain their concept URIs; canonical skill IDs use `skill:esco:<URI>` and occupation IDs use `occupation:esco:<URI>`, distinct from O*NET SOC identities and internal `skill:<id>`/`tech:<id>` identifiers. Response facts carry source/version/description, taxonomy URI, relationship type, evidence ID, and provenance. The frontend shows the reference source, canonical ID, taxonomy version, description, relationship, taxonomy URIs, and provenance; the existing conversation answer renderer continues to handle clarification and error states.

## Verified local records

The database was opened using SQLite read-only mode. A case-insensitive ESCO alias query found `Python` as an alternative label of `Python (computer programming)`, URI `http://data.europa.eu/esco/skill/ccd0a1d9-afda-43d9-b901-96344886e14d`, version `v1.2.1`. Its description is read from the database and returned in the API fact. The Data Analyst occupation record is `http://data.europa.eu/esco/occupation/d3edb8f8-3a06-47a0-8fb9-9b212c006aa2`, version `v1.2.1`; its 67 imported occupation-skill relations comprise 36 `essential` and 31 `optional`. The endpoint returns at most ten matching associations per request, with real relation rows and their skill/occupation URIs. Database table counts were asserted unchanged by integration tests.

## Corrective changes

- ESCO alternative labels may contain multiple newline-separated labels in one imported value. Entity resolution now compares each line independently, including `Python`, and exposes the split aliases.
- The exact question “What is the Python skill in the ESCO taxonomy?” was not recognized by the explicit ESCO phrase matcher because the pattern omitted “the” and “taxonomy”; it now preserves the whole question while extracting only Python.
- Skill Reference readiness previously treated every ESCO request as a skill URI check. It now permits an ESCO occupation only when the occupation and at least one linked-skill relation exist locally.
- A selected Skill Reference feature can retrieve explicit ESCO occupation-skill links in the Skill domain. The taxonomy links remain clearly described as reference mappings, not hiring demand or proof of qualifications.
- Unknown or ambiguous explicit ESCO lookups now request clarification before readiness failure can produce an irrelevant insufficient-observation response.
- Reference detail rendering now displays descriptions, ESCO relation types, taxonomy URIs, and provenance.

No live Firebase, Firestore, Gemini, or external provider was contacted. HTTP tests inject an offline authenticated test user and orchestrator; they verify route/schema integration, not production identity-provider operation.

## Verification and manual review

Offline integration tests use the checked-out database with read-only stores and forbid Firestore initialization. They cover the exact selected-feature Python question, Data Analyst associations, missing and ambiguous names, API response schema/provenance, and unchanged local row counts. Frontend tests cover reference details and conversation success/clarification/error rendering.

To review manually after deploying this code to a suitable local environment: open AI Assistant → Skill Intelligence → Skill Reference; ask “What is the Python skill in the ESCO taxonomy?” and confirm the ESCO label, description, version, URI, and evidence details. Then ask “What skills are associated with the Data Analyst occupation in ESCO?” and confirm essential/optional labels and ESCO identifiers. Try an unknown ESCO skill and an ambiguous term to confirm clarification is shown. These steps verify the browser/session integration only when run against a safely configured non-production environment; no browser or live service was used in this phase.
