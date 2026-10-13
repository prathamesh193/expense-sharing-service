import pytest


class TestUsers:
    def test_create_and_list(self, client):
        r = client.post("/users", json={"name": "Mohit"})
        assert r.status_code == 201
        assert r.json() == {"id": 1, "name": "Mohit"}
        client.post("/users", json={"name": "Rahul"})
        assert client.get("/users").json() == [{"id": 1, "name": "Mohit"}, {"id": 2, "name": "Rahul"}]

    def test_list_empty(self, client):
        assert client.get("/users").json() == []

    def test_name_is_trimmed(self, client):
        assert client.post("/users", json={"name": "  Mohit  "}).json()["name"] == "Mohit"

    def test_duplicate_name_is_case_insensitive_conflict(self, client):
        client.post("/users", json={"name": "Mohit"})
        r = client.post("/users", json={"name": "mohit"})
        assert r.status_code == 409
        assert r.json()["error"]["code"] == "CONFLICT"

    @pytest.mark.parametrize("payload", [{}, {"name": ""}, {"name": "   "}, {"name": 123}, {"name": None}, {"name": "x" * 101}])
    def test_invalid_payloads_rejected(self, client, payload):
        r = client.post("/users", json=payload)
        assert r.status_code == 422
        assert r.json()["error"]["code"] == "VALIDATION_ERROR"

    def test_malformed_json_rejected(self, client):
        r = client.post("/users", content="{not json", headers={"Content-Type": "application/json"})
        assert r.status_code == 422


class TestGroups:
    def test_create_group(self, client):
        r = client.post("/groups", json={"name": "Goa Trip"})
        assert r.status_code == 201
        assert r.json() == {"id": 1, "name": "Goa Trip"}

    def test_invalid_group_payload(self, client):
        assert client.post("/groups", json={"name": ""}).status_code == 422

    def test_add_and_list_members(self, api, client):
        m, r = api.user("Mohit"), api.user("Rahul")
        g = api.group()
        added = api.add_member(g, r).json()
        assert (added["id"], added["name"]) == (r, "Rahul")
        api.add_member(g, m)
        members = client.get(f"/groups/{g}/members").json()
        assert [x["name"] for x in members] == ["Mohit", "Rahul"]  # ordered by user id

    def test_duplicate_membership_is_conflict(self, api, client):
        u, g = api.user("Mohit"), api.group()
        api.add_member(g, u)
        r = client.post(f"/groups/{g}/members", json={"user_id": u})
        assert r.status_code == 409
        assert len(client.get(f"/groups/{g}/members").json()) == 1

    def test_add_nonexistent_user(self, api, client):
        g = api.group()
        assert client.post(f"/groups/{g}/members", json={"user_id": 999}).status_code == 404

    def test_add_to_nonexistent_group(self, api, client):
        u = api.user("Mohit")
        assert client.post("/groups/999/members", json={"user_id": u}).status_code == 404

    def test_list_members_of_nonexistent_group(self, client):
        assert client.get("/groups/999/members").status_code == 404

    def test_empty_group_has_no_members(self, api, client):
        g = api.group()
        assert client.get(f"/groups/{g}/members").json() == []

    def test_body_group_id_accepted_when_matching_and_rejected_when_not(self, api, client):
        u, g = api.user("Mohit"), api.group()
        assert client.post(f"/groups/{g}/members", json={"group_id": g, "user_id": u}).status_code == 201
        u2 = api.user("Rahul")
        assert client.post(f"/groups/{g}/members", json={"group_id": g + 1, "user_id": u2}).status_code == 422

    @pytest.mark.parametrize("payload", [{}, {"user_id": "abc"}, {"user_id": 0}, {"user_id": -1}])
    def test_invalid_member_payload(self, api, client, payload):
        g = api.group()
        assert client.post(f"/groups/{g}/members", json=payload).status_code == 422
