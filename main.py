from typing import List, Optional

from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from sqlmodel import SQLModel, create_engine, Session, Field, Relationship


# Define the SQLModel classes for User and Loan


class User(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True)
    username: str

    loans: List["Loan"] = Relationship(back_populates="user")


class Loan(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True)
    amount: float
    annual_interest_rate: float
    loan_term: int

    # Define a relationship to the User model
    user_id: int = Field(foreign_key="user.id")
    user: List[User] = Relationship(back_populates="loans")


sqlite_file_name = "database.db"
sqlite_url = f"sqlite:///{sqlite_file_name}"


connect_args = {"check_same_thread": False}
engine = create_engine(sqlite_url, echo=True, connect_args=connect_args)


def get_session():
    with Session(engine) as session:
        yield session


def create_db_and_tables():
    SQLModel.metadata.create_all(engine)


app = FastAPI()


# Define the FastAPI models
class UserCreate(BaseModel):
    username: str


class LoanCreate(BaseModel):
    user_id: int
    amount: float
    annual_interest_rate: float
    loan_term: int


class LoanSchedule(BaseModel):
    month: int
    remaining_balance: float
    monthly_payment: float


class LoanSummary(BaseModel):
    current_principal_balance: float
    aggregate_principal_paid: float
    aggregate_interest_paid: float


# Define the FastAPI endpoints
@app.on_event("startup")
def on_startup():
    create_db_and_tables()


@app.post("/create_user")
async def create_user(user_create: UserCreate, db: Session = Depends(get_session)):
    user = User(**user_create.dict())
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"message": "User created successfully", "user": user}


@app.post("/create_loan")
async def create_loan(loan_create: LoanCreate, db: Session = Depends(get_session)):
    loan = Loan(**loan_create.dict())
    db.add(loan)
    db.commit()
    db.refresh(loan)
    return {"message": "Loan created successfully", "loan": loan}


def calculate_monthly_payment(amount: float, annual_interest_rate: float, loan_term: int) -> float:
    monthly_interest_rate = annual_interest_rate / 12 / 100
    return (amount * monthly_interest_rate) / (1 - (1 + monthly_interest_rate) ** -loan_term)


def calculate_loan_schedule(amount: float, annual_interest_rate: float, loan_term: int) -> List[LoanSchedule]:
    schedules = []
    remaining_balance = amount
    monthly_interest_rate = annual_interest_rate / 12 / 100
    monthly_payment = calculate_monthly_payment(amount, annual_interest_rate, loan_term)

    for month in range(1, loan_term + 1):
        interest_payment = remaining_balance * monthly_interest_rate
        principal_payment = monthly_payment - interest_payment
        remaining_balance -= principal_payment

        cur_schedule = LoanSchedule(
            month=month,
            remaining_balance=round(remaining_balance, 2),
            monthly_payment=round(monthly_payment, 2),
        )
        schedules.append(cur_schedule)

    return schedules


@app.get("/loan/{loan_id}/schedule")
async def loan_schedule(loan_id: int, db: Session = Depends(get_session)):
    loan = db.get(Loan, loan_id)
    if not loan:
        raise HTTPException(status_code=404, detail="Loan not found")

    schedule = calculate_loan_schedule(loan.amount, loan.annual_interest_rate, loan.loan_term)
    return {"message": "Loan schedule fetched successfully", "loan_schedule": schedule}


def calculate_loan_summary(amount: float, month_number: int, schedule: List[LoanSchedule]) -> LoanSummary:
    current_principal_balance = schedule[month_number - 1].remaining_balance
    total_paid = schedule[0].monthly_payment * month_number

    aggregate_principal_paid = amount - current_principal_balance
    aggregate_interest_paid = total_paid - aggregate_principal_paid

    cur_loan_summary = LoanSummary(
        current_principal_balance=round(current_principal_balance, 2),
        aggregate_principal_paid=round(aggregate_principal_paid, 2),
        aggregate_interest_paid=round(aggregate_interest_paid, 2),
    )

    return cur_loan_summary


@app.get("/loan/{loan_id}/summary")
async def loan_summary(loan_id: int, month: int, db: Session = Depends(get_session)):
    loan = db.get(Loan, loan_id)
    if not loan:
        raise HTTPException(status_code=404, detail="Loan not found")

    if month > loan.loan_term:
        raise HTTPException(status_code=400, detail="Invalid month number")

    schedule = calculate_loan_schedule(loan.amount, loan.annual_interest_rate, loan.loan_term)
    cur_loan_summary = calculate_loan_summary(loan.amount, month, schedule)
    return {"message": "Loan summary fetched successfully", "loan_summary": cur_loan_summary}


@app.get("/user/{user_id}/loans")
async def user_loans(user_id: int, db: Session = Depends(get_session)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user_loans_all = db.query(Loan).filter(getattr(Loan, "user_id") == User.id).all()
    return {"message": "User loans fetched successfully", "user_loans": user_loans_all}


@app.post("/loan/{loan_id}/share/{recipient_user_id}")
async def share_loan(loan_id: int, recipient_user_id: int, db: Session = Depends(get_session)):
    loan = db.get(Loan, loan_id)
    if not loan:
        raise HTTPException(status_code=404, detail="Loan not found")

    recipient_user = db.get(User, recipient_user_id)
    if not recipient_user:
        raise HTTPException(status_code=404, detail="Recipient user not found")

    if loan.user_id == recipient_user.id:
        raise HTTPException(status_code=404, detail="Loan cannot be shared with the original owner")

    new_loan = Loan(
        user_id=recipient_user.id,
        amount=loan.amount,
        annual_interest_rate=loan.annual_interest_rate,
        loan_term=loan.loan_term,
    )
    db.add(new_loan)
    db.commit()
    db.refresh(new_loan)

    return {"message": "Loan shared successfully", "shared_loan": new_loan}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
