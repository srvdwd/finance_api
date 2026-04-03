# Finance Tracker API

A RESTful backend for managing personal financial records, built with **FastAPI**, **SQLAlchemy**, and **SQLite**. Features JWT authentication, role-based access control, analytics, and a full test suite.

---

## Tech Stack

| Layer        | Technology                          |
|--------------|-------------------------------------|
| Framework    | FastAPI 0.115                       |
| ORM          | SQLAlchemy 2.0                      |
| Database     | SQLite (swappable to PostgreSQL)    |
| Validation   | Pydantic v2                         |
| Auth         | JWT via `python-jose` + `passlib`   |
| Server       | Uvicorn                             |
| Tests        | Pytest + HTTPX                      |

---

## Project Structure

```
finance_system/
├── app/
│   ├── main.py              # App factory; registers routers + middleware
│   ├── config.py            # Settings loaded from environment / .env
│   ├── database.py          # SQLAlchemy engine, session, Base
│   ├── dependencies.py      # get_current_user, require_role (JWT guard)
│   ├── models/
│   │   ├── user.py          # User model + UserRole enum
│   │   └── transaction.py   # Transaction model + TransactionType enum
│   ├── schemas/
│   │   ├── user.py          # Pydantic schemas: UserCreate, UserOut, Token
│   │   └── transaction.py   # TransactionCreate, TransactionUpdate, TransactionOut, PaginatedTransactions
│   ├── routers/
│   │   ├── auth.py          # POST /auth/register, POST /auth/login
│   │   ├── transactions.py  # CRUD endpoints for transactions
│   │   ├── analytics.py     # Summary, category breakdown, monthly totals
│   │   └── users.py         # User listing and role management (admin)
│   └── services/
│       ├── auth_service.py         # Password hashing, JWT, user queries
│       ├── transaction_service.py  # CRUD + filtered pagination logic
│       └── analytics_service.py    # Aggregation and summary logic
├── tests/
│   └── test_api.py          # 40+ tests across auth, transactions, analytics, users
├── seed.py                  # Populates DB with sample users and transactions
├── requirements.txt
└── .env.example
```

---

## Setup

### 1. Clone and create a virtual environment

```bash
git clone <repo-url>
cd finance_system
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment

```bash
cp .env.example .env
# Edit .env to set a strong SECRET_KEY in production
```

### 4. Seed the database (optional but recommended)

```bash
python seed.py
```

This creates three test users and 60 randomised transactions:

| Username | Password    | Role     |
|----------|-------------|----------|
| admin    | password123 | admin    |
| analyst  | password123 | analyst  |
| viewer   | password123 | viewer   |

### 5. Start the server

```bash
uvicorn app.main:app --reload
```

- **Swagger UI:** http://127.0.0.1:8000/docs
- **ReDoc:**      http://127.0.0.1:8000/redoc

---

## Roles & Permissions

Roles follow a strict hierarchy: **viewer < analyst < admin**

| Endpoint                     | Viewer | Analyst | Admin |
|------------------------------|:------:|:-------:|:-----:|
| GET /transactions/           |   ✅   |   ✅    |  ✅   |
| GET /transactions/{id}       |   ✅   |   ✅    |  ✅   |
| GET /analytics/summary       |   ✅   |   ✅    |  ✅   |
| GET /analytics/by-category   |   ❌   |   ✅    |  ✅   |
| GET /analytics/monthly       |   ❌   |   ✅    |  ✅   |
| GET /analytics/recent        |   ❌   |   ✅    |  ✅   |
| POST /transactions/          |   ❌   |   ❌    |  ✅   |
| PUT /transactions/{id}       |   ❌   |   ❌    |  ✅   |
| DELETE /transactions/{id}    |   ❌   |   ❌    |  ✅   |
| GET /users/                  |   ❌   |   ❌    |  ✅   |
| PUT /users/{id}/role         |   ❌   |   ❌    |  ✅   |

---

## API Reference

### Authentication

#### Register
```
POST /auth/register
Content-Type: application/json

