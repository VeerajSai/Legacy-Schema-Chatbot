from functools import lru_cache

from catalog.build_catalog import build_catalog, load_table_cards
from config.settings import TABLE_CARDS_PATH


@lru_cache(maxsize=1)
def _cards():
    if TABLE_CARDS_PATH.exists():
        return load_table_cards()
    return build_catalog()


def test_known_tables_present_with_description():
    cards = _cards()
    assert "cust_mst" in cards
    assert "ord_hdr" in cards
    assert cards["cust_mst"].description.strip() != ""
    assert cards["ord_hdr"].description.strip() != ""


def test_low_cardinality_columns_enumerated():
    cards = _cards()
    cust_type = next(c for c in cards["cust_mst"].columns if c.name == "cust_type")
    assert cust_type.distinct_values
    assert set(cust_type.distinct_values) == {"RETAIL", "WHOLESALE", "ONLINE"}

    status_cd = next(c for c in cards["ord_hdr"].columns if c.name == "status_cd")
    assert status_cd.distinct_values
    assert set(status_cd.distinct_values) == {"PLACED", "SHIPPED", "CANCELLED", "RETURNED"}
