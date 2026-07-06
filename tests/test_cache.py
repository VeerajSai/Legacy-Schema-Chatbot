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
