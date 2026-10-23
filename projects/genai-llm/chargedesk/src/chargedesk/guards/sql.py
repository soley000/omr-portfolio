"""Garde-fou SQL : seule une requete de lecture sur les tables autorisees passe.

La requete est analysee par sqlglot AVANT d'etre executee :
- une seule instruction, et c'est un SELECT (eventuellement avec WITH) ;
- toutes les tables lues sont dans le schema `marts` et dans la liste autorisee ;
- aucune fonction qui lit des fichiers ou d'autres bases (read_csv, attach...).
Elle est ensuite executee dans la vue "soir courant" (lecture seule), avec
un nombre de lignes plafonne.
"""
from __future__ import annotations

import sqlglot
from sqlglot import exp

ALLOWED_TABLES = {
    "dim_post", "dim_site", "fct_post_day", "fct_evening_list", "fct_post_evening",
    "fct_silent_alert", "fct_drift_month", "fct_list_daily_hits",
}
FORBIDDEN_FUNCTIONS = {"read_csv", "read_csv_auto", "read_parquet", "read_json", "read_json_auto",
                       "read_text", "read_blob", "glob", "sniff_csv", "query", "query_table"}
MAX_ROWS = 200


class SQLRejected(ValueError):
    pass


def check_sql(sql: str) -> str:
    """Renvoie la requete si elle est autorisee, sinon leve SQLRejected (message lisible par le LLM)."""
    try:
        statements = [s for s in sqlglot.parse(sql, read="duckdb") if s is not None]
    except sqlglot.errors.ParseError as exc:
        raise SQLRejected(f"requete illisible : {str(exc).splitlines()[0]}") from exc
    if len(statements) != 1:
        raise SQLRejected("une seule requete a la fois")
    tree = statements[0]
    if not isinstance(tree, (exp.Select, exp.Union, exp.Intersect, exp.Except)):
        raise SQLRejected("seules les requetes de lecture (SELECT) sont autorisees")
    for node in tree.walk():
        if isinstance(node, (exp.Insert, exp.Update, exp.Delete, exp.Drop, exp.Create, exp.Alter,
                             exp.Command, exp.Attach if hasattr(exp, "Attach") else exp.Command)):
            raise SQLRejected("seules les requetes de lecture (SELECT) sont autorisees")
        if isinstance(node, exp.Func):
            name = (node.sql_name() if hasattr(node, "sql_name") else "").lower()
            fname = node.name.lower() if isinstance(node, exp.Anonymous) else name
            if fname in FORBIDDEN_FUNCTIONS:
                raise SQLRejected(f"fonction interdite : {fname}")
    ctes = {c.alias_or_name.lower() for c in tree.find_all(exp.CTE)}
    for t in tree.find_all(exp.Table):
        name = t.name.lower()
        if not name or name in ctes:
            continue
        if isinstance(t.this, exp.Anonymous) or t.find(exp.Anonymous):
            raise SQLRejected("lecture de fichiers interdite")
        schema = (t.db or "").lower()
        if t.catalog or schema != "marts" or name not in ALLOWED_TABLES:
            raise SQLRejected(f"table non autorisee : {t.sql()} (tables permises : marts.{', marts.'.join(sorted(ALLOWED_TABLES))})")
    return sql


def run_checked(con, sql: str) -> list[dict]:
    """Verifie puis execute la requete ; renvoie au plus MAX_ROWS lignes sous forme de dictionnaires."""
    check_sql(sql)
    cur = con.execute(f"select * from ({sql.strip().rstrip(';')}) as q limit {MAX_ROWS}")
    cols = [d[0] for d in cur.description]
    rows = []
    for r in cur.fetchall():
        rows.append({c: (v.isoformat() if hasattr(v, "isoformat") else v) for c, v in zip(cols, r)})
    return rows
