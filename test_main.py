import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from .main import app, get_session, calculate_monthly_payment, calculate_loan_schedule, calculate_loan_summary


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture(name="client")
def client_fixture(session: Session):
    def get_session_override():
        return session

    app.dependency_overrides[get_session] = get_session_override

    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


def test_create_user(client: TestClient):
    response = client.post(
        "/create_user/", json={"username": "test_user"}
    )
    data = response.json()
    assert response.status_code == 200
    assert data["user"]["username"] == "test_user"
    assert data["user"]["id"] is not None


def test_create_loan(client: TestClient):
    response_create_loan = client.post("/create_loan", json={
        "user_id": 1,
        "amount": 1000.0,
        "annual_interest_rate": 5.0,
        "loan_term": 12
    })
    assert response_create_loan.status_code == 200
    assert response_create_loan.json()["message"] == "Loan created successfully"
    assert "loan" in response_create_loan.json()
    assert "id" in response_create_loan.json()["loan"]
    assert "user_id" in response_create_loan.json()["loan"]
    assert response_create_loan.json()["loan"]["user_id"] == 1


def test_loan_schedule(client: TestClient):
    response_create_user = client.post(
        "/create_user", json={"username": "test_user"})
    assert response_create_user.status_code == 200
    user_id = response_create_user.json()["user"]["id"]

    response_create_loan = client.post("/create_loan", json={
        "user_id": user_id,
        "amount": 1000.0,
        "annual_interest_rate": 5.0,
        "loan_term": 12,
    })
    assert response_create_loan.status_code == 200
    loan_id = response_create_loan.json()["loan"]["id"]

    response_loan_schedule = client.get(f"/loan/{loan_id}/schedule")
    assert response_loan_schedule.status_code == 200
    assert response_loan_schedule.json()["message"] == "Loan schedule fetched successfully"
    assert "loan_schedule" in response_loan_schedule.json()
    assert len(response_loan_schedule.json()["loan_schedule"]) == 12


def test_loan_summary(client: TestClient):
    response_create_user = client.post(
        "/create_user", json={"username": "test_user"})
    assert response_create_user.status_code == 200
    user_id = response_create_user.json()["user"]["id"]

    response_create_loan = client.post("/create_loan", json={
        "user_id": user_id,
        "amount": 1000.0,
        "annual_interest_rate": 5.0,
        "loan_term": 12
    })
    assert response_create_loan.status_code == 200
    loan_id = response_create_loan.json()["loan"]["id"]

    response_loan_summary = client.get(f"/loan/{loan_id}/summary?month=6")
    assert response_loan_summary.status_code == 200
    assert response_loan_summary.json()["message"] == "Loan summary fetched successfully"
    assert "loan_summary" in response_loan_summary.json()


def test_user_loans(client: TestClient):
    response_create_user = client.post("/create_user", json={"username": "test_user"})
    assert response_create_user.status_code == 200
    user_id = response_create_user.json()["user"]["id"]

    response_user_loans = client.get(f"/user/{user_id}/loans")
    assert response_user_loans.status_code == 200
    assert response_user_loans.json()["message"] == "User loans fetched successfully"
    assert "user_loans" in response_user_loans.json()
    assert len(response_user_loans.json()["user_loans"]) == 0  # No loans created yet


def test_share_loan(client: TestClient):
    response_create_user = client.post(
        "/create_user", json={"username": "test_user"})
    assert response_create_user.status_code == 200
    user_id = response_create_user.json()["user"]["id"]

    response_create_loan = client.post("/create_loan", json={
        "user_id": user_id,
        "amount": 1000.0,
        "annual_interest_rate": 5.0,
        "loan_term": 12
    })
    assert response_create_loan.status_code == 200
    loan_id = response_create_loan.json()["loan"]["id"]

    response_create_recipient_user = client.post("/create_user", json={"username": "recipient_user"})
    assert response_create_recipient_user.status_code == 200
    recipient_user_id = response_create_recipient_user.json()["user"]["id"]

    response_share_loan = client.post(f"/loan/{loan_id}/share/{recipient_user_id}")
    assert response_share_loan.status_code == 200
    assert response_share_loan.json()["message"] == "Loan shared successfully"
    assert "shared_loan" in response_share_loan.json()
    assert response_share_loan.json()["shared_loan"]["user_id"] == recipient_user_id


def test_calculate_monthly_payment():
    amount = 10000.0
    annual_interest_rate = 5.0
    loan_term = 120

    monthly_payment = calculate_monthly_payment(amount, annual_interest_rate, loan_term)

    assert round(monthly_payment, 2) == 106.07


def test_calculate_loan_schedule():
    amount = 10000.0
    annual_interest_rate = 5
    loan_term = 120

    loan_schedule = calculate_loan_schedule(amount, annual_interest_rate, loan_term)

    assert len(loan_schedule) == loan_term

    assert round(loan_schedule[0].monthly_payment, 2) == 106.07
    assert round(loan_schedule[0].remaining_balance, 2) == 9935.6
    assert loan_schedule[0].month == 1

    assert round(loan_schedule[-1].monthly_payment, 2) == 106.07
    assert round(loan_schedule[-1].remaining_balance, 2) == 0
    assert loan_schedule[-1].month == 120


def test_calculate_loan_summary():
    amount = 10000.0
    annual_interest_rate = 5
    loan_term = 120
    month_number = 24

    loan_schedule = calculate_loan_schedule(amount, annual_interest_rate, loan_term)
    loan_summary = calculate_loan_summary(
        schedule=loan_schedule, month_number=month_number, amount=amount
    )

    # Perform assertions
    assert round(loan_summary.current_principal_balance, 2) == 8378.06
    assert round(loan_summary.aggregate_principal_paid, 2) == 1621.94
    assert round(loan_summary.aggregate_interest_paid, 2) == 923.63
