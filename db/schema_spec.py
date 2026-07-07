"""Single source of truth for the synthetic legacy schema: ~74 cryptically-named
tables across 7 modules, with a deliberate mix of declared and undeclared FKs.

Two ways a table gets rows in generate_data.py:
- "fixed_rows": exact rows inserted verbatim (canonical lookup/code tables).
- "rows": int (fixed count) or ("scale", parent_table, lo, hi) meaning
  round(parent_row_count * uniform(lo, hi)) — used for header/detail tables so
  order counts, order-line counts, etc. scale together and stay referentially
  sane.

fk on a column is (ref_table, ref_column, declared: bool). declared=False is
what forces catalog/fk_inference.py to earn its keep.
"""
from __future__ import annotations


def C(name, dtype, *, pk=False, fk=None, enum=None, nullable=True):
    """fk = (ref_table, ref_column, declared_bool) or None."""
    return {"name": name, "dtype": dtype, "pk": pk, "fk": fk, "enum": enum, "nullable": nullable}


TABLES: dict[str, dict] = {
    # ---------------------------------------------------------------- core (6)
    "country_lkp": {
        "module": "core",
        "columns": [C("country_cd", "TEXT", pk=True), C("country_nm", "TEXT")],
        "fixed_rows": [
            {"country_cd": cd, "country_nm": nm} for cd, nm in [
                ("USA", "United States"), ("GBR", "United Kingdom"), ("CAN", "Canada"),
                ("AUS", "Australia"), ("DEU", "Germany"), ("FRA", "France"),
                ("IND", "India"), ("JPN", "Japan"), ("BRA", "Brazil"), ("MEX", "Mexico"),
            ]
        ],
    },
    "currency_lkp": {
        "module": "core",
        "columns": [C("currency_cd", "TEXT", pk=True), C("currency_nm", "TEXT"), C("symbol", "TEXT")],
        "fixed_rows": [
            {"currency_cd": "USD", "currency_nm": "US Dollar", "symbol": "$"},
            {"currency_cd": "GBP", "currency_nm": "British Pound", "symbol": "£"},
            {"currency_cd": "EUR", "currency_nm": "Euro", "symbol": "€"},
            {"currency_cd": "INR", "currency_nm": "Indian Rupee", "symbol": "₹"},
            {"currency_cd": "JPY", "currency_nm": "Japanese Yen", "symbol": "¥"},
        ],
    },
    "currency_rate_hist": {
        "module": "core",
        "columns": [
            C("rate_id", "INTEGER", pk=True),
            C("currency_cd", "TEXT", fk=("currency_lkp", "currency_cd", True)),
            C("rate_dt", "TEXT"), C("rate", "REAL"),
        ],
        "rows": 400,
    },
    "user_role_map": {
        "module": "core",
        "columns": [
            C("user_id", "INTEGER", pk=True), C("user_nm", "TEXT"),
            C("role_cd", "TEXT", enum=["admin", "sales_analyst", "finance_analyst", "hr_admin", "exec"]),
        ],
        "rows": 25,
    },
    "audit_log": {
        "module": "core",
        "columns": [
            C("audit_id", "INTEGER", pk=True),
            C("user_id", "INTEGER", fk=("user_role_map", "user_id", True)),
            C("action", "TEXT"), C("ts", "TEXT"),
        ],
        "rows": 2000,
    },
    "doc_attachment": {
        "module": "core",
        "columns": [
            C("attachment_id", "INTEGER", pk=True), C("entity_type", "TEXT"),
            C("entity_id", "INTEGER"), C("file_nm", "TEXT"),
        ],
        "rows": 500,
    },

    # -------------------------------------------------------------- sales (12)
    "region_lkp": {
        "module": "sales",
        "columns": [C("region_cd", "TEXT", pk=True), C("region_nm", "TEXT")],
        "fixed_rows": [
            {"region_cd": cd, "region_nm": nm} for cd, nm in [
                ("NA_EAST", "North America East"), ("NA_WEST", "North America West"),
                ("EMEA", "Europe, Middle East & Africa"), ("APAC", "Asia Pacific"),
                ("LATAM", "Latin America"),
            ]
        ],
    },
    "cust_mst": {
        "module": "sales",
        "columns": [
            C("cust_id", "INTEGER", pk=True), C("cust_nm", "TEXT"),
            C("cust_type", "TEXT", enum=["RETAIL", "WHOLESALE", "ONLINE"]),
            C("country_cd", "TEXT", fk=("country_lkp", "country_cd", True)),
        ],
        "rows": 600,
    },
    "cust_addr": {
        "module": "sales",
        "columns": [
            C("addr_id", "INTEGER", pk=True),
            C("cust_id", "INTEGER", fk=("cust_mst", "cust_id", True)),
            C("region_cd", "TEXT", fk=("region_lkp", "region_cd", True)),
            C("addr_line", "TEXT"), C("city", "TEXT"),
        ],
        "rows": ("scale", "cust_mst", 1.0, 1.4),
    },
    "sales_rep_map": {
        "module": "sales",
        "columns": [
            C("rep_id", "INTEGER", pk=True),
            C("emp_id", "INTEGER", fk=("employee", "emp_id", False)),
            C("territory_cd", "TEXT", fk=("region_lkp", "region_cd", True)),
        ],
        "rows": 60,
    },
    "ord_hdr": {
        "module": "sales",
        "columns": [
            C("ord_id", "INTEGER", pk=True),
            C("cust_id", "INTEGER", fk=("cust_mst", "cust_id", True)),
            C("sales_rep_id", "INTEGER", fk=("sales_rep_map", "rep_id", True)),
            C("order_dt", "TEXT"),
            C("status_cd", "TEXT", enum=["PLACED", "SHIPPED", "CANCELLED", "RETURNED"]),
            C("currency_cd", "TEXT", fk=("currency_lkp", "currency_cd", True)),
        ],
        "rows": 4000,
    },
    "ord_dtl_2": {
        "module": "sales",
        "columns": [
            C("ord_dtl_id", "INTEGER", pk=True),
            C("ord_id", "INTEGER", fk=("ord_hdr", "ord_id", True)),
            C("item_id", "INTEGER", fk=("item_mst", "item_id", False)),
            C("qty", "INTEGER"), C("unit_price", "REAL"),
            C("line_status", "TEXT", enum=["OPEN", "SHIPPED", "CANCELLED", "RETURNED"]),
        ],
        "rows": ("scale", "ord_hdr", 1.5, 3.5),
    },
    "ord_status_hist": {
        "module": "sales",
        "columns": [
            C("hist_id", "INTEGER", pk=True),
            C("ord_id", "INTEGER", fk=("ord_hdr", "ord_id", True)),
            C("status_cd", "TEXT", enum=["PLACED", "SHIPPED", "CANCELLED", "RETURNED"]),
            C("changed_dt", "TEXT"),
        ],
        "rows": ("scale", "ord_hdr", 1.0, 2.0),
    },
    "price_list": {
        "module": "sales",
        "columns": [
            C("price_list_id", "INTEGER", pk=True), C("price_list_nm", "TEXT"),
            C("currency_cd", "TEXT", fk=("currency_lkp", "currency_cd", True)),
        ],
        "rows": 10,
    },
    "price_list_itm": {
        "module": "sales",
        "columns": [
            C("price_itm_id", "INTEGER", pk=True),
            C("price_list_id", "INTEGER", fk=("price_list", "price_list_id", True)),
            C("item_id", "INTEGER", fk=("item_mst", "item_id", False)),
            C("unit_price", "REAL"),
        ],
        "rows": 1500,
    },
    "discount_cd": {
        "module": "sales",
        "columns": [C("discount_cd", "TEXT", pk=True), C("pct", "REAL")],
        "fixed_rows": [
            {"discount_cd": "NONE", "pct": 0.0}, {"discount_cd": "VOL5", "pct": 0.05},
            {"discount_cd": "VOL10", "pct": 0.10}, {"discount_cd": "LOYALTY", "pct": 0.15},
        ],
    },
    "sales_target": {
        "module": "sales",
        "columns": [
            C("target_id", "INTEGER", pk=True),
            C("sales_rep_id", "INTEGER", fk=("sales_rep_map", "rep_id", True)),
            C("period", "TEXT"), C("target_amt", "REAL"),
        ],
        "rows": 240,
    },
    "ord_return_hdr": {
        "module": "sales",
        "columns": [
            C("return_id", "INTEGER", pk=True),
            C("ord_id", "INTEGER", fk=("ord_hdr", "ord_id", True)),
            C("return_dt", "TEXT"),
            C("reason_cd", "TEXT", enum=["DEFECTIVE", "WRONG_ITEM", "CHANGED_MIND"]),
        ],
        "rows": 300,
    },

    # ---------------------------------------------------------- purchasing (12)
    "vendor_mst": {
        "module": "purchasing",
        "columns": [
            C("vendor_id", "INTEGER", pk=True), C("vendor_nm", "TEXT"),
            C("country_cd", "TEXT", fk=("country_lkp", "country_cd", True)),
        ],
        "rows": 250,
    },
    "vendor_contact": {
        "module": "purchasing",
        "columns": [
            C("contact_id", "INTEGER", pk=True),
            C("vendor_id", "INTEGER", fk=("vendor_mst", "vendor_id", True)),
            C("contact_nm", "TEXT"), C("email", "TEXT"),
        ],
        "rows": ("scale", "vendor_mst", 1.0, 1.5),
    },
    "vendor_bank_acct": {
        "module": "purchasing",
        "columns": [
            C("acct_id", "INTEGER", pk=True),
            C("vendor_id", "INTEGER", fk=("vendor_mst", "vendor_id", True)),
            C("iban", "TEXT"),
        ],
        "rows": ("scale", "vendor_mst", 0.8, 1.0),
    },
    "vendor_rating": {
        "module": "purchasing",
        "columns": [
            C("rating_id", "INTEGER", pk=True),
            C("vendor_id", "INTEGER", fk=("vendor_mst", "vendor_id", True)),
            C("rating_dt", "TEXT"), C("score", "INTEGER"),
        ],
        "rows": 600,
    },
    "po_hdr": {
        "module": "purchasing",
        "columns": [
            C("po_id", "INTEGER", pk=True),
            C("vendor_id", "INTEGER", fk=("vendor_mst", "vendor_id", True)),
            C("buyer_emp_id", "INTEGER", fk=("employee", "emp_id", False)),
            C("po_dt", "TEXT"),
            C("status_cd", "TEXT", enum=["DRAFT", "APPROVED", "RECEIVED", "CANCELLED"]),
            C("currency_cd", "TEXT", fk=("currency_lkp", "currency_cd", True)),
        ],
        "rows": 2200,
    },
    "po_dtl": {
        "module": "purchasing",
        "columns": [
            C("po_dtl_id", "INTEGER", pk=True),
            C("po_id", "INTEGER", fk=("po_hdr", "po_id", True)),
            C("item_id", "INTEGER", fk=("item_mst", "item_id", False)),
            C("qty", "INTEGER"), C("unit_cost", "REAL"),
        ],
        "rows": ("scale", "po_hdr", 1.5, 3.0),
    },
    "po_approval_hist": {
        "module": "purchasing",
        "columns": [
            C("approval_id", "INTEGER", pk=True),
            C("po_id", "INTEGER", fk=("po_hdr", "po_id", True)),
            C("approver_emp_id", "INTEGER", fk=("employee", "emp_id", False)),
            C("approved_dt", "TEXT"),
        ],
        "rows": ("scale", "po_hdr", 0.8, 1.2),
    },
    "po_receipt_hdr": {
        "module": "purchasing",
        "columns": [
            C("receipt_id", "INTEGER", pk=True),
            C("po_id", "INTEGER", fk=("po_hdr", "po_id", True)),
            C("receipt_dt", "TEXT"),
            C("whse_id", "INTEGER", fk=("whse_mst", "whse_id", False)),
        ],
        "rows": ("scale", "po_hdr", 0.7, 0.95),
    },
    "po_receipt_dtl": {
        "module": "purchasing",
        "columns": [
            C("receipt_dtl_id", "INTEGER", pk=True),
            C("receipt_id", "INTEGER", fk=("po_receipt_hdr", "receipt_id", True)),
            C("po_dtl_id", "INTEGER", fk=("po_dtl", "po_dtl_id", True)),
            C("qty_received", "INTEGER"),
        ],
        "rows": ("scale", "po_receipt_hdr", 1.5, 2.5),
    },
    "contract_mst": {
        "module": "purchasing",
        "columns": [
            C("contract_id", "INTEGER", pk=True),
            C("vendor_id", "INTEGER", fk=("vendor_mst", "vendor_id", True)),
            C("start_dt", "TEXT"), C("end_dt", "TEXT"),
        ],
        "rows": 180,
    },
    "contract_itm": {
        "module": "purchasing",
        "columns": [
            C("contract_itm_id", "INTEGER", pk=True),
            C("contract_id", "INTEGER", fk=("contract_mst", "contract_id", True)),
            C("item_id", "INTEGER", fk=("item_mst", "item_id", False)),
            C("contract_price", "REAL"),
        ],
        "rows": ("scale", "contract_mst", 2.0, 4.0),
    },
    "purchase_req": {
        "module": "purchasing",
        "columns": [
            C("req_id", "INTEGER", pk=True),
            C("requested_by_emp_id", "INTEGER", fk=("employee", "emp_id", False)),
            C("item_id", "INTEGER", fk=("item_mst", "item_id", False)),
            C("qty", "INTEGER"),
            C("status_cd", "TEXT", enum=["PENDING", "APPROVED", "REJECTED", "CONVERTED"]),
        ],
        "rows": 900,
    },

    # ----------------------------------------------------------- inventory (12)
    "whse_mst": {
        "module": "inventory",
        "columns": [
            C("whse_id", "INTEGER", pk=True), C("whse_nm", "TEXT"),
            C("region_cd", "TEXT", fk=("region_lkp", "region_cd", True)),
        ],
        "rows": 18,
    },
    "whse_loc": {
        "module": "inventory",
        "columns": [
            C("loc_id", "INTEGER", pk=True),
            C("whse_id", "INTEGER", fk=("whse_mst", "whse_id", True)),
            C("aisle", "TEXT"), C("bin", "TEXT"),
        ],
        "rows": ("scale", "whse_mst", 20.0, 30.0),
    },
    "item_uom": {
        "module": "inventory",
        "columns": [C("uom_cd", "TEXT", pk=True), C("uom_nm", "TEXT")],
        "fixed_rows": [
            {"uom_cd": "EA", "uom_nm": "Each"}, {"uom_cd": "CS", "uom_nm": "Case"},
            {"uom_cd": "KG", "uom_nm": "Kilogram"}, {"uom_cd": "LB", "uom_nm": "Pound"},
            {"uom_cd": "PLT", "uom_nm": "Pallet"},
        ],
    },
    "item_mst": {
        "module": "inventory",
        "columns": [
            C("item_id", "INTEGER", pk=True), C("item_nm", "TEXT"),
            C("uom_cd", "TEXT", fk=("item_uom", "uom_cd", True)), C("unit_wt", "REAL"),
        ],
        "rows": 1200,
    },
    "item_cat": {
        "module": "inventory",
        "columns": [C("cat_id", "INTEGER", pk=True), C("cat_nm", "TEXT")],
        "fixed_rows": [
            {"cat_id": i + 1, "cat_nm": nm} for i, nm in enumerate([
                "Electronics", "Apparel", "Hardware", "Packaging", "Raw Materials",
                "Office Supplies", "Perishables", "Furniture",
            ])
        ],
    },
    "item_cat_map": {
        "module": "inventory",
        "columns": [
            C("map_id", "INTEGER", pk=True),
            C("item_id", "INTEGER", fk=("item_mst", "item_id", True)),
            C("cat_id", "INTEGER", fk=("item_cat", "cat_id", True)),
        ],
        "rows": ("scale", "item_mst", 1.0, 1.2),
    },
    "stock_bal": {
        "module": "inventory",
        "columns": [
            C("stock_bal_id", "INTEGER", pk=True),
            C("item_id", "INTEGER", fk=("item_mst", "item_id", True)),
            C("whse_id", "INTEGER", fk=("whse_mst", "whse_id", True)),
            C("qty_on_hand", "INTEGER"),
        ],
        "rows": ("scale", "item_mst", 2.0, 3.0),
    },
    "stock_txn_hdr": {
        "module": "inventory",
        "columns": [
            C("txn_id", "INTEGER", pk=True),
            C("whse_id", "INTEGER", fk=("whse_mst", "whse_id", True)),
            C("txn_dt", "TEXT"),
            C("txn_type", "TEXT", enum=["RECEIPT", "SHIPMENT", "ADJUSTMENT", "TRANSFER"]),
        ],
        "rows": 3500,
    },
    "stock_txn_dtl": {
        "module": "inventory",
        "columns": [
            C("txn_dtl_id", "INTEGER", pk=True),
            C("txn_id", "INTEGER", fk=("stock_txn_hdr", "txn_id", True)),
            C("item_id", "INTEGER", fk=("item_mst", "item_id", True)),
            C("qty", "INTEGER"),
        ],
        "rows": ("scale", "stock_txn_hdr", 1.5, 2.5),
    },
    "reorder_rule": {
        "module": "inventory",
        "columns": [
            C("rule_id", "INTEGER", pk=True),
            C("item_id", "INTEGER", fk=("item_mst", "item_id", True)),
            C("whse_id", "INTEGER", fk=("whse_mst", "whse_id", True)),
            C("reorder_pt", "INTEGER"), C("reorder_qty", "INTEGER"),
        ],
        "rows": ("scale", "item_mst", 0.5, 0.8),
    },
    "cycle_count_hdr": {
        "module": "inventory",
        "columns": [
            C("count_id", "INTEGER", pk=True),
            C("whse_id", "INTEGER", fk=("whse_mst", "whse_id", True)),
            C("count_dt", "TEXT"),
        ],
        "rows": 200,
    },
    "cycle_count_dtl": {
        "module": "inventory",
        "columns": [
            C("count_dtl_id", "INTEGER", pk=True),
            C("count_id", "INTEGER", fk=("cycle_count_hdr", "count_id", True)),
            C("item_id", "INTEGER", fk=("item_mst", "item_id", True)),
            C("counted_qty", "INTEGER"), C("system_qty", "INTEGER"),
        ],
        "rows": ("scale", "cycle_count_hdr", 8.0, 15.0),
    },

    # ------------------------------------------------------------------ hr (10)
    "employee": {
        "module": "hr",
        "columns": [
            C("emp_id", "INTEGER", pk=True), C("emp_nm", "TEXT"), C("hire_dt", "TEXT"),
            C("country_cd", "TEXT", fk=("country_lkp", "country_cd", True)),
        ],
        "rows": 350,
    },
    "department": {
        "module": "hr",
        "columns": [
            C("dept_id", "INTEGER", pk=True), C("dept_nm", "TEXT"),
            C("manager_emp_id", "INTEGER", fk=("employee", "emp_id", True)),
        ],
        "rows": 22,
    },
    "emp_dept_assign": {
        "module": "hr",
        "columns": [
            C("assign_id", "INTEGER", pk=True),
            C("emp_id", "INTEGER", fk=("employee", "emp_id", True)),
            C("dept_id", "INTEGER", fk=("department", "dept_id", True)),
        ],
        "rows": ("scale", "employee", 1.0, 1.1),
    },
    "position_mst": {
        "module": "hr",
        "columns": [
            C("position_id", "INTEGER", pk=True), C("position_nm", "TEXT"),
            C("dept_id", "INTEGER", fk=("department", "dept_id", True)),
        ],
        "rows": 80,
    },
    "emp_position_hist": {
        "module": "hr",
        "columns": [
            C("hist_id", "INTEGER", pk=True),
            C("emp_id", "INTEGER", fk=("employee", "emp_id", True)),
            C("position_id", "INTEGER", fk=("position_mst", "position_id", True)),
            C("start_dt", "TEXT"), C("end_dt", "TEXT", nullable=True),
        ],
        "rows": ("scale", "employee", 1.2, 1.6),
    },
    "payroll_run": {
        "module": "hr",
        "columns": [C("run_id", "INTEGER", pk=True), C("run_dt", "TEXT"), C("period", "TEXT")],
        "rows": 36,
    },
    "payroll_dtl": {
        "module": "hr",
        "columns": [
            C("payroll_dtl_id", "INTEGER", pk=True),
            C("run_id", "INTEGER", fk=("payroll_run", "run_id", True)),
            C("emp_id", "INTEGER", fk=("employee", "emp_id", True)),
            C("gross_amt", "REAL"), C("net_amt", "REAL"),
        ],
        "rows": ("scale", "payroll_run", 300.0, 350.0),
    },
    "leave_type_lkp": {
        "module": "hr",
        "columns": [C("leave_type_cd", "TEXT", pk=True), C("leave_type_nm", "TEXT")],
        "fixed_rows": [
            {"leave_type_cd": "VAC", "leave_type_nm": "Vacation"},
            {"leave_type_cd": "SICK", "leave_type_nm": "Sick Leave"},
            {"leave_type_cd": "PARENT", "leave_type_nm": "Parental Leave"},
            {"leave_type_cd": "UNPAID", "leave_type_nm": "Unpaid Leave"},
        ],
    },
    "leave_request": {
        "module": "hr",
        "columns": [
            C("leave_id", "INTEGER", pk=True),
            C("emp_id", "INTEGER", fk=("employee", "emp_id", True)),
            C("leave_type_cd", "TEXT", fk=("leave_type_lkp", "leave_type_cd", True)),
            C("start_dt", "TEXT"), C("end_dt", "TEXT"),
            C("status_cd", "TEXT", enum=["PENDING", "APPROVED", "DENIED"]),
        ],
        "rows": ("scale", "employee", 2.0, 3.0),
    },
    "emp_skill_map": {
        "module": "hr",
        "columns": [
            C("skill_id", "INTEGER", pk=True),
            C("emp_id", "INTEGER", fk=("employee", "emp_id", True)),
            C("skill_nm", "TEXT"),
        ],
        "rows": ("scale", "employee", 1.5, 2.5),
    },

    # ------------------------------------------------------------- finance (12)
    "gl_account": {
        "module": "finance",
        "columns": [
            C("gl_acct_id", "INTEGER", pk=True), C("acct_nm", "TEXT"),
            C("acct_type", "TEXT", enum=["ASSET", "LIABILITY", "EQUITY", "REVENUE", "EXPENSE"]),
        ],
        "rows": 60,
    },
    "cost_center": {
        "module": "finance",
        "columns": [
            C("cost_center_id", "INTEGER", pk=True), C("cost_center_nm", "TEXT"),
            C("dept_id", "INTEGER", fk=("department", "dept_id", False)),
        ],
        "rows": 22,
    },
    "fiscal_period": {
        "module": "finance",
        "columns": [C("fiscal_period_id", "INTEGER", pk=True), C("period_nm", "TEXT"),
                    C("start_dt", "TEXT"), C("end_dt", "TEXT")],
        "fixed_rows": [
            {"fiscal_period_id": i + 1, "period_nm": f"2024-{i+1:02d}",
             "start_dt": f"2024-{i+1:02d}-01", "end_dt": f"2024-{i+1:02d}-28"}
            for i in range(24)
        ],
    },
    "gl_txn_hdr": {
        "module": "finance",
        "columns": [
            C("gl_txn_id", "INTEGER", pk=True), C("gl_txn_dt", "TEXT"),
            C("fiscal_period_id", "INTEGER", fk=("fiscal_period", "fiscal_period_id", True)),
            C("cost_center_id", "INTEGER", fk=("cost_center", "cost_center_id", True)),
        ],
        "rows": 3000,
    },
    "gl_txn_dtl": {
        "module": "finance",
        "columns": [
            C("gl_txn_dtl_id", "INTEGER", pk=True),
            C("gl_txn_id", "INTEGER", fk=("gl_txn_hdr", "gl_txn_id", True)),
            C("gl_acct_id", "INTEGER", fk=("gl_account", "gl_acct_id", True)),
            C("amt", "REAL"),
        ],
        "rows": ("scale", "gl_txn_hdr", 1.8, 2.5),
    },
    "invoice_hdr": {
        "module": "finance",
        "columns": [
            C("invoice_id", "INTEGER", pk=True),
            C("cust_id", "INTEGER", fk=("cust_mst", "cust_id", False)),
            C("ord_id", "INTEGER", fk=("ord_hdr", "ord_id", False)),
            C("invoice_dt", "TEXT"), C("total_amt", "REAL"),
            C("currency_cd", "TEXT", fk=("currency_lkp", "currency_cd", True)),
        ],
        "rows": ("scale", "ord_hdr", 0.85, 0.98),
    },
    "invoice_dtl": {
        "module": "finance",
        "columns": [
            C("invoice_dtl_id", "INTEGER", pk=True),
            C("invoice_id", "INTEGER", fk=("invoice_hdr", "invoice_id", True)),
            C("ord_dtl_id", "INTEGER", fk=("ord_dtl_2", "ord_dtl_id", False)),
            C("amt", "REAL"),
        ],
        "rows": ("scale", "invoice_hdr", 1.5, 3.0),
    },
    "payment_hdr": {
        "module": "finance",
        "columns": [
            C("payment_id", "INTEGER", pk=True),
            C("cust_id", "INTEGER", fk=("cust_mst", "cust_id", False)),
            C("payment_dt", "TEXT"), C("amt", "REAL"),
        ],
        "rows": ("scale", "invoice_hdr", 0.7, 0.9),
    },
    "payment_alloc": {
        "module": "finance",
        "columns": [
            C("alloc_id", "INTEGER", pk=True),
            C("payment_id", "INTEGER", fk=("payment_hdr", "payment_id", True)),
            C("invoice_id", "INTEGER", fk=("invoice_hdr", "invoice_id", True)),
            C("alloc_amt", "REAL"),
        ],
        "rows": ("scale", "payment_hdr", 1.0, 1.3),
    },
    "budget_line": {
        "module": "finance",
        "columns": [
            C("budget_line_id", "INTEGER", pk=True),
            C("cost_center_id", "INTEGER", fk=("cost_center", "cost_center_id", True)),
            C("fiscal_period_id", "INTEGER", fk=("fiscal_period", "fiscal_period_id", True)),
            C("budget_amt", "REAL"),
        ],
        "rows": ("scale", "cost_center", 20.0, 24.0),
    },
    "tax_code": {
        "module": "finance",
        "columns": [C("tax_cd", "TEXT", pk=True), C("tax_nm", "TEXT"), C("rate", "REAL")],
        "fixed_rows": [
            {"tax_cd": "STD", "tax_nm": "Standard Rate", "rate": 0.20},
            {"tax_cd": "REDUCED", "tax_nm": "Reduced Rate", "rate": 0.05},
            {"tax_cd": "ZERO", "tax_nm": "Zero Rate", "rate": 0.0},
        ],
    },
    "expense_report": {
        "module": "finance",
        "columns": [
            C("expense_id", "INTEGER", pk=True),
            C("emp_id", "INTEGER", fk=("employee", "emp_id", False)),
            C("amt", "REAL"),
            C("status_cd", "TEXT", enum=["PENDING", "APPROVED", "REIMBURSED"]),
        ],
        "rows": ("scale", "employee", 1.0, 1.5),
    },

    # ----------------------------------------------------------------- crm (10)
    "account": {
        "module": "crm",
        "columns": [
            C("account_id", "INTEGER", pk=True), C("account_nm", "TEXT"),
            C("cust_id", "INTEGER", fk=("cust_mst", "cust_id", False)),
        ],
        "rows": ("scale", "cust_mst", 0.6, 0.8),
    },
    "contact": {
        "module": "crm",
        "columns": [C("contact_id", "INTEGER", pk=True), C("contact_nm", "TEXT"), C("email", "TEXT")],
        "rows": 900,
    },
    "account_contact_map": {
        "module": "crm",
        "columns": [
            C("map_id", "INTEGER", pk=True),
            C("account_id", "INTEGER", fk=("account", "account_id", True)),
            C("contact_id", "INTEGER", fk=("contact", "contact_id", True)),
        ],
        "rows": ("scale", "contact", 0.9, 1.0),
    },
    "lead": {
        "module": "crm",
        "columns": [
            C("lead_id", "INTEGER", pk=True), C("lead_nm", "TEXT"),
            C("source_cd", "TEXT", enum=["WEB", "REFERRAL", "EVENT", "COLD_CALL"]),
            C("status_cd", "TEXT", enum=["NEW", "QUALIFIED", "DISQUALIFIED", "CONVERTED"]),
        ],
        "rows": 1100,
    },
    "opportunity": {
        "module": "crm",
        "columns": [
            C("opp_id", "INTEGER", pk=True),
            C("account_id", "INTEGER", fk=("account", "account_id", True)),
            C("lead_id", "INTEGER", fk=("lead", "lead_id", True)),
            C("amt", "REAL"),
            C("stage_cd", "TEXT", enum=["PROSPECTING", "PROPOSAL", "NEGOTIATION", "CLOSED_WON", "CLOSED_LOST"]),
        ],
        "rows": 700,
    },
    "opportunity_stage_hist": {
        "module": "crm",
        "columns": [
            C("hist_id", "INTEGER", pk=True),
            C("opp_id", "INTEGER", fk=("opportunity", "opp_id", True)),
            C("stage_cd", "TEXT", enum=["PROSPECTING", "PROPOSAL", "NEGOTIATION", "CLOSED_WON", "CLOSED_LOST"]),
            C("changed_dt", "TEXT"),
        ],
        "rows": ("scale", "opportunity", 1.5, 2.5),
    },
    "campaign": {
        "module": "crm",
        "columns": [C("campaign_id", "INTEGER", pk=True), C("campaign_nm", "TEXT"),
                    C("start_dt", "TEXT"), C("end_dt", "TEXT")],
        "rows": 45,
    },
    "campaign_member_map": {
        "module": "crm",
        "columns": [
            C("member_id", "INTEGER", pk=True),
            C("campaign_id", "INTEGER", fk=("campaign", "campaign_id", True)),
            C("contact_id", "INTEGER", fk=("contact", "contact_id", True)),
        ],
        "rows": ("scale", "campaign", 15.0, 25.0),
    },
    "interaction_log": {
        "module": "crm",
        "columns": [
            C("interaction_id", "INTEGER", pk=True),
            C("contact_id", "INTEGER", fk=("contact", "contact_id", True)),
            C("rep_emp_id", "INTEGER", fk=("employee", "emp_id", False)),
            C("interaction_dt", "TEXT"),
            C("channel_cd", "TEXT", enum=["EMAIL", "PHONE", "MEETING"]),
        ],
        "rows": ("scale", "contact", 1.5, 2.5),
    },
    "support_ticket": {
        "module": "crm",
        "columns": [
            C("ticket_id", "INTEGER", pk=True),
            C("account_id", "INTEGER", fk=("account", "account_id", True)),
            C("opened_dt", "TEXT"),
            C("status_cd", "TEXT", enum=["OPEN", "IN_PROGRESS", "RESOLVED", "CLOSED"]),
        ],
        "rows": ("scale", "account", 0.8, 1.5),
    },
}

MODULES = sorted({spec["module"] for spec in TABLES.values()})

# doc's disjoint-path trap: two real, declared, semantically-different paths
# between the same node pair. graph_expand.py must surface both.
DISJOINT_PATH_PAIRS = [
    (("department", "manager_emp_id", "employee", "emp_id", "manages"),
     ("emp_dept_assign", "emp_id", "dept_id", "works_in")),
]

# a couple of legacy tables get intentionally mixed-case categorical values
# (doc's "#1 silent failure": WHERE status = 'shipped' vs stored 'SHIPPED')
MIXED_CASE_TABLES = {"ord_dtl_2": "line_status", "ord_status_hist": "status_cd"}
