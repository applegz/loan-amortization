from fastapi import FastAPI, HTTPException, Path, Query

app = FastAPI()

# In-memory storage for user and loan data
users_db = []
loans_db = []


class User:
    def __init__(self, username: str):
        self.username = username


class Loan:
    def __init__(self, username: str, amount: float, annual_interest_rate: float, loan_term: int):
        self.username = username
        self.amount = amount
        self.annual_interest_rate = annual_interest_rate
        self.loan_term = loan_term
        self.remaining_balance = amount
        self.monthly_payment = self.calculate_monthly_payment()
        self.payment_schedule = self.calculate_payment_schedule()

    def calculate_monthly_payment(self):
        monthly_interest_rate = self.annual_interest_rate / 12 / 100
        return (self.amount * monthly_interest_rate) / (1 - (1 + monthly_interest_rate) ** -self.loan_term)

    def calculate_payment_schedule(self):
        schedule = []
        for month in range(1, self.loan_term + 1):
            interest_payment = self.remaining_balance * (self.annual_interest_rate / 12 / 100)
            principal_payment = self.monthly_payment - interest_payment
            self.remaining_balance -= principal_payment
            schedule.append({
                "Month": month,
                "Remaining Balance": round(self.remaining_balance, 2),
                "Monthly Payment": round(self.monthly_payment, 2)
            })
        return schedule


@app.post("/create_user/{username}")
async def create_user(username: str):
    new_user = User(username=username)
    users_db.append(new_user)
    return {"message": "User created successfully", "user": new_user.__dict__}


@app.post("/create_loan")
async def create_loan(username: str, amount: float, annual_interest_rate: float, loan_term: int):
    if username in users_db:
        new_loan = Loan(username=username,
                        amount=amount,
                        annual_interest_rate=annual_interest_rate,
                        loan_term=loan_term)
        loans_db.append(new_loan)
        return {"message": "Loan created successfully", "loan": new_loan.__dict__}
    else:
        raise HTTPException(status_code=400, detail="Username not found")


@app.get("/loan_schedule/{loan_id}")
async def loan_schedule(loan_id: int = Path(..., title="The ID of the loan", gt=0, description="Loan ID")):
    try:
        loan = loans_db[loan_id - 1]
        return {"message": "Loan schedule fetched successfully", "loan_schedule": loan.payment_schedule}
    except IndexError:
        raise HTTPException(status_code=404, detail="Loan not found")


@app.get("/loan_summary/{loan_id}")
async def loan_summary(loan_id: int = Path(..., title="The ID of the loan", gt=0, description="Loan ID"),
                       month: int = Query(..., title="The month number", ge=1, description="Month number")):
    try:
        loan = loans_db[loan_id - 1]
        if month > loan.loan_term:
            raise HTTPException(status_code=400, detail="Invalid month number")
        summary = loan.payment_schedule[month - 1]
        return {"message": "Loan summary fetched successfully", "loan_summary": summary}
    except IndexError:
        raise HTTPException(status_code=404, detail="Loan not found")


@app.get("/user_loans/{username}")
async def user_loans(username: str):
    user_loans_all = [loan.__dict__ for loan in loans_db if loan.username == username]
    return {"message": "User loans fetched successfully", "user_loans": user_loans_all}


@app.post("/share_loan/{loan_id}/{recipient_username}")
async def share_loan(loan_id: int = Path(..., title="The ID of the loan", gt=0, description="Loan ID"),
                     recipient_username: str = Path(..., title="The username of the recipient",
                                                    description="Recipient Username")):
    try:
        loan = loans_db[loan_id - 1]
        recipient_user = next((user for user in users_db if user.username == recipient_username), None)
        if recipient_user is None:
            raise HTTPException(status_code=404, detail="Recipient user not found")
        new_loan = Loan(username=recipient_user.username,
                        amount=loan.amount,
                        annual_interest_rate=loan.annual_interest_rate,
                        loan_term=loan.loan_term)
        loans_db.append(new_loan)
        return {"message": "Loan shared successfully", "shared_loan": new_loan.__dict__}
    except IndexError:
        raise HTTPException(status_code=404, detail="Loan not found")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
