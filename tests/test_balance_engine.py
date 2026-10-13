"""Unit tests for the pure engine (no database, no HTTP)."""
import random

import pytest

from app.services.balance_engine import Debt, net_balances, pairwise_balances, split_equally, suggest_settlements
from app.services.money import format_paise, rupees_to_paise
from decimal import Decimal


class TestSplitEqually:
    def test_even(self):
        assert split_equally(120000, [1, 2, 3]) == {1: 40000, 2: 40000, 3: 40000}

    def test_remainder_goes_to_lowest_ids_regardless_of_input_order(self):
        assert split_equally(10000, [3, 1, 2]) == {1: 3334, 2: 3333, 3: 3333}
        assert split_equally(10, [5, 9, 2]) == {2: 4, 5: 3, 9: 3}

    def test_single_member_pays_everything(self):
        assert split_equally(777, [4]) == {4: 777}

    def test_no_members_is_an_error(self):
        with pytest.raises(ValueError):
            split_equally(100, [])

    def test_property_shares_sum_exactly_and_differ_by_at_most_one(self):
        rng = random.Random(42)
        for _ in range(500):
            amount, n = rng.randint(1, 10_000_000), rng.randint(1, 12)
            shares = list(split_equally(amount, range(1, n + 1)).values())
            assert sum(shares) == amount
            assert max(shares) - min(shares) <= 1


class TestPairwise:
    def test_cancels_opposite_directions(self):
        out = pairwise_balances([Debt(1, 2, 700), Debt(2, 1, 300)])
        assert out == [Debt(1, 2, 400)]

    def test_exact_cancellation_drops_pair(self):
        assert pairwise_balances([Debt(1, 2, 500), Debt(2, 1, 500)]) == []

    def test_merges_duplicates_and_ignores_self_debts(self):
        assert pairwise_balances([Debt(1, 2, 100), Debt(1, 2, 50), Debt(3, 3, 999)]) == [Debt(1, 2, 150)]

    def test_output_is_sorted(self):
        out = pairwise_balances([Debt(3, 1, 5), Debt(2, 1, 5), Debt(1, 3, 1)])
        assert out == [Debt(2, 1, 5), Debt(3, 1, 4)]


class TestNetAndSettlement:
    def test_net_balances(self):
        assert net_balances([Debt(2, 1, 400), Debt(3, 1, 400)]) == {1: 800, 2: -400, 3: -400}

    def test_settlement_rejects_non_zero_sum(self):
        with pytest.raises(ValueError):
            suggest_settlements({1: 100, 2: -50})

    def test_settlement_tie_break_is_by_lowest_id(self):
        assert suggest_settlements({1: 100, 2: 100, 3: -100, 4: -100}) == [Debt(3, 1, 100), Debt(4, 2, 100)]

    def test_settlement_handles_partial_matches(self):
        assert suggest_settlements({1: 70, 2: 30, 3: -50, 4: -50}) == [
            Debt(3, 1, 50), Debt(4, 2, 30), Debt(4, 1, 20)
        ]

    def test_property_random_ledgers_always_fully_settle(self):
        rng = random.Random(7)
        for _ in range(300):
            n = rng.randint(2, 9)
            debts = [Debt(rng.randint(1, n), rng.randint(1, n), rng.randint(1, 100_000)) for _ in range(rng.randint(1, 25))]
            pairs = pairwise_balances(debts)
            net = net_balances(pairs)
            assert sum(net.values()) == 0
            assert net == net_balances(debts)  # cancelling opposite debts never changes anyone's net
            payments = suggest_settlements(net)
            assert all(p.amount_paise > 0 for p in payments)
            assert len(payments) <= max(len(net) - 1, 0)
            left = dict(net)
            for p in payments:
                left[p.debtor] += p.amount_paise
                left[p.creditor] -= p.amount_paise
            assert all(v == 0 for v in left.values())
            assert payments == suggest_settlements(net)  # deterministic


class TestMoney:
    def test_rupees_to_paise_is_exact(self):
        assert rupees_to_paise(Decimal("10.10")) == 1010
        assert rupees_to_paise(Decimal("1200")) == 120000

    @pytest.mark.parametrize("paise,text", [(0, "0.00"), (5, "0.05"), (40000, "400.00"), (123456, "1234.56"), (-250, "-2.50")])
    def test_format(self, paise, text):
        assert format_paise(paise) == text
