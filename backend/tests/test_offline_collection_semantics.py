import asyncio
import ipaddress
import socket
from pathlib import Path
import pytest

from app.core.config import Settings
from app.scripts.collect_market_data import _successful_exit, main as cli_main
from app.services.market_collection_service import collect_market_data


def _network_and_db_traps(monkeypatch):
    """Trap all network sockets, HTTP clients, and database stores to ensure zero side effects."""
    # Socket trap
    orig_create_connection = socket.create_connection

    def fail_socket(*args, **kwargs):
        pytest.fail("Network socket connection attempted during offline/dry-run mode")

    monkeypatch.setattr(socket, "create_connection", fail_socket)

    # httpx trap
    try:
        import httpx
        monkeypatch.setattr(httpx.AsyncClient, "request", lambda *args, **kwargs: pytest.fail("httpx request made"))
        monkeypatch.setattr(httpx.Client, "request", lambda *args, **kwargs: pytest.fail("httpx request made"))
    except ImportError:
        pass


def test_offline_test_mode_makes_zero_network_calls_and_zero_db_writes(monkeypatch):
    _network_and_db_traps(monkeypatch)

    result = asyncio.run(collect_market_data(
        location="Chennai",
        country="in",
        offline_test=True,
        provider_name="adzuna",
        query="software developer",
        result_limit=10,
    ))

    assert result.status == "dry_run"
    assert result.dry_run is True
    assert result.data_origin == "test"
    assert result.location == "Chennai"
    assert result.country == "in"
    assert result.observations_inserted == 0
    assert result.observations_validated > 0
    assert result.postings_validated == 2
    assert result.postings_persisted_count is None
    assert result.observations_persistence_status == "not_attempted"
    assert "offline_test" in result.status_reasons
    assert "zero_database_writes" in result.status_reasons
    assert len(result.providers) == 1
    assert result.providers[0].provider == "adzuna"
    assert result.providers[0].status == "success"
    assert result.providers[0].data_origin == "test"
    assert result.providers[0].sampling_frame == "offline_mock_fixture"
    assert _successful_exit(result) is True


def test_preview_dry_run_mode_makes_zero_network_calls_and_zero_db_writes(monkeypatch):
    _network_and_db_traps(monkeypatch)

    result = asyncio.run(collect_market_data(
        location="Chennai",
        country="in",
        dry_run=True,
        preview_only=True,
        provider_name="adzuna",
        query="software developer",
        result_limit=10,
    ))

    assert result.status == "dry_run"
    assert result.dry_run is True
    assert result.data_origin == "test"
    assert result.observations_inserted == 0
    assert result.observations_validated == 0
    assert result.postings_validated == 0
    assert result.postings_persisted_count is None
    assert result.observations_persistence_status == "not_attempted"
    assert "preview_mode_zero_network_calls" in result.status_reasons
    assert "zero_database_writes" in result.status_reasons
    assert len(result.providers) == 1
    assert result.providers[0].provider == "adzuna"
    assert result.providers[0].status == "preview"
    assert result.providers[0].page_size_limit == 10
    assert result.providers[0].sampling_frame == "preview_only_no_network"
    assert _successful_exit(result) is True


def test_cli_rejects_combining_dry_run_and_offline_test(monkeypatch):
    monkeypatch.setattr("sys.argv", ["collect_market_data", "--dry-run", "--offline-test"])
    with pytest.raises(SystemExit) as exc:
        cli_main()
    assert exc.value.code != 0


def test_relative_database_path_is_independent_of_working_directory(monkeypatch):
    settings = Settings.model_construct(skill_intelligence_db_path="data/skill_intelligence.sqlite3")
    monkeypatch.chdir(Path(__file__).parents[2])
    root_result = settings.database_path
    monkeypatch.chdir(Path(__file__).parents[1])
    backend_result = settings.database_path
    assert root_result == backend_result
    assert root_result.is_absolute()


def test_cli_executes_offline_test_successfully(monkeypatch, capsys):
    _network_and_db_traps(monkeypatch)
    monkeypatch.setattr("sys.argv", [
        "collect_market_data", "--offline-test", "--provider", "adzuna",
        "--location", "Chennai", "--country", "in", "--limit", "10",
    ])
    exit_code = cli_main()
    assert exit_code == 0
    captured = capsys.readouterr()
    assert '"status": "dry_run"' in captured.out
    assert '"offline_test"' in captured.out
    assert '"zero_database_writes"' in captured.out
    assert '"data_origin": "test"' in captured.out


