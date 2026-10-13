def apply(net, payments):
    """Apply suggested payments to net balances (debtor pays creditor)."""
    out = dict(net)
    for p in payments:
        out[p["from_user"]["name"]] = out.get(p["from_user"]["name"], 0) + p["amount_paise"]
        out[p["to_user"]["name"]] = out.get(p["to_user"]["name"], 0) - p["amount_paise"]
    return out


def test_assignment_example(api, client, trip):
    api.expense(trip["group"], trip["mohit"], 1200)
    r = client.get(f"/groups/{trip['group']}/settlements")
    assert r.status_code == 200
    body = r.json()
    assert body["is_settled"] is False and body["payment_count"] == 2
    got = sorted((p["from_user"]["name"], p["to_user"]["name"], p["amount_paise"], p["amount"]) for p in body["suggested_payments"])
    assert got == [("Ankit", "Mohit", 40000, "400.00"), ("Rahul", "Mohit", 40000, "400.00")]


def test_settlement_needs_fewer_payments_than_pairwise_debts(api, client):
    a, b, c, d = (api.user(n) for n in "ABCD")
    g = api.group("four", (a, b, c, d))
    api.expense(g, a, "4.00")   # B, C, D each owe A 1.00
    api.expense(g, d, "4.00")   # A, B, C each owe D 1.00  (A<->D cancel)
    pairwise = api.balances(g)["balances"]
    assert len(pairwise) == 4   # B->A, C->A, B->D, C->D
    body = client.get(f"/groups/{g}/settlements").json()
    got = [(p["from_user"]["name"], p["to_user"]["name"], p["amount_paise"]) for p in body["suggested_payments"]]
    assert got == [("B", "A", 200), ("C", "D", 200)]   # 2 payments clear all 4 debts


def test_suggestions_clear_every_net_balance_and_do_not_change_state(api, client, trip):
    g = trip["group"]
    api.expense(g, trip["mohit"], "1200.00")
    api.expense(g, trip["rahul"], "333.33")
    api.expense(g, trip["ankit"], "77.77")
    before = api.balances(g)
    net = {n["user"]["name"]: n["net_paise"] for n in before["net_balances"]}

    body = client.get(f"/groups/{g}/settlements").json()
    assert all(p["amount_paise"] > 0 for p in body["suggested_payments"])          # no zero transfers
    assert len(body["suggested_payments"]) <= len(net) - 1                         # at most n-1 payments
    assert all(v == 0 for v in apply(net, body["suggested_payments"]).values())    # everything cleared

    assert api.balances(g) == before                                               # read-only
    assert client.get(f"/groups/{g}/settlements").json() == body                   # deterministic


def test_nothing_to_settle(api, client, trip):
    body = client.get(f"/groups/{trip['group']}/settlements").json()
    assert body == {**body, "is_settled": True, "payment_count": 0, "suggested_payments": []}


def test_unknown_group(client):
    assert client.get("/groups/999/settlements").status_code == 404
