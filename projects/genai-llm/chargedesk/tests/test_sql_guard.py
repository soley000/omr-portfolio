import pytest

from chargedesk.data.snapshot import snapshot_connection
from chargedesk.guards.sql import SQLRejected, check_sql, run_checked

ALLOWED = [
    "select sum(n_hw_faults) as v from marts.fct_post_day where site = 'Park A'",
    "with x as (select * from marts.dim_post) select count(*) from x",
]
REJECTED = [
    "delete from marts.fct_post_day",
    "drop table marts.dim_post",
    "update marts.dim_post set site = 'x'",
    "attach 'x.db' as y",
    "copy marts.dim_post to 'x.csv'",
    "select 1; select 2",
    "select * from marts.fct_post_signals",      # table d'entrainement : fuite
    "select * from wh.marts.fct_post_day",       # contourner la vue du soir
    "select * from read_csv('x.csv')",
    "select * from 'C:/secret.parquet'",
    "pragma show_tables",
]


@pytest.mark.parametrize("sql", ALLOWED)
def test_read_queries_on_marts_pass(sql):
    assert check_sql(sql) == sql


@pytest.mark.parametrize("sql", REJECTED)
def test_dangerous_or_leaky_queries_are_rejected(sql):
    with pytest.raises(SQLRejected):
        check_sql(sql)


def test_rows_are_capped_and_dated_values_serialized(fake_warehouse):
    from datetime import date
    con = snapshot_connection(fake_warehouse, date(2021, 10, 5))
    rows = run_checked(con, "select day from marts.fct_post_day")
    con.close()
    assert len(rows) == 200 and isinstance(rows[0]["day"], str)