def test_cli_fixture_persists_test_observations_and_run_without_firebase(monkeypatch, capsys, tmp_path):
    import sqlite3
    import firebase_admin
    import app.core.firebase as firebase_module
    from app.storage.market_store import MarketDataStore

    _network_and_db_traps(monkeypatch)
    original_connect = socket.socket.connect

    def allow_loopback_only(sock, address):
        host = address[0] if isinstance(address, tuple) and address else ""
        try:
            loopback = ipaddress.ip_address(host).is_loopback
        except ValueError:
            loopback = False
        if not loopback:
            pytest.fail("non-loopback socket connection made")
        return original_connect(sock, address)

    monkeypatch.setattr(socket.socket, "connect", allow_loopback_only)
    monkeypatch.setattr(firebase_module, "get_firebase_app", lambda: pytest.fail("Firebase app requested"))
    monkeypatch.setattr(firebase_module, "get_firestore_client", lambda: pytest.fail("Firestore client requested"))
    monkeypatch.setattr(firebase_admin, "initialize_app", lambda *_args, **_kwargs: pytest.fail("Firebase initialized"))
    monkeypatch.setattr(firebase_module.firestore, "client", lambda *_args, **_kwargs: pytest.fail("Firestore client constructed"))
    database = tmp_path / "fixture-run.sqlite3"
    monkeypatch.setattr("sys.argv", [
        "collect_market_data", "--fixture", "--database-path", str(database),
        "--provider", "adzuna", "--location", "Chennai", "--country", "in", "--limit", "10",
        "--trigger-type", "workflow_dispatch", "--workflow-run-id", "fixture-run-123",
        "--workflow-attempt", "2",
    ])

    assert cli_main() == 0
    output = capsys.readouterr().out
    assert '"status": "success"' in output
    assert '"data_origin": "test"' in output
    assert '"observation_storage_backend": "sqlite"' in output
    assert database.is_file()

    connection = sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True)
    try:
        rows = connection.execute(
            "SELECT data_origin, panel_version, extractor_version, fetch_run_id "
            "FROM market_observations"
        ).fetchall()
        runs = connection.execute(
            "SELECT status, record_json FROM market_fetch_runs"
        ).fetchall()
        fixture_posts = connection.execute(
            "SELECT COUNT(*), COUNT(DISTINCT data_origin) FROM market_fixture_postings"
        ).fetchone()
    finally:
        connection.close()
    assert rows
    assert all(row[0] == "test" for row in rows)
    assert all(row[1] == "fixture-panel-v1" for row in rows)
    assert all(row[2] == "skill-extractor-v1" for row in rows)
    assert MarketDataStore(database, read_only=True).get_observations() == []
    assert runs and all(row[0] == "success" for row in runs)
    assert all('"execution_mode":"fixture"' in row[1] for row in runs)
    assert all('"trigger_type":"workflow_dispatch"' in row[1] for row in runs)
    assert all('"workflow_run_id":"fixture-run-123"' in row[1] for row in runs)
    assert all('"workflow_attempt":2' in row[1] for row in runs)
    assert fixture_posts == (2, 1)


def test_fixture_retry_keeps_observations_and_postings_idempotent(tmp_path):
    import sqlite3
    from app.services.market_collection_service import OfflineFixtureProvider
    from app.storage.fetch_run_store import SQLiteFetchRunStore
    from app.storage.market_store import MarketDataStore

    database = tmp_path / "retry-fixture.sqlite3"
    store = MarketDataStore(database)
    runs = SQLiteFetchRunStore(database)
    settings = Settings.model_construct(
        environment="local-test", skill_intelligence_read_backend="sqlite",
        skill_intelligence_db_path=str(database), market_collection_enabled_providers=[],
        market_collection_panel_version="fixture-panel-v1", market_collection_cron="fixture-manual",
    )
    async def collect_once():
        return await collect_market_data(
            settings=settings, providers=[OfflineFixtureProvider("adzuna")],
            fetch_run_store=runs, observation_store=store,
            raw_response_archive=type("NoArchive", (), {"archive": lambda *_a, **_k: None})(),
            fixture_mode=True, posting_persister=store.persist_fixture_postings,
            location="Chennai", country="in", query="software developer", result_limit=10,
        )

    first = asyncio.run(collect_once())
    second = asyncio.run(collect_once())
    connection = sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True)
    try:
        observation_count = connection.execute("SELECT COUNT(*) FROM market_observations").fetchone()[0]
        posting_count = connection.execute("SELECT COUNT(*) FROM market_fixture_postings").fetchone()[0]
        run_count = connection.execute("SELECT COUNT(*) FROM market_fetch_runs").fetchone()[0]
    finally:
        connection.close()
    assert first.observations_inserted > 0
    assert second.observations_inserted == 0
    assert first.postings_persisted_count == second.postings_persisted_count == 2
    assert observation_count == first.observations_inserted
    assert posting_count == 2
    assert run_count == 2


