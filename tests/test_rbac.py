from contracts.rbac import allowed_modules
from contracts.types import ColumnCard, TableCard
from pipeline.validation import validate_sql

HR_ONLY_TABLE = TableCard(
    table="employee_secret",
    module="hr",
    description="Employee records",
    row_count=10,
    columns=[ColumnCard(name="emp_id", dtype="INTEGER", is_pk=True), ColumnCard(name="salary", dtype="REAL")],
)


def test_rejects_table_outside_role_modules():
    # sales_analyst's allowed modules are {sales, crm, inventory, core} — no "hr".
    sql = "SELECT e.emp_id FROM employee_secret e"
    result = validate_sql(sql, {"employee_secret": HR_ONLY_TABLE}, "sales_analyst")
    assert not result.is_valid
    assert any("RBAC" in e for e in result.errors)


def test_allows_table_inside_role_modules():
    sql = "SELECT e.emp_id FROM employee_secret e"
    result = validate_sql(sql, {"employee_secret": HR_ONLY_TABLE}, "hr_admin")
    # hr_admin has module "hr" -> passes RBAC (may still fail EXPLAIN since the
    # table doesn't exist in the real DB, but must NOT fail for RBAC reasons).
    assert not any("RBAC" in e for e in result.errors)


def test_unknown_role_denies_all():
    assert allowed_modules("nonexistent_role") == set()
