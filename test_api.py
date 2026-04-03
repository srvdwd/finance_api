"""
Test suite for the Finance Tracker API.

Run with:
    pytest tests/ -v

Uses an in-memory SQLite database that is created fresh for every test,
so tests are fully isolated and leave no side effects.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app
from app.models.user import UserRole
from app.schemas.user import UserCreate
from app.services.auth_service import create_access_token, create_user

# ── Test database setup ──────────────────────────────────────────────────────

TEST_DB_URL = "sqlite:///./test_finance.db"
test_engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestSession = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def override_get_db():
    db = TestSession()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def reset_db():
    """Recreate all tables before each test; drop them after."""
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def client():
    return TestClient(app)


def _make_user(role: UserRole, username: str, email: str) -> str:
    """Helper: create a user in the test DB and return their JWT token."""
    db = TestSession()
    try:
        user = create_user(
            db,
            UserCreate(username=username, email=email, password="password123"),
            role=role,
        )
        return create_access_token({"sub": str(user.id)})
    finally:
        db.close()


@pytest.fixture
def admin_token():
    return _make_user(UserRole.admin, "admin", "admin@test.com")


@pytest.fixture
def analyst_token():
    return _make_user(UserRole.analyst, "analyst", "analyst@test.com")


@pytest.fixture
def viewer_token():
    return _make_user(UserRole.viewer, "viewer", "viewer@test.com")


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def make_tx(client, token: str, **overrides) -> dict:
    """Helper: POST a transaction and return the response JSON."""
    payload = {"amount": 100.0, "type": "expense", "category": "Food", **overrides}
    res = client.post("/transactions/", json=payload, headers=auth(token))
    assert res.status_code == 201, res.text
    return res.json()


# ════════════════════════════════════════════════════════════════════════════
# AUTH TESTS
# ════════════════════════════════════════════════════════════════════════════

class TestAuth:
    def test_register_success(self, client):
        res = client.post("/auth/register", json={
            "username": "newuser", "email": "new@test.com", "password": "password123"
        })
        assert res.status_code == 201
        data = res.json()
        assert data["username"] == "newuser"
        assert data["role"] == "viewer"
        assert "hashed_password" not in data

    def test_register_duplicate_username(self, client):
        payload = {"username": "dup", "email": "a@test.com", "password": "password123"}
        client.post("/auth/register", json=payload)
        res = client.post("/auth/register", json={**payload, "email": "b@test.com"})
        assert res.status_code == 400
        assert "Username" in res.json()["detail"]

    def test_register_duplicate_email(self, client):
        payload = {"username": "user1", "email": "same@test.com", "password": "password123"}
        client.post("/auth/register", json=payload)
        res = client.post("/auth/register", json={**payload, "username": "user2"})
        assert res.status_code == 400
        assert "Email" in res.json()["detail"]

    def test_register_short_password(self, client):
        res = client.post("/auth/register", json={
            "username": "user1", "email": "u@test.com", "password": "ab"
        })
        assert res.status_code == 422

    def test_register_short_username(self, client):
        res = client.post("/auth/register", json={
            "username": "ab", "email": "u@test.com", "password": "password123"
        })
        assert res.status_code == 422

    def test_login_success(self, client):
        client.post("/auth/register", json={
            "username": "loginuser", "email": "l@test.com", "password": "password123"
        })
        res = client.post("/auth/login", data={"username": "loginuser", "password": "password123"})
        assert res.status_code == 200
        data = res.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["user"]["username"] == "loginuser"

    def test_login_wrong_password(self, client):
        client.post("/auth/register", json={
            "username": "u2", "email": "u2@test.com", "password": "password123"
        })
        res = client.post("/auth/login", data={"username": "u2", "password": "wrong"})
        assert res.status_code == 401

    def test_login_unknown_user(self, client):
        res = client.post("/auth/login", data={"username": "nobody", "password": "pass"})
        assert res.status_code == 401

    def test_protected_route_without_token(self, client):
        res = client.get("/transactions/")
        assert res.status_code == 401

    def test_protected_route_with_invalid_token(self, client):
        res = client.get("/transactions/", headers={"Authorization": "Bearer not-a-real-token"})
        assert res.status_code == 401

    def test_get_me(self, client, viewer_token):
        res = client.get("/users/me", headers=auth(viewer_token))
        assert res.status_code == 200
        assert res.json()["role"] == "viewer"


# ════════════════════════════════════════════════════════════════════════════
# TRANSACTION TESTS
# ════════════════════════════════════════════════════════════════════════════

class TestTransactions:
    def test_create_as_admin(self, client, admin_token):
        tx = make_tx(client, admin_token, amount=500.0, type="income", category="Salary")
        assert tx["amount"] == 500.0
        assert tx["type"] == "income"
        assert tx["category"] == "Salary"
        assert "id" in tx

    def test_create_as_viewer_forbidden(self, client, viewer_token):
        res = client.post("/transactions/", json={
            "amount": 100.0, "type": "expense", "category": "Food"
        }, headers=auth(viewer_token))
        assert res.status_code == 403

    def test_create_as_analyst_forbidden(self, client, analyst_token):
        res = client.post("/transactions/", json={
            "amount": 100.0, "type": "expense", "category": "Food"
        }, headers=auth(analyst_token))
        assert res.status_code == 403

    def test_create_negative_amount(self, client, admin_token):
        res = client.post("/transactions/", json={
            "amount": -50.0, "type": "expense", "category": "Food"
        }, headers=auth(admin_token))
        assert res.status_code == 422

    def test_create_zero_amount(self, client, admin_token):
        res = client.post("/transactions/", json={
            "amount": 0.0, "type": "expense", "category": "Food"
        }, headers=auth(admin_token))
        assert res.status_code == 422

    def test_create_empty_category(self, client, admin_token):
        res = client.post("/transactions/", json={
            "amount": 100.0, "type": "expense", "category": "   "
        }, headers=auth(admin_token))
        assert res.status_code == 422

    def test_create_invalid_type(self, client, admin_token):
        res = client.post("/transactions/", json={
            "amount": 100.0, "type": "gift", "category": "Food"
        }, headers=auth(admin_token))
        assert res.status_code == 422

    def test_list_transactions_viewer(self, client, admin_token, viewer_token):
        make_tx(client, admin_token, amount=100.0)
        make_tx(client, admin_token, amount=200.0)
        res = client.get("/transactions/", headers=auth(viewer_token))
        assert res.status_code == 200
        data = res.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2

    def test_list_transactions_pagination(self, client, admin_token):
        for i in range(5):
            make_tx(client, admin_token, amount=float(100 * (i + 1)))
        res = client.get("/transactions/?page=1&page_size=3", headers=auth(admin_token))
        assert res.status_code == 200
        data = res.json()
        assert data["total"] == 5
        assert len(data["items"]) == 3

    def test_filter_by_type(self, client, admin_token):
        make_tx(client, admin_token, type="income", category="Salary")
        make_tx(client, admin_token, type="expense", category="Food")
        make_tx(client, admin_token, type="expense", category="Transport")

        res = client.get("/transactions/?type=expense", headers=auth(admin_token))
        data = res.json()
        assert data["total"] == 2
        assert all(t["type"] == "expense" for t in data["items"])

    def test_filter_by_category(self, client, admin_token):
        make_tx(client, admin_token, category="Salary")
        make_tx(client, admin_token, category="Food")
        make_tx(client, admin_token, category="Salary Bonus")

        # partial match
        res = client.get("/transactions/?category=Salary", headers=auth(admin_token))
        data = res.json()
        assert data["total"] == 2

    def test_filter_invalid_date_range(self, client, admin_token):
        res = client.get(
            "/transactions/?date_from=2025-06-01T00:00:00&date_to=2025-01-01T00:00:00",
            headers=auth(admin_token),
        )
        assert res.status_code == 400

    def test_get_by_id(self, client, admin_token, viewer_token):
        tx = make_tx(client, admin_token)
        res = client.get(f"/transactions/{tx['id']}", headers=auth(viewer_token))
        assert res.status_code == 200
        assert res.json()["id"] == tx["id"]

    def test_get_nonexistent(self, client, admin_token):
        res = client.get("/transactions/99999", headers=auth(admin_token))
        assert res.status_code == 404

    def test_update_transaction(self, client, admin_token):
        tx = make_tx(client, admin_token, amount=200.0, category="Shopping")
        res = client.put(f"/transactions/{tx['id']}", json={
            "amount": 350.0, "category": "Electronics"
        }, headers=auth(admin_token))
        assert res.status_code == 200
        updated = res.json()
        assert updated["amount"] == 350.0
        assert updated["category"] == "Electronics"
        assert updated["type"] == tx["type"]  # unchanged

    def test_update_empty_body(self, client, admin_token):
        tx = make_tx(client, admin_token)
        res = client.put(f"/transactions/{tx['id']}", json={}, headers=auth(admin_token))
        assert res.status_code == 400

    def test_update_as_viewer_forbidden(self, client, admin_token, viewer_token):
        tx = make_tx(client, admin_token)
        res = client.put(f"/transactions/{tx['id']}", json={"amount": 999.0},
                         headers=auth(viewer_token))
        assert res.status_code == 403

    def test_delete_transaction(self, client, admin_token):
        tx = make_tx(client, admin_token)
        res = client.delete(f"/transactions/{tx['id']}", headers=auth(admin_token))
        assert res.status_code == 204
        # Confirm it's gone
        get_res = client.get(f"/transactions/{tx['id']}", headers=auth(admin_token))
        assert get_res.status_code == 404

    def test_delete_nonexistent(self, client, admin_token):
        res = client.delete("/transactions/99999", headers=auth(admin_token))
        assert res.status_code == 404

    def test_delete_as_analyst_forbidden(self, client, admin_token, analyst_token):
        tx = make_tx(client, admin_token)
        res = client.delete(f"/transactions/{tx['id']}", headers=auth(analyst_token))
        assert res.status_code == 403


# ════════════════════════════════════════════════════════════════════════════
# ANALYTICS TESTS
# ════════════════════════════════════════════════════════════════════════════

class TestAnalytics:
    def test_summary_empty_db(self, client, viewer_token):
        res = client.get("/analytics/summary", headers=auth(viewer_token))
        assert res.status_code == 200
        data = res.json()
        assert data["total_income"] == 0.0
        assert data["total_expenses"] == 0.0
        assert data["balance"] == 0.0

    def test_summary_correct_totals(self, client, admin_token):
        make_tx(client, admin_token, amount=1000.0, type="income", category="Salary")
        make_tx(client, admin_token, amount=400.0, type="expense", category="Rent")
        make_tx(client, admin_token, amount=100.0, type="expense", category="Food")

        res = client.get("/analytics/summary", headers=auth(admin_token))
        data = res.json()
        assert data["total_income"] == 1000.0
        assert data["total_expenses"] == 500.0
        assert data["balance"] == 500.0
        assert data["income_count"] == 1
        assert data["expense_count"] == 2
        assert data["total_transactions"] == 3

    def test_summary_accessible_by_viewer(self, client, viewer_token):
        res = client.get("/analytics/summary", headers=auth(viewer_token))
        assert res.status_code == 200

    def test_by_category_viewer_forbidden(self, client, viewer_token):
        res = client.get("/analytics/by-category", headers=auth(viewer_token))
        assert res.status_code == 403

    def test_by_category_analyst_allowed(self, client, admin_token, analyst_token):
        make_tx(client, admin_token, amount=200.0, type="expense", category="Food")
        make_tx(client, admin_token, amount=300.0, type="expense", category="Food")
        make_tx(client, admin_token, amount=100.0, type="expense", category="Transport")

        res = client.get("/analytics/by-category", headers=auth(analyst_token))
        assert res.status_code == 200
        data = res.json()
        categories = {row["category"]: row["total"] for row in data}
        assert categories["Food"] == 500.0
        assert categories["Transport"] == 100.0

    def test_by_category_type_filter(self, client, admin_token, analyst_token):
        make_tx(client, admin_token, amount=1000.0, type="income", category="Salary")
        make_tx(client, admin_token, amount=200.0, type="expense", category="Food")

        res = client.get("/analytics/by-category?type=income", headers=auth(analyst_token))
        data = res.json()
        assert all(row["type"] == "income" for row in data)
        assert len(data) == 1

    def test_monthly_totals(self, client, admin_token, analyst_token):
        # Both dated explicitly to a known month
        make_tx(client, admin_token, amount=1000.0, type="income",
                category="Salary", date="2025-03-15T10:00:00")
        make_tx(client, admin_token, amount=300.0, type="expense",
                category="Rent", date="2025-03-20T10:00:00")

        res = client.get("/analytics/monthly?year=2025", headers=auth(analyst_token))
        assert res.status_code == 200
        data = res.json()
        march = next((m for m in data if m["month"] == "2025-03"), None)
        assert march is not None
        assert march["income"] == 1000.0
        assert march["expense"] == 300.0
        assert march["balance"] == 700.0

    def test_monthly_viewer_forbidden(self, client, viewer_token):
        res = client.get("/analytics/monthly", headers=auth(viewer_token))
        assert res.status_code == 403

    def test_recent_transactions(self, client, admin_token, analyst_token):
        for i in range(15):
            make_tx(client, admin_token, amount=float(10 * (i + 1)))

        res = client.get("/analytics/recent?limit=5", headers=auth(analyst_token))
        assert res.status_code == 200
        assert len(res.json()) == 5

    def test_recent_viewer_forbidden(self, client, viewer_token):
        res = client.get("/analytics/recent", headers=auth(viewer_token))
        assert res.status_code == 403


# ════════════════════════════════════════════════════════════════════════════
# USER MANAGEMENT TESTS
# ════════════════════════════════════════════════════════════════════════════

class TestUsers:
    def test_list_users_admin(self, client, admin_token, viewer_token):
        res = client.get("/users/", headers=auth(admin_token))
        assert res.status_code == 200
        assert isinstance(res.json(), list)

    def test_list_users_viewer_forbidden(self, client, viewer_token):
        res = client.get("/users/", headers=auth(viewer_token))
        assert res.status_code == 403

    def test_update_role(self, client, admin_token):
        # Register a plain viewer
        reg = client.post("/auth/register", json={
            "username": "promouser", "email": "promo@test.com", "password": "password123"
        })
        user_id = reg.json()["id"]

        res = client.put(f"/users/{user_id}/role", json={"role": "analyst"},
                         headers=auth(admin_token))
        assert res.status_code == 200
        assert res.json()["role"] == "analyst"

    def test_update_role_nonexistent_user(self, client, admin_token):
        res = client.put("/users/99999/role", json={"role": "analyst"},
                         headers=auth(admin_token))
        assert res.status_code == 404
