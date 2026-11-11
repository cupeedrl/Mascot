"""`python -m app.serve` migrates first and only then starts the API."""

from __future__ import annotations

from app import serve


def test_serve_runs_migrations_before_uvicorn(monkeypatch) -> None:
    calls: list[tuple] = []
    monkeypatch.setattr(serve.command, "upgrade", lambda config, target: calls.append(("upgrade", target, config.get_main_option("script_location"))))
    monkeypatch.setattr(serve.uvicorn, "run", lambda app, host, port: calls.append(("run", app, host, port)))
    monkeypatch.delenv("MASCOT_PORT", raising=False)

    serve.main()

    assert calls[0][:2] == ("upgrade", "head")
    assert calls[0][2].endswith("alembic")
    assert calls[1] == ("run", "app.main:app", "0.0.0.0", 8000)


def test_failed_migration_never_starts_the_server(monkeypatch) -> None:
    started = []

    def boom(config, target):
        raise RuntimeError("migration failed")

    monkeypatch.setattr(serve.command, "upgrade", boom)
    monkeypatch.setattr(serve.uvicorn, "run", lambda *args, **kwargs: started.append(True))
    try:
        serve.main()
    except RuntimeError:
        pass
    assert not started
