import pytest

psycopg2 = pytest.importorskip("psycopg2")

from telemetry_mining import db
from telemetry_mining.config import Config
from telemetry_mining.exceptions import DatabaseUnavailableError


class FakeCursor:
    def __init__(self, conn):
        self.conn = conn

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def execute(self, query, params=None):
        if self.conn.should_fail:
            raise psycopg2.OperationalError("simulated stale/dropped connection")
        self.conn.executed.append((query, params))

    def fetchall(self):
        return self.conn.rows


class FakeConnection:
    def __init__(self, rows=None, should_fail=False):
        self.closed = 0
        self.rows = rows if rows is not None else []
        self.should_fail = should_fail
        self.executed = []

    def cursor(self, cursor_factory=None):
        return FakeCursor(self)

    def close(self):
        self.closed = 1


def make_config(tmp_path, host="fake-host"):
    return Config(
        site="test",
        exposures_root=tmp_path / "exposures",
        redux_root=tmp_path / "redux",
        db_name="d",
        db_host=host,
        db_port=5432,
        db_user="u",
        db_password="p",
    )


def test_get_connection_reuses_same_object(monkeypatch, tmp_path):
    cfg = make_config(tmp_path)
    created = []

    def fake_open(config):
        conn = FakeConnection()
        created.append(conn)
        return conn

    monkeypatch.setattr(db, "_open_connection", fake_open)
    c1 = db._get_connection(cfg)
    c2 = db._get_connection(cfg)
    assert c1 is c2
    assert len(created) == 1


def test_get_connection_reopens_if_closed(monkeypatch, tmp_path):
    cfg = make_config(tmp_path)
    created = []

    def fake_open(config):
        conn = FakeConnection()
        created.append(conn)
        return conn

    monkeypatch.setattr(db, "_open_connection", fake_open)
    c1 = db._get_connection(cfg)
    c1.closed = 1
    c2 = db._get_connection(cfg)
    assert c2 is not c1
    assert len(created) == 2


def test_different_db_identities_get_different_connections(monkeypatch, tmp_path):
    cfg_a = make_config(tmp_path, host="host-a")
    cfg_b = make_config(tmp_path, host="host-b")
    monkeypatch.setattr(db, "_open_connection", lambda config: FakeConnection())
    ca = db._get_connection(cfg_a)
    cb = db._get_connection(cfg_b)
    assert ca is not cb


def test_fetch_all_retries_once_on_operational_error(monkeypatch, tmp_path):
    cfg = make_config(tmp_path)
    conns = [FakeConnection(should_fail=True), FakeConnection(rows=[{"a": 1}])]
    monkeypatch.setattr(db, "_open_connection", lambda config: conns.pop(0))

    result = db.fetch_all(cfg, "SELECT 1")
    assert result == [{"a": 1}]


def test_fetch_all_raises_after_two_failures(monkeypatch, tmp_path):
    cfg = make_config(tmp_path)
    monkeypatch.setattr(db, "_open_connection", lambda config: FakeConnection(should_fail=True))
    with pytest.raises(DatabaseUnavailableError):
        db.fetch_all(cfg, "SELECT 1")


def test_close_all_connections_clears_cache(monkeypatch, tmp_path):
    cfg = make_config(tmp_path)
    conn = FakeConnection()
    monkeypatch.setattr(db, "_open_connection", lambda config: conn)
    db._get_connection(cfg)
    assert db._connection_cache()
    db.close_all_connections()
    assert not db._connection_cache()
    assert conn.closed == 1


def test_connection_cache_is_thread_local(monkeypatch, tmp_path):
    cfg = make_config(tmp_path)
    monkeypatch.setattr(db, "_open_connection", lambda config: FakeConnection())
    main_conn = db._get_connection(cfg)

    other_thread_conn = {}

    def worker():
        other_thread_conn["conn"] = db._get_connection(cfg)

    import threading

    t = threading.Thread(target=worker)
    t.start()
    t.join()

    assert other_thread_conn["conn"] is not main_conn
