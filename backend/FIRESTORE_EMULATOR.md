# Local Firebase Emulator workflow

The backend's Firebase guard requires both Firestore and Auth emulators, an explicit local-test mode, and the dedicated `demo-talentscope-local` project. It fails closed instead of falling back to production.

## Windows PowerShell

From the backend directory, start the emulators in one terminal:

```powershell
firebase emulators:start --only firestore,auth --project demo-talentscope-local
```

In another terminal, configure the backend and start it:

```powershell
$env:TALENTSCOPE_FIREBASE_MODE = "emulator"
$env:TALENTSCOPE_OFFLINE_TEST_MODE = "1"
$env:ENVIRONMENT = "local-test"
$env:FIREBASE_PROJECT_ID = "demo-talentscope-local"
$env:FIRESTORE_EMULATOR_HOST = "127.0.0.1:8080"
$env:FIREBASE_AUTH_EMULATOR_HOST = "127.0.0.1:9099"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Protected API routes still require a Firebase ID token. The Auth emulator is configured because the backend verifies tokens with Firebase Admin; use an emulator user/token for local checks. There is no local-login bypass. No production credential file is needed in emulator mode.

Both sync tools are dry-run by default and require explicit source/target flags. Use `--apply` only for an intentional copy. Emulator-to-real copy requires a real project ID and service-account file path; real-to-emulator copy requires the real source project/file and explicit loopback emulator host.

## Copy commands (only when an operator intends to sync data)

Run these from the backend directory after the emulator is available. The default is read-only dry-run; `--apply` is the explicit write switch.

```powershell
.\.venv\Scripts\python.exe -m app.scripts.copy_firestore_real_to_emulator --source-project <REAL_PROJECT_ID> --source-credentials <PATH_TO_SERVICE_ACCOUNT_JSON> --target-emulator-host 127.0.0.1:8080
.\.venv\Scripts\python.exe -m app.scripts.copy_firestore_real_to_emulator --source-project <REAL_PROJECT_ID> --source-credentials <PATH_TO_SERVICE_ACCOUNT_JSON> --target-emulator-host 127.0.0.1:8080 --apply
.\.venv\Scripts\python.exe -m app.scripts.sync_firestore_emulator_to_real --source-emulator-host 127.0.0.1:8080 --target-project <REAL_PROJECT_ID> --target-credentials <PATH_TO_SERVICE_ACCOUNT_JSON>
.\.venv\Scripts\python.exe -m app.scripts.sync_firestore_emulator_to_real --source-emulator-host 127.0.0.1:8080 --target-project <REAL_PROJECT_ID> --target-credentials <PATH_TO_SERVICE_ACCOUNT_JSON> --apply
```

The sync tools only copy `jobs` and `skill_market_signals`; they preserve document IDs, skip IDs already present at the destination, and use 200-document read/write batches. The emulator-to-real sync prints complete source/target counts before its first write.
