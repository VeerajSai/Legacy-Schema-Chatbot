import json
from pathlib import Path

import networkx as nx
import pytest

from contracts.types import TableCard

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def table_cards() -> dict[str, TableCard]:
    with open(FIXTURES / "mini_table_cards.json", encoding="utf-8") as f:
        raw = json.load(f)
    return {d["table"]: TableCard.from_dict(d) for d in raw}


@pytest.fixture
def join_graph() -> nx.Graph:
    with open(FIXTURES / "mini_join_graph.json", encoding="utf-8") as f:
        data = json.load(f)
    return nx.node_link_graph(data, edges="links")
