"""Association rule mining using a lightweight FP-Growth implementation."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from itertools import combinations
from typing import Dict, List, Sequence, Tuple

from ..config import ModelConfig
from ..data.ingestion import OrderRecord


class FPNode:
    __slots__ = ("item", "count", "parent", "children", "link")

    def __init__(self, item: str | None, parent: "FPNode" | None) -> None:
        self.item = item
        self.count = 0
        self.parent = parent
        self.children: Dict[str, FPNode] = {}
        self.link: FPNode | None = None

    def increment(self, value: int) -> None:
        self.count += value


def build_transactions(orders: Sequence[OrderRecord]) -> List[List[str]]:
    transactions: Dict[str, List[str]] = {}
    for record in orders:
        transactions.setdefault(record.order_id, [])
        basket = transactions[record.order_id]
        if record.product_id not in basket:
            basket.append(record.product_id)
    return [sorted(items) for items in transactions.values()]


def _link_header(header_table: Dict[str, Dict[str, object]], item: str, node: FPNode) -> None:
    entry = header_table[item]
    if entry["head"] is None:
        entry["head"] = node
        entry["tail"] = node
    else:
        tail: FPNode = entry["tail"]  # type: ignore[assignment]
        tail.link = node
        entry["tail"] = node


def build_fp_tree(
    transactions: Sequence[Sequence[str]],
    min_support_count: int,
) -> Tuple[FPNode, Dict[str, Dict[str, object]]]:
    item_counter: Counter[str] = Counter()
    for transaction in transactions:
        item_counter.update(transaction)

    frequent_items = {item for item, count in item_counter.items() if count >= min_support_count}
    header_table: Dict[str, Dict[str, object]] = {
        item: {"support": item_counter[item], "head": None, "tail": None}
        for item in frequent_items
    }

    root = FPNode(item=None, parent=None)

    for transaction in transactions:
        filtered = [item for item in transaction if item in frequent_items]
        if not filtered:
            continue
        sorted_items = sorted(filtered, key=lambda item: (-item_counter[item], item))
        current = root
        for item in sorted_items:
            if item not in current.children:
                child = FPNode(item, current)
                current.children[item] = child
                _link_header(header_table, item, child)
            current = current.children[item]
            current.increment(1)

    return root, header_table


def ascend_path(node: FPNode) -> List[str]:
    path: List[str] = []
    current = node.parent
    while current and current.item is not None:
        path.append(current.item)
        current = current.parent
    path.reverse()
    return path


def mine_tree(
    header_table: Dict[str, Dict[str, object]],
    min_support_count: int,
    prefix: Tuple[str, ...],
    frequent_itemsets: Dict[Tuple[str, ...], int],
) -> None:
    for item in sorted(header_table.keys(), key=lambda i: header_table[i]["support"]):
        new_itemset = prefix + (item,)
        support = header_table[item]["support"]
        frequent_itemsets[new_itemset] = support  # type: ignore[arg-type]

        conditional_patterns: List[Tuple[List[str], int]] = []
        node: FPNode | None = header_table[item]["head"]  # type: ignore[assignment]
        while node is not None:
            path = ascend_path(node)
            if path:
                conditional_patterns.append((path, node.count))
            node = node.link

        if not conditional_patterns:
            continue

        transactions: List[List[str]] = []
        for path, count in conditional_patterns:
            for _ in range(count):
                transactions.append(path)

        _, conditional_header = build_fp_tree(transactions, min_support_count)
        if conditional_header:
            mine_tree(conditional_header, min_support_count, new_itemset, frequent_itemsets)


@dataclass
class AssociationRuleResult:
    itemsets: List[Dict[str, object]]
    rules: List[Dict[str, object]]


def generate_frequent_itemsets(transactions: List[List[str]], min_support: float) -> Dict[Tuple[str, ...], int]:
    if not transactions:
        return {}
    min_support_count = max(1, int(min_support * len(transactions)))
    _, header_table = build_fp_tree(transactions, min_support_count)
    frequent_itemsets: Dict[Tuple[str, ...], int] = {}
    mine_tree(header_table, min_support_count, tuple(), frequent_itemsets)
    for item, entry in header_table.items():
        frequent_itemsets.setdefault((item,), entry["support"])  # type: ignore[arg-type]
    return frequent_itemsets


def generate_association_rules(
    frequent_itemsets: Dict[Tuple[str, ...], int],
    total_transactions: int,
    min_confidence: float,
    min_lift: float,
) -> List[Dict[str, object]]:
    rows: List[Dict[str, object]] = []
    if total_transactions == 0:
        return rows
    support_lookup = {itemset: count / total_transactions for itemset, count in frequent_itemsets.items()}
    for itemset, support_count in frequent_itemsets.items():
        if len(itemset) < 2:
            continue
        itemset_support = support_lookup[itemset]
        for r in range(1, len(itemset)):
            for lhs in combinations(itemset, r):
                lhs = tuple(sorted(lhs))
                rhs = tuple(sorted(set(itemset) - set(lhs)))
                lhs_support = support_lookup.get(lhs)
                rhs_support = support_lookup.get(rhs)
                if lhs_support is None or rhs_support is None:
                    continue
                confidence = itemset_support / lhs_support if lhs_support else 0.0
                if confidence < min_confidence:
                    continue
                lift = confidence / rhs_support if rhs_support else 0.0
                if lift < min_lift:
                    continue
                rows.append(
                    {
                        "lhs": list(lhs),
                        "rhs": list(rhs),
                        "support": itemset_support,
                        "confidence": confidence,
                        "lift": lift,
                    }
                )
    rows.sort(key=lambda row: (row["confidence"], row["support"]), reverse=True)
    return rows


def mine_rules(orders: Sequence[OrderRecord], config: ModelConfig) -> AssociationRuleResult:
    transactions = build_transactions(orders)
    frequent_itemsets = generate_frequent_itemsets(transactions, config.min_support)
    itemsets = [
        {
            "itemset": list(itemset),
            "support": support_count / len(transactions) if transactions else 0.0,
        }
        for itemset, support_count in sorted(frequent_itemsets.items(), key=lambda x: (len(x[0]), x[0]))
    ]
    rules = generate_association_rules(
        frequent_itemsets,
        len(transactions),
        config.min_confidence,
        config.min_lift,
    )
    rules = generate_association_rules(frequent_itemsets, len(transactions), config.min_confidence)
    return AssociationRuleResult(itemsets=itemsets, rules=rules)


def top_rules_for_item(rules: List[Dict[str, object]], product_id: str, top_k: int) -> List[Dict[str, object]]:
    filtered = [rule for rule in rules if product_id in rule["lhs"]]
    return filtered[:top_k]
