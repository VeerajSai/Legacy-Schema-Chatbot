"""Single source of truth for paths, model names, and thresholds.

Nothing below should be hardcoded again at call sites — import from here.
"""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

DB_PATH = ROOT / "data" / "legacy.db"
DB_SEED = 42

CATALOG_DIR = ROOT / "catalog" / "artifacts"
TABLE_CARDS_PATH = CATALOG_DIR / "table_cards.json"
JOIN_GRAPH_PATH = CATALOG_DIR / "join_graph.json"
GLOSSARY_PATH = CATALOG_DIR / "glossary.json"
FEWSHOT_BANK_PATH = CATALOG_DIR / "fewshot_bank.json"
DESCRIBE_CACHE_PATH = CATALOG_DIR / "describe_cache.json"

RBAC_CONFIG_PATH = ROOT / "config" / "rbac.yaml"

GOLDEN_SET_PATH = ROOT / "eval" / "golden_set.jsonl"
GOLDEN_SET_RESOLVED_PATH = ROOT / "eval" / "golden_set_resolved.jsonl"

CACHE_DB_PATH = ROOT / "data" / "cache.db"
PIPELINE_LOG_PATH = ROOT / "logs" / "pipeline.jsonl"

# --- LLM model routing (doc section 4, stage-routing rule) ---
# Cheap model: stages 2 (query understanding) and 10 (answer synthesis), plus
# the one-time offline table/column description pass.
# Strong model: stage 7 (SQL generation) only.
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "anthropic")
MODEL_CHEAP = os.environ.get("NL2SQL_MODEL_CHEAP", "claude-haiku-4-5-20251001")
MODEL_STRONG = os.environ.get("NL2SQL_MODEL_STRONG", "claude-sonnet-5")

# --- retrieval ---
DENSE_MODEL_NAME = "all-MiniLM-L6-v2"
CROSS_ENCODER_NAME = "cross-encoder/ms-marco-MiniLM-L-6-v2"
RETRIEVAL_UNION_TOP_N = 15     # top-N from each of BM25/dense before rerank
RETRIEVAL_FINAL_TOP_K = 8      # tables kept after cross-encoder rerank

# --- cataloging ---
LOW_CARDINALITY_THRESHOLD = 50  # columns with < this many distinct values get enumerated

# --- cache ---
SEMANTIC_CACHE_THRESHOLD = 0.95
EXACT_CACHE_TTL_SECONDS = {"operational": 300, "historical": 86400}

# --- execution / repair ---
MAX_REPAIR_RETRIES = 2
EXECUTION_ROW_CAP = 10_000
EXECUTION_TIMEOUT_SECONDS = 30

# --- eval ---
TABLE_RECALL_TARGET = 0.95
