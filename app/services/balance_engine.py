"""Pure balance logic: no database, no HTTP. Everything is integer paise.

Concepts (kept separate on purpose):
  * Pairwise balances  - the real "who owes whom" derived from expense history.
  * Net balances       - one signed number per person (positive = is owed money).
  * Settlement plan    - a *suggested* shorter list of payments that clears all net balances.
"""
import heapq
from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class Debt:
    """`debtor` owes `creditor` `amount_paise`."""

    debtor: int
    creditor: int
    amount_paise: int


def split_equally(amount_paise: int, member_ids: Iterable[int]) -> dict[int, int]:
    """Split an amount equally; remainder paise go one each to the lowest user ids.

    Invariants: shares sum exactly to amount_paise, and any two shares differ by at most 1 paisa.
    Deterministic: depends only on the amount and the *set* of member ids.
    """
    members = sorted(set(member_ids))
    if not members:
        raise ValueError("cannot split among zero members")
    base, remainder = divmod(amount_paise, len(members))
    return {uid: base + (1 if i < remainder else 0) for i, uid in enumerate(members)}


def pairwise_balances(debts: Iterable[Debt]) -> list[Debt]:
    """Combine raw debts per pair and cancel opposite directions.

    A owes B 700 and B owes A 300  ->  A owes B 400.  Zero results are dropped.
    Output is sorted by (debtor, creditor) so it is deterministic.  O(n log n).
    """
    directed: dict[tuple[int, int], int] = defaultdict(int)
    for d in debts:
        if d.debtor != d.creditor and d.amount_paise > 0:
            directed[(d.debtor, d.creditor)] += d.amount_paise

    result: list[Debt] = []
    for (a, b), a_to_b in directed.items():
        if a > b and (b, a) in directed:
            continue  # the pair is handled once, from the smaller id's side
        net = a_to_b - directed.get((b, a), 0)
        if net > 0:
            result.append(Debt(debtor=a, creditor=b, amount_paise=net))
        elif net < 0:
            result.append(Debt(debtor=b, creditor=a, amount_paise=-net))
    return sorted(result, key=lambda d: (d.debtor, d.creditor))


def net_balances(debts: Iterable[Debt]) -> dict[int, int]:
    """Signed net per user: positive = is owed money, negative = owes money. Zeros dropped.

    The values always sum to 0 because every debt adds +x to one user and -x to another.
    """
    net: dict[int, int] = defaultdict(int)
    for d in debts:
        net[d.creditor] += d.amount_paise
        net[d.debtor] -= d.amount_paise
    return {uid: v for uid, v in sorted(net.items()) if v != 0}


def suggest_settlements(net: dict[int, int]) -> list[Debt]:
    """Greedy settlement: repeatedly match the largest debtor with the largest creditor.

    Each step fully clears at least one person, so at most (people with a non-zero balance - 1)
    payments are produced.  Ties are broken by user id, so output is deterministic.
    Not guaranteed minimal (that is NP-hard in general) but never worse than n-1.  O(n log n).
    """
    if sum(net.values()) != 0:
        raise ValueError("net balances must sum to zero")

    # heapq is a min-heap, so amounts are stored negated: the largest amount pops first,
    # and the lowest user id wins ties because the id is the second tuple element.
    debtor_heap = [(v, uid) for uid, v in net.items() if v < 0]  # v is already negative
    creditor_heap = [(-v, uid) for uid, v in net.items() if v > 0]
    heapq.heapify(debtor_heap)
    heapq.heapify(creditor_heap)

    payments: list[Debt] = []
    while debtor_heap and creditor_heap:
        neg_owed, debtor = heapq.heappop(debtor_heap)
        neg_credit, creditor = heapq.heappop(creditor_heap)
        owed, credit = -neg_owed, -neg_credit
        transfer = min(owed, credit)
        payments.append(Debt(debtor=debtor, creditor=creditor, amount_paise=transfer))
        if owed > transfer:
            heapq.heappush(debtor_heap, (-(owed - transfer), debtor))
        if credit > transfer:
            heapq.heappush(creditor_heap, (-(credit - transfer), creditor))
    return payments