def test_cli_fixture_requires_a_new_temp_database(monkeypatch, tmp_path):
    existing = tmp_path / "already-existing.sqlite3"
    existing.touch()
    monkeypatch.setattr("sys.argv", [
        "collect_market_data", "--fixture", "--database-path", str(existing),
    ])
    with pytest.raises(SystemExit) as exc:
        cli_main()
    assert exc.value.code == 2


@pytest.mark.parametrize("database_arg", [None, "outside-temp.sqlite3"])
def test_cli_fixture_rejects_missing_or_out_of_temp_database(monkeypatch, database_arg):
    args = ["collect_market_data", "--fixture"]
    if database_arg is not None:
        args.extend(["--database-path", str(Path(__file__).parents[2] / database_arg)])
    monkeypatch.setattr("sys.argv", args)
    with pytest.raises(SystemExit) as exc:
        cli_main()
    assert exc.value.code == 2


@pytest.mark.parametrize("outcome", ["zero", "failed"])
def test_sqlite_fixture_run_ledger_records_zero_and_failed_terminal_states(tmp_path, outcome):
    from app.services.market_data.base import PostingFetchResult
    from app.storage.fetch_run_store import SQLiteFetchRunStore
    from app.storage.market_store import MarketDataStore

    class FixtureProvider:
        name = "adzuna"

        async def fetch_market_postings_with_stats(self, **_kwargs):
            if outcome == "failed":
                raise TimeoutError("fixture timeout")
            return PostingFetchResult(
                postings=[], records_fetched=0, pagination_complete=True,
                zero_results_verified=True, sampling_frame="test zero fixture",
            )

    database = tmp_path / f"{outcome}.sqlite3"
    market_store = MarketDataStore(database)
    run_store = SQLiteFetchRunStore(database)
    settings = Settings.model_construct(
        environment="local-test", skill_intelligence_read_backend="sqlite",
        skill_intelligence_db_path=str(database), market_collection_enabled_providers=[],
        market_collection_panel_version="fixture-panel-v1", market_collection_cron="fixture-manual",
    )
    result = asyncio.run(collect_market_data(
        settings=settings, providers=[FixtureProvider()], fetch_run_store=run_store,
        observation_store=market_store, raw_response_archive=object(), fixture_mode=True,
        posting_persister=lambda *_args, **_kwargs: 0, country="in", query="fixture query",
    ))
    saved = run_store.collection_summary()["last_collection"]["providers"]["adzuna"]
    assert saved["completed_at"]
    assert saved["status"] == ("success" if outcome == "zero" else "failed")
    assert result.sources_failed == ({"adzuna": "Adzuna collection failed."} if outcome == "failed" else {})
    if outcome == "zero":
        assert saved["zero_results_verified"] is True
        assert result.status == "success"
    else:
        assert saved["error_category"] == "provider"
        assert result.status == "error"


def test_scheduled_workflow_is_fixture_only_bounded_and_serialized():
    from pathlib import Path

    workflow = Path(__file__).parents[2] / ".github" / "workflows" / "market-collection-fixture.yml"
    content = workflow.read_text(encoding="utf-8")
    assert 'cron: "15 3 * * *"' in content
    assert "workflow_dispatch:" in content
    assert "cancel-in-progress: false" in content
    assert "timeout-minutes: 10" in content
    assert "--fixture --database-path" in content
    assert "--provider adzuna" in content
    assert "secrets." not in content


def test_cli_executes_dry_run_preview_successfully(monkeypatch, capsys):
    _network_and_db_traps(monkeypatch)
    monkeypatch.setattr("sys.argv", [
        "collect_market_data", "--dry-run", "--provider", "adzuna",
        "--location", "Chennai", "--country", "in", "--limit", "10",
    ])
    exit_code = cli_main()
    assert exit_code == 0
    captured = capsys.readouterr()
    assert '"status": "dry_run"' in captured.out
    assert '"preview_mode_zero_network_calls"' in captured.out
    assert '"zero_database_writes"' in captured.out
