import sqlite3

import pipeline.cache as cache


def test_exact_cache_hit_same_role(tmp_path, monkeypatch):
    monkeypatch.setattr(cache, "CACHE_DB_PATH", tmp_path / "cache.db")
    cache.cache_store("How many orders are there?", "sales_analyst", "SELECT COUNT(*) FROM ord_hdr")

    tier, sql = cache.cache_lookup("How many orders are there?", "sales_analyst")
    assert tier == "exact"
    assert sql == "SELECT COUNT(*) FROM ord_hdr"


def test_exact_cache_not_shared_across_roles(tmp_path, monkeypatch):
    monkeypatch.setattr(cache, "CACHE_DB_PATH", tmp_path / "cache.db")
    cache.cache_store("How many orders are there?", "admin", "SELECT COUNT(*) FROM ord_hdr")

    tier, sql = cache.cache_lookup("How many orders are there?", "sales_analyst")
    assert (tier, sql) == (None, None)


def test_semantic_cache_hit_on_paraphrase(tmp_path, monkeypatch):
    monkeypatch.setattr(cache, "CACHE_DB_PATH", tmp_path / "cache.db")
    cache.cache_store(
        "what is the total order value by customer", "sales_analyst",
        "SELECT cust_id, SUM(net_amt) FROM ord_hdr GROUP BY cust_id",
    )

    tier, sql = cache.cache_lookup("what is total order value per customer", "sales_analyst")
    assert tier == "semantic"
    assert sql == "SELECT cust_id, SUM(net_amt) FROM ord_hdr GROUP BY cust_id"


def test_template_cache_does_not_collapse_absolute_months(tmp_path, monkeypatch):
    monkeypatch.setattr(cache, "CACHE_DB_PATH", tmp_path / "cache.db")
    cache.cache_store(
        "sales in january", "sales_analyst",
        "SELECT * FROM ord_hdr WHERE month = 'January'",
    )

    tier, sql = cache.cache_lookup("sales in march", "sales_analyst")
    assert (tier, sql) == (None, None)


def test_template_cache_expires_after_ttl(tmp_path, monkeypatch):
    db_path = tmp_path / "cache.db"
    monkeypatch.setattr(cache, "CACHE_DB_PATH", db_path)
    cache.cache_store("sales last quarter", "sales_analyst", "SELECT * FROM ord_hdr")

    # simulate both exact and template entries having aged past their TTL
    conn = sqlite3.connect(db_path)
    conn.execute("UPDATE exact_cache SET created_at = 0")
    conn.execute("UPDATE template_cache SET created_at = 0")
    conn.commit()
    conn.close()

    tier, _sql = cache.cache_lookup("sales last quarter", "sales_analyst")
    assert tier != "template"
