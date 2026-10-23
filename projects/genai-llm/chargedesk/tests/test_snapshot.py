from datetime import date

from chargedesk.data.snapshot import snapshot_connection

E = date(2021, 10, 5)


def test_future_days_are_hidden(fake_warehouse):
    con = snapshot_connection(fake_warehouse, E)
    assert con.execute("select max(day) from marts.fct_post_day").fetchone()[0] == E
    con.close()


def test_next_day_outcome_hidden_until_known(fake_warehouse):
    con = snapshot_connection(fake_warehouse, E)
    tonight = con.execute(
        "select count(*), count(episode_next_day) from marts.fct_evening_list where evening = ?", [E]).fetchone()
    yesterday = con.execute(
        "select count(episode_next_day) from marts.fct_evening_list where evening = ?", [date(2021, 10, 4)]).fetchone()
    assert tonight == (20, 0)        # liste du soir visible, resultat du lendemain cache
    assert yesterday[0] == 20        # resultat d'hier connu ce soir
    assert con.execute("select max(evening) from marts.fct_post_evening").fetchone()[0] == E
    assert con.execute(
        "select count(n_hits) from marts.fct_list_daily_hits where evening = ?", [E]).fetchone()[0] == 0
    con.close()


def test_alerts_and_drift_are_dated(fake_warehouse):
    con = snapshot_connection(fake_warehouse, E)
    assert con.execute("select max(alert_date) from marts.fct_silent_alert").fetchone()[0] <= E
    assert con.execute("select count(*) from marts.fct_drift_month").fetchone()[0] == 1   # septembre, connu fin septembre
    con.close()


def test_snapshot_cannot_write_to_warehouse(fake_warehouse):
    con = snapshot_connection(fake_warehouse, E)
    try:
        con.execute("delete from wh.marts.fct_post_day")
        raised = False
    except Exception:
        raised = True
    con.close()
    assert raised


def test_training_table_is_not_exposed(fake_warehouse):
    con = snapshot_connection(fake_warehouse, E)
    tables = {r[0] for r in con.execute(
        "select table_name from information_schema.tables where table_schema = 'marts' and table_catalog = current_database()").fetchall()}
    con.close()
    assert "fct_post_signals" not in tables and "fct_post_evening" in tables


def test_dimensions_expose_only_fixed_columns(tmp_path):
    """Meme si l'entrepot contient une colonne datee dans dim_post, la vue du soir ne la montre pas."""
    import duckdb
    from chargedesk.data.snapshot import SNAPSHOT_VIEWS
    wh = tmp_path / "leaky.duckdb"
    con = duckdb.connect(str(wh))
    con.execute("create schema marts")
    con.execute("create table marts.dim_post as select 1 as post_id, 'A' as site, 'D' as district, "
                "date '2020-01-01' as first_day, date '2021-12-31' as last_session_day")
    con.execute("create table marts.dim_site as select 'A' as site, 'D' as district, 1 as n_posts")
    for name in SNAPSHOT_VIEWS:
        if name.startswith("fct_"):
            con.execute(f"create table marts.{name} (available_from date, outcome_known_from date, evening date, "
                        "episode_next_day boolean, n_hits int, n_unknown int, precision double)")
    con.close()
    snap = snapshot_connection(wh, E)
    cols = [r[0] for r in snap.execute("describe marts.dim_post").fetchall()]
    snap.close()
    assert cols == ["post_id", "site", "district", "first_day"]
