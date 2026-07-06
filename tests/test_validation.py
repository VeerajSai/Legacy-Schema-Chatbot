from contracts.types import ColumnCard, TableCard
from pipeline.validation import validate_sql

ORD_HDR_CARD = TableCard(
    table="ord_hdr",
    module="sales",
    description="Order headers",
    row_count=4000,
    columns=[
        ColumnCard(name="ord_id", dtype="INTEGER", is_pk=True),
        ColumnCard(name="cust_id", dtype="INTEGER"),
        ColumnCard(name="sales_rep_id", dtype="INTEGER"),
        ColumnCard(name="order_dt", dtype="TEXT"),
        ColumnCard(name="status_cd", dtype="TEXT"),
        ColumnCard(name="currency_cd", dtype="TEXT"),
    ],
)


def test_rejects_delete_statement():
    result = validate_sql("DELETE FROM ord_hdr WHERE ord_id = 1", {"ord_hdr": ORD_HDR_CARD}, "admin")
    assert not result.is_valid
    assert any("SELECT" in e for e in result.errors)


def test_rejects_drop_statement():
    result = validate_sql("DROP TABLE ord_hdr", {"ord_hdr": ORD_HDR_CARD}, "admin")
    assert not result.is_valid


def test_auto_injects_limit_on_plain_select():
    sql = "SELECT o.ord_id, o.status_cd FROM ord_hdr o"
    result = validate_sql(sql, {"ord_hdr": ORD_HDR_CARD}, "admin")
    assert result.is_valid, result.errors
    assert result.repaired_sql is not None
    assert "LIMIT" in result.repaired_sql.upper()


def test_pure_aggregation_does_not_need_limit():
    sql = "SELECT COUNT(*) FROM ord_hdr"
    result = validate_sql(sql, {"ord_hdr": ORD_HDR_CARD}, "admin")
    assert result.is_valid, result.errors
    assert result.repaired_sql is None


def test_flags_hallucinated_table():
    sql = "SELECT x.foo FROM not_a_real_table x"
    result = validate_sql(sql, {"ord_hdr": ORD_HDR_CARD}, "admin")
    assert not result.is_valid
    assert any("not_a_real_table" in e for e in result.errors)


def test_flags_hallucinated_column():
    sql = "SELECT o.made_up_column FROM ord_hdr o"
    result = validate_sql(sql, {"ord_hdr": ORD_HDR_CARD}, "admin")
    assert not result.is_valid
    assert any("made_up_column" in e for e in result.errors)
