"""Hand-authored business-jargon -> table synonyms. Static domain knowledge,
no LLM needed (ladder rung 3: a dict is enough)."""
from __future__ import annotations

import json
from pathlib import Path

from config.settings import GLOSSARY_PATH

# business term -> tables it refers to
GLOSSARY: dict[str, list[str]] = {
    "revenue": ["gl_account", "invoice_hdr", "gl_txn_dtl"],
    "sales": ["ord_hdr", "ord_dtl_2"],
    "orders": ["ord_hdr", "ord_dtl_2"],
    "order lines": ["ord_dtl_2"],
    "customers": ["cust_mst"],
    "clients": ["cust_mst"],
    "buyers": ["cust_mst"],
    "products": ["item_mst"],
    "sku": ["item_mst"],
    "skus": ["item_mst"],
    "items": ["item_mst"],
    "staff": ["employee"],
    "employees": ["employee"],
    "personnel": ["employee"],
    "workers": ["employee"],
    "vendors": ["vendor_mst"],
    "suppliers": ["vendor_mst"],
    "purchase orders": ["po_hdr", "po_dtl"],
    "pos": ["po_hdr", "po_dtl"],
    "invoices": ["invoice_hdr", "invoice_dtl"],
    "billing": ["invoice_hdr", "invoice_dtl"],
    "payments": ["payment_hdr", "payment_alloc"],
    "receipts": ["po_receipt_hdr", "po_receipt_dtl"],
    "warehouses": ["whse_mst"],
    "inventory": ["stock_bal", "stock_txn_hdr", "stock_txn_dtl"],
    "stock": ["stock_bal", "stock_txn_hdr"],
    "stock levels": ["stock_bal"],
    "departments": ["department"],
    "org chart": ["department", "emp_dept_assign"],
    "managers": ["department", "employee"],
    "opportunities": ["opportunity"],
    "deals": ["opportunity"],
    "leads": ["lead"],
    "accounts": ["account"],
    "contacts": ["contact"],
    "campaigns": ["campaign"],
    "support tickets": ["support_ticket"],
    "tickets": ["support_ticket"],
    "budget": ["budget_line"],
    "budgets": ["budget_line"],
    "payroll": ["payroll_run", "payroll_dtl"],
    "salary": ["payroll_dtl"],
    "wages": ["payroll_dtl"],
    "leave": ["leave_request"],
    "time off": ["leave_request"],
    "vacation": ["leave_request"],
    "contracts": ["contract_mst", "contract_itm"],
    "returns": ["ord_return_hdr"],
    "regions": ["region_lkp"],
    "territories": ["region_lkp", "sales_rep_map"],
    "currency": ["currency_lkp", "currency_rate_hist"],
    "exchange rate": ["currency_rate_hist"],
    "tax": ["tax_code"],
    "cost centers": ["cost_center"],
    "general ledger": ["gl_account", "gl_txn_hdr", "gl_txn_dtl"],
    "gl": ["gl_account", "gl_txn_hdr", "gl_txn_dtl"],
    "expenses": ["expense_report"],
    "reimbursement": ["expense_report"],
    "sales reps": ["sales_rep_map"],
    "quotas": ["sales_target"],
    "targets": ["sales_target"],
    "price list": ["price_list", "price_list_itm"],
    "pricing": ["price_list", "price_list_itm"],
    "discounts": ["discount_cd"],
    "categories": ["item_cat", "item_cat_map"],
    "positions": ["position_mst"],
    "job titles": ["position_mst", "emp_position_hist"],
    "skills": ["emp_skill_map"],
    "audit trail": ["audit_log"],
    "attachments": ["doc_attachment"],
    "documents": ["doc_attachment"],
    "users": ["user_role_map"],
    "roles": ["user_role_map"],
    "cycle counts": ["cycle_count_hdr", "cycle_count_dtl"],
    "reorder": ["reorder_rule"],
    "vendor rating": ["vendor_rating"],
    "bank accounts": ["vendor_bank_acct"],
}


def table_synonyms() -> dict[str, list[str]]:
    """Inverts GLOSSARY into {table: [terms]}."""
    out: dict[str, list[str]] = {}
    for term, tables in GLOSSARY.items():
        for t in tables:
            out.setdefault(t, []).append(term)
    return out


def build_glossary(path=GLOSSARY_PATH) -> dict[str, list[str]]:
    syns = table_synonyms()
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(syns, indent=2))
    return syns
