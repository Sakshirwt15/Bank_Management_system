# Bank Management System

A web-based banking application that I built using **Python (Flask)** and **SQL (SQLite)**.

I made this project to understand how the basic services of a bank work behind the scenes, such as opening an account, depositing and withdrawing money, fixed deposits and loans.

## What this project can do

- **Open an account:** Savings or Current account with KYC details. A minimum balance has to be maintained. The 4-digit PIN is stored in hashed form, not as plain text.
- **Transactions:** Deposit, withdraw and transfer money to another account. Every transaction is saved and shown in the account statement.
- **Fixed Deposit (FD):** Open an FD for a chosen period, see the maturity amount (interest is compounded quarterly), and redeem it. If the FD is broken early, a 1% penalty is charged and no interest is paid.
- **Loans:** Apply for a Home, Car or Personal loan. The app calculates the EMI and checks eligibility. If the customer is not eligible, it shows the maximum loan amount they can get. EMIs can be paid from the account.
- **Calculators:** EMI calculator and FD maturity calculator. These work without login.

## Technologies used

- Python and Flask (backend)
- SQL with SQLite (database)
- HTML, CSS and Jinja2 templates (frontend)
- pytest (unit tests) and gunicorn (deployment)

## Project structure

```
Bank_Management_system/
├── app.py            # web routes (pages and forms)
├── banking.py        # banking rules and formulas
├── db.py             # database connection
├── schema.sql        # SQL tables
├── templates/        # HTML pages
├── static/           # CSS
├── tests/            # unit tests
├── requirements.txt  # libraries needed
├── Procfile          # start command for hosting
└── render.yaml       # settings for deployment on Render
```

The database has 5 tables: `customers`, `accounts`, `transactions`, `fixed_deposits` and `loans`.

## How to run it on your computer

1. Install Python 3 and download this project.
2. Open a terminal inside the project folder and run:

```
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

On Mac or Linux, use `source venv/bin/activate` instead of `venv\Scripts\activate`.

3. Open `http://127.0.0.1:5000` in the browser.
4. Click **Open Account**. After the account is created, you will get an account number. Use it with your PIN to log in.
5. After logging in, the **Fixed Deposit** and **Loans** pages are available in the top menu.

To run the tests: `pip install -r requirements-dev.txt` and then `pytest`.

## How the main calculations work

- **EMI** = P × r × (1 + r)^n / ((1 + r)^n − 1), where P is the loan amount, r is the monthly interest rate (annual rate / 12 / 100) and n is the number of months.
- **FD maturity amount** = P × (1 + rate / 400)^(4 × years), because interest is compounded 4 times a year.
- **Loan eligibility:** the total of all EMIs should not be more than 50% of the monthly income.

## Things I handled while building it

- If any step of a transaction fails, everything is rolled back. For example, in a transfer, money is not deducted from one account unless it is added to the other.
- The minimum balance is checked inside the SQL update itself, so the balance cannot go below the limit.
- Wrong inputs (negative amounts, invalid phone number, wrong PIN, unknown account) show a clear message to the user.
- I wrote 15 unit tests for the formulas, minimum balance, transfers, FD and loan rules.

## Limitations and what I want to add next

- Interest rates and rules in this project are only examples. They are not the real rates of any bank.
- There is no OTP login, PIN lock after wrong attempts or CSRF protection yet.
- SQLite is fine for a demo project. For many users, a database like PostgreSQL would be better.
- Next, I want to add interest on savings accounts, an admin panel and a downloadable statement.

## About me

**Sakshi Rawat**
B.Tech in Computer Science and Engineering, Graphic Era Hill University, Dehradun
GitHub: [github.com/sakshirwt15](https://github.com/sakshirwt15)

> This is an educational project. Please do not enter real personal or banking details in it.
