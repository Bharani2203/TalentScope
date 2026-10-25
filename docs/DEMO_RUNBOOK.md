# Local Assistant Demo Runbook

This runbook is for an isolated local demo. Use only the Firebase Auth and
Firestore emulators and the local backend. Do not configure production
credentials, enable a market provider, or enable Gemini for this demo.

## Start the local environment

Open three PowerShell terminals from the repository root.

### 1. Start Auth and Firestore emulators

```powershell
npm run start:emulators
```

Confirm both emulators report that they are ready before continuing. These
commands target the dedicated `demo-talentscope-local` project and loopback
hosts only.

### 2. Start the backend in emulator mode

In the second terminal:

```powershell
Set-Location .\backend
.\scripts\start-local-emulator-test.ps1
```

The launcher sets all six required environment variables for the backend
process, disables Gemini and market-provider credentials, and restores the
terminal's prior environment when the process stops. The values it sets are:

| Environment variable | Emulator value |
| --- | --- |
| `TALENTSCOPE_FIREBASE_MODE` | `emulator` |
| `TALENTSCOPE_OFFLINE_TEST_MODE` | `1` |
| `ENVIRONMENT` | `local-test` |
| `FIREBASE_PROJECT_ID` | `demo-talentscope-local` |
| `FIRESTORE_EMULATOR_HOST` | `127.0.0.1:8080` |
| `FIREBASE_AUTH_EMULATOR_HOST` | `127.0.0.1:9099` |

The equivalent explicit setup, if not using the launcher, is:

```powershell
$env:TALENTSCOPE_FIREBASE_MODE = "emulator"
$env:TALENTSCOPE_OFFLINE_TEST_MODE = "1"
$env:ENVIRONMENT = "local-test"
$env:FIREBASE_PROJECT_ID = "demo-talentscope-local"
$env:FIRESTORE_EMULATOR_HOST = "127.0.0.1:8080"
$env:FIREBASE_AUTH_EMULATOR_HOST = "127.0.0.1:9099"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Do not replace either loopback host or the demo project ID with a real
Firebase target. Emulator mode fails closed if the configuration is not
local.

### 3. Create a synthetic user and start the frontend

In the second terminal, or another terminal with the repository's emulator
configuration:

```powershell
Set-Location .\backend
.\scripts\provision-emulator-user.ps1
```

The script prompts for a password using hidden input. Do not print or save the
password or token. In the third terminal:

```powershell
Set-Location ..
npm start
```

Open `http://127.0.0.1:3000/?firebaseEmulator=1#/auth/login`, sign in with the
synthetic emulator account, then open the AI Assistant. The browser's existing
Firebase SDK, icon, and font imports may still use CDN-hosted static assets;
assistant API, Auth, and Firestore data traffic should use the local
environment. This runbook does not make any live requests.

## Demo sample data and provenance

The Assistant displays a prominent **“DEMO SAMPLE — illustrative data only;
not live market evidence.”** banner whenever a returned source, evidence item,
or fact has `data_origin: "demo"`. The banner is provenance-driven; it is not
inferred from a title, company, URL, or a manually selected UI option.

To add one explicitly labelled illustrative observation to the Firestore
emulator, open another PowerShell terminal, set the six environment variables
using the explicit setup block above (the launcher does not pass its
process-scoped environment to other terminals), then run this from `backend`.
It adds one current-month snapshot only; it does not backdate data or create a
multi-month trend:

```powershell
@'
from datetime import datetime, timezone
from app.models.skill_intelligence import MarketObservation
from app.storage.firestore_observation_store import FirestoreObservationStore

now = datetime.now(timezone.utc)
observation = MarketObservation(
    source="demo_sample",
    signal_type="interest",
    observed_at=now,
    period=now.strftime("%Y-%m"),
    location="Global",
    scope="global",
    skill="Python",
    value=1,
    unit="illustrative sample",
    data_origin="demo",
    history_type="snapshot",
    series_id=f"demo_sample:python:{now:%Y-%m}",
    metadata={"fixture_label": "demo_sample"},
)
count = FirestoreObservationStore().insert_observations([observation])
print(f"Inserted {count} explicitly demo-labelled observation(s) into the emulator.")
'@ | .\.venv\Scripts\python.exe -
```

This row is illustrative, not measured hiring demand. Demo-origin observations
do not qualify as real trend evidence and must not be used to satisfy readiness
gates. The banner appears in an Assistant response only if that response
actually includes the demo-origin row as source/evidence/fact; the seed command
does not force the API to include it or claim that it was used.

**Do not seed synthetic postings into the `jobs` collection for a browser
demo.** The current stored-job model and answer contract do not carry demo
provenance for postings; a seeded posting could therefore be displayed as an
ordinary stored result, without a truthful demo banner. The Bangalore
job-search example is covered by an isolated mocked route test that seeds
in-memory postings. A provenance-safe emulator job seed requires a future
backend contract change and is intentionally not provided here.

## Eight demo questions

The expected outcomes below follow the mocked route coverage. “Data” means the
route has a deterministic/local reference or matching stored data; it does
not mean the emulator starts with those records. An empty emulator may return
limited data for a question whose mocked fixture includes records.

| Question | Expected capability/result | Expected presentation |
| --- | --- | --- |
| “Find data engineer jobs in Bangalore” | `job_verified_postings`; the mocked fixture has stored Bangalore/Bengaluru postings | **Data** in the mocked seeded case. In an empty emulator, limited data; do not insert synthetic postings as ordinary jobs. |
| “Find python developer jobs in Chennai” | `job_verified_postings`; no matching postings | **Limited data** with scanned/matched counts; live search is off. |
| “What does a data engineer do?” | `skill_lookup`; local reference dataset | **Data** from the reference capability. |
| “What skills does a data engineer need?” | `job_role_requirements`; no sufficient evidence | **Limited data**; do not invent requirements or evidence. |
| “Is Python becoming more popular?” | `skill_demand_trends`; trend readiness is partial | **Limited data**; show only returned evidence and limits, not an unsupported trend claim. |
| “Compare Python and Java” | No executable comparison capability; clarification | **Clarification** that comparison is not supported; offer separate lookups. |
| “Give me a preparation plan for Web Developer” | `job_preparation_actions`; local reference dataset | **Data** from deterministic preparation guidance. |
| “what is the weather” | No data capability; clarification | **Clarification** asking whether the user wants skills, jobs, market signals, or role information. |

For the entirely mocked route suite (no app server, emulator, Gemini, or
provider calls), from `backend` run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests\test_demo_questions_mocked.py
```

## Degraded-mode rehearsal (Gemini off)

The emulator launcher disables Gemini and market-provider credentials. With
the emulator and local backend running, ask the questions above in the
Assistant. Deterministic routing, local reference answers, stored-job lookup,
insufficient-data responses, and clarifications should remain usable. When a
response is marked degraded, the UI says **“Gemini unavailable, showing
deterministic answer.”** No Gemini request is needed for this rehearsal.

For an isolated backend test of the mocked demo routes, use the pytest command
above; it injects in-memory Firestore and an unavailable Gemini stub. Do not
set an availability override or enable a live provider.

## Known limits (for teachers)

- The four-month readiness gate is not met. Collection began around
  **6 October 2026**; one demo snapshot cannot establish four completed
  months, and sample data must not be backdated to make it appear met.
- When `n < 20`, show counts rather than percentages.
- Attention signals are contextual attention, not hiring demand.
- Sample coverage is skewed toward a few global companies and should not be
  presented as representative of the whole market.
