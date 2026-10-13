import pytest


def shares(expense_json):
    return {p["name"]: p["share_paise"] for p in expense_json["participants"]}


class TestCreateExpense:
    def test_equal_split_example_from_assignment(self, api, trip):
        r = api.expense(trip["group"], trip["mohit"], 1200)
        assert r.status_code == 201
        body = r.json()
        assert body["description"] == "Dinner"
        assert body["amount"] == "1200.00" and body["amount_paise"] == 120000
        assert body["paid_by"] == "Mohit" and body["paid_by_id"] == trip["mohit"]
        assert shares(body) == {"Mohit": 40000, "Rahul": 40000, "Ankit": 40000}
        assert [p["share"] for p in body["participants"]] == ["400.00"] * 3

    def test_uneven_split_distributes_remainder_paise_deterministically(self, api, trip):
        # 100.00 / 3 = 3333.33.. paise -> lowest user ids get the extra paisa
        body = api.expense(trip["group"], trip["mohit"], "100.00").json()
        assert shares(body) == {"Mohit": 3334, "Rahul": 3333, "Ankit": 3333}
        assert sum(shares(body).values()) == 10000

    def test_decimal_amounts_are_exact(self, api, trip):
        # 10.10 and 0.30 are classic float traps
        assert api.expense(trip["group"], trip["mohit"], 10.10).json()["amount_paise"] == 1010
        assert api.expense(trip["group"], trip["mohit"], 0.30).json()["amount_paise"] == 30
        assert api.expense(trip["group"], trip["mohit"], "1200.50").json()["amount_paise"] == 120050

    def test_one_paisa_expense(self, api, trip):
        body = api.expense(trip["group"], trip["mohit"], "0.01").json()
        assert sorted(shares(body).values()) == [0, 0, 1]

    @pytest.mark.parametrize("amount", [0, -5, "-0.01", "0.00"])
    def test_amount_must_be_positive(self, api, trip, amount):
        r = api.expense(trip["group"], trip["mohit"], amount)
        assert r.status_code == 422
        assert r.json()["error"]["code"] == "VALIDATION_ERROR"

    @pytest.mark.parametrize("amount", ["10.123", 1.005, "abc", None, "NaN", "Infinity", True])
    def test_malformed_amounts_rejected(self, api, trip, amount):
        assert api.expense(trip["group"], trip["mohit"], amount).status_code == 422

    def test_missing_fields_rejected(self, client):
        r = client.post("/expenses", json={"group_id": 1})
        assert r.status_code == 422
        fields = {d["field"] for d in r.json()["error"]["details"]}
        assert {"paid_by", "amount", "description"} <= fields

    def test_blank_description_rejected(self, api, trip):
        assert api.expense(trip["group"], trip["mohit"], 100, "   ").status_code == 422

    def test_nonexistent_group(self, api, trip):
        assert api.expense(999, trip["mohit"], 100).status_code == 404

    def test_nonexistent_payer(self, api, trip):
        assert api.expense(trip["group"], 999, 100).status_code == 404

    def test_payer_not_in_group(self, api, trip):
        outsider = api.user("Outsider")
        r = api.expense(trip["group"], outsider, 100)
        assert r.status_code == 422
        assert r.json()["error"]["code"] == "BUSINESS_RULE_VIOLATION"

    def test_expense_in_empty_group_rejected(self, api):
        u, g = api.user("Mohit"), api.group()
        assert api.expense(g, u, 100).status_code == 422

    def test_single_member_group(self, api, client):
        u = api.user("Solo")
        g = api.group("Solo", (u,))
        r = api.expense(g, u, 500)
        assert r.status_code == 201
        assert shares(r.json()) == {"Solo": 50000}
        assert api.balances(g)["balances"] == []


class TestHistory:
    def test_list_expenses_in_chronological_order_with_details(self, api, client, trip):
        api.expense(trip["group"], trip["mohit"], 1200, "Dinner")
        api.expense(trip["group"], trip["rahul"], 300, "Taxi")
        rows = client.get(f"/groups/{trip['group']}/expenses").json()
        assert [(e["description"], e["amount_paise"], e["paid_by"]) for e in rows] == [
            ("Dinner", 120000, "Mohit"),
            ("Taxi", 30000, "Rahul"),
        ]
        assert rows[0]["id"] < rows[1]["id"]

    def test_empty_history(self, api, client):
        g = api.group()
        assert client.get(f"/groups/{g}/expenses").json() == []

    def test_history_of_unknown_group(self, client):
        assert client.get("/groups/999/expenses").status_code == 404

    def test_expenses_are_scoped_to_their_group(self, api, client, trip):
        other = api.group("Other", (trip["mohit"],))
        api.expense(trip["group"], trip["mohit"], 900)
        assert client.get(f"/groups/{other}/expenses").json() == []

    def test_late_member_does_not_change_historical_split(self, api, client, trip):
        api.expense(trip["group"], trip["mohit"], 1200)
        before = client.get(f"/groups/{trip['group']}/expenses").json()

        newcomer = api.user("Newbie")
        api.add_member(trip["group"], newcomer)

        after = client.get(f"/groups/{trip['group']}/expenses").json()
        assert after == before                       # old expense untouched
        assert len(after[0]["participants"]) == 3    # newcomer was not part of it
        assert api.balances(trip["group"])["net_balances"][0]["net_paise"] == 80000

        # ...but the next expense includes the newcomer (4-way split)
        new = api.expense(trip["group"], trip["mohit"], 1000).json()
        assert shares(new) == {"Mohit": 25000, "Rahul": 25000, "Ankit": 25000, "Newbie": 25000}
