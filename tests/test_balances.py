import pytest


def owed(resp):
    """{(debtor, creditor): paise}"""
    return {(b["debtor"]["name"], b["creditor"]["name"]): b["amount_paise"] for b in resp["balances"]}


def nets(resp):
    return {n["user"]["name"]: n["net_paise"] for n in resp["net_balances"]}


class TestGroupBalances:
    def test_assignment_example(self, api, trip):
        api.expense(trip["group"], trip["mohit"], 1200)
        resp = api.balances(trip["group"])
        assert owed(resp) == {("Rahul", "Mohit"): 40000, ("Ankit", "Mohit"): 40000}
        assert resp["scope"] == {"type": "group", "group_id": trip["group"]}
        assert resp["owes"] == {"Rahul": {"owes": {"Mohit": "400.00"}}, "Ankit": {"owes": {"Mohit": "400.00"}}}
        assert nets(resp) == {"Mohit": 80000, "Rahul": -40000, "Ankit": -40000}
        assert sum(nets(resp).values()) == 0

    def test_payer_never_owes_themselves(self, api, trip):
        api.expense(trip["group"], trip["mohit"], 1200)
        assert all(b["debtor"]["name"] != b["creditor"]["name"] for b in api.balances()["balances"])
        assert "Mohit" not in api.balances()["owes"]

    def test_multiple_payers(self, api, trip):
        g = trip["group"]
        api.expense(g, trip["mohit"], 1200)   # each owes Mohit 400
        api.expense(g, trip["rahul"], 600)    # each owes Rahul 200
        resp = api.balances(g)
        # Rahul->Mohit 400, Mohit->Rahul 200 cancel to Rahul->Mohit 200
        assert owed(resp) == {("Rahul", "Mohit"): 20000, ("Ankit", "Mohit"): 40000, ("Ankit", "Rahul"): 20000}
        assert sum(nets(resp).values()) == 0
        assert nets(resp) == {"Mohit": 60000, "Ankit": -60000}  # Rahul nets to exactly 0, so he is omitted

    def test_opposite_debts_cancel_completely(self, api, trip):
        g = trip["group"]
        api.expense(g, trip["mohit"], 300)   # Rahul owes Mohit 100, Ankit owes Mohit 100
        api.expense(g, trip["rahul"], 300)   # Mohit owes Rahul 100, Ankit owes Rahul 100
        resp = api.balances(g)
        assert owed(resp) == {("Ankit", "Mohit"): 10000, ("Ankit", "Rahul"): 10000}   # Rahul<->Mohit gone entirely
        assert ("Rahul", "Mohit") not in owed(resp) and ("Mohit", "Rahul") not in owed(resp)

    def test_fully_settled_group_has_no_outstanding_balances(self, api, trip):
        g = trip["group"]
        for payer in ("mohit", "rahul", "ankit"):
            api.expense(g, trip[payer], 300)
        resp = api.balances(g)
        assert resp["balances"] == [] and resp["owes"] == {} and resp["net_balances"] == []

    def test_no_expenses_and_empty_group(self, api, trip):
        assert api.balances(trip["group"])["balances"] == []
        assert api.balances(api.group("Empty"))["balances"] == []

    def test_remainder_paise_never_lost(self, api, trip):
        g = trip["group"]
        api.expense(g, trip["mohit"], "100.00")  # shares 3334/3333/3333
        resp = api.balances(g)
        assert owed(resp) == {("Rahul", "Mohit"): 3333, ("Ankit", "Mohit"): 3333}
        assert nets(resp) == {"Mohit": 6666, "Rahul": -3333, "Ankit": -3333}
        assert sum(nets(resp).values()) == 0

    def test_unknown_group(self, client):
        assert client.get("/balances?group_id=999").status_code == 404
        assert client.get("/groups/999/balances").status_code == 404

    def test_invalid_group_id_query(self, client):
        assert client.get("/balances?group_id=abc").status_code == 422

    def test_group_route_matches_query_route(self, api, client, trip):
        api.expense(trip["group"], trip["mohit"], 1200)
        assert client.get(f"/groups/{trip['group']}/balances").json() == api.balances(trip["group"])


class TestSystemWideBalances:
    def test_combines_groups_and_cancels_across_them(self, api):
        m, r = api.user("Mohit"), api.user("Rahul")
        g1, g2 = api.group("Goa", (m, r)), api.group("Pune", (m, r))
        api.expense(g1, m, 1000)   # Rahul owes Mohit 500 in Goa
        api.expense(g2, r, 400)    # Mohit owes Rahul 200 in Pune
        assert owed(api.balances(g1)) == {("Rahul", "Mohit"): 50000}
        assert owed(api.balances(g2)) == {("Mohit", "Rahul"): 20000}
        overall = api.balances()
        assert overall["scope"] == {"type": "all_groups", "group_id": None}
        assert owed(overall) == {("Rahul", "Mohit"): 30000}

    def test_empty_system(self, client):
        assert client.get("/balances").json()["balances"] == []