{
  "username": "alice",
  "email": "alice@example.com",
  "password": "mypassword"
}
```

#### Login
```
POST /auth/login
Content-Type: application/x-www-form-urlencoded

username=alice&password=mypassword
```
Returns:
```json
{
  "access_token": "<jwt>",
  "token_type": "bearer",
  "user": { "id": 1, "username": "alice", "role": "viewer", ... }
}
```

All subsequent requests require the header:
```
Authorization: Bearer <access_token>
```

---

### Transactions

#### List (with optional filters)
```
GET /transactions/?type=expense&category=food&date_from=2025-01-01&page=1&page_size=20
```
Response:
```json
{
  "total": 42,
  "page": 1,
  "page_size": 20,
  "items": [ { "id": 1, "amount": 50.0, "type": "expense", ... } ]
}
```

#### Create (admin only)
```
POST /transactions/
{
  "amount": 3500.00,
  "type": "income",
  "category": "Salary",
  "date": "2025-03-01T09:00:00",
  "notes": "March salary"
}
```

#### Update (admin only)
```
PUT /transactions/1
{ "amount": 3600.00, "notes": "Corrected amount" }
```

#### Delete (admin only)
```
DELETE /transactions/1
→ 204 No Content
```

---

### Analytics

#### Summary (viewer+)
```
GET /analytics/summary

{
  "total_income": 15000.00,
  "total_expenses": 6200.00,
  "balance": 8800.00,
  "income_count": 5,
  "expense_count": 18,
  "total_transactions": 23
}
```

#### By Category (analyst+)
```
GET /analytics/by-category?type=expense

[
  { "category": "Rent",  "type": "expense", "total": 3000.00, "count": 3 },
  { "category": "Food",  "type": "expense", "total": 900.00,  "count": 12 }
]
```

#### Monthly Totals (analyst+)
```
GET /analytics/monthly?year=2025

[
  { "month": "2025-01", "income": 5000.0, "expense": 1800.0, "balance": 3200.0, "count": 8 },
  { "month": "2025-02", "income": 5000.0, "expense": 2100.0, "balance": 2900.0, "count": 9 }
]
```

#### Recent Transactions (analyst+)
```
GET /analytics/recent?limit=5
```

---

### Users (admin only)

```
GET  /users/               → list all users
GET  /users/{id}           → get one user
PUT  /users/{id}/role      → { "role": "analyst" }
GET  /users/me             → current authenticated user (any role)
```

---

## Running Tests

```bash
pytest tests/ -v
```

The test suite uses an isolated in-memory SQLite database. Each test class covers a distinct area:

- `TestAuth` — registration, login, token validation, edge cases
- `TestTransactions` — CRUD, filters, pagination, role enforcement
- `TestAnalytics` — summary correctness, category breakdown, monthly, role gates
- `TestUsers` — admin list/get/update-role flows

---

## Switching to PostgreSQL

1. Update `.env`:
   ```
   DATABASE_URL=postgresql://user:password@localhost/finance_db
   ```
2. In `app/database.py`, remove the `connect_args={"check_same_thread": False}` argument.
3. In `app/services/analytics_service.py`, replace `func.strftime(...)` with `func.to_char(Transaction.date, 'YYYY-MM')` for the monthly grouping query.
4. Install: `pip install psycopg2-binary`

---

## Assumptions

- All transactions are stored in UTC. The client is responsible for timezone conversion.
- New users default to the `viewer` role. Roles can only be changed by an admin via `PUT /users/{id}/role`.
- Amount values are stored as floats and rounded to 2 decimal places on input.
- Pagination defaults: `page=1`, `page_size=20`, max `page_size=100`.
- The seed script targets the `admin` user's ID for sample transactions; it is idempotent and safe to run more than once.
