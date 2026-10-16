# Mini Banking System

A small banking web application built with **Python (Flask)** and **SQL (SQLite)**.
It covers the basic services of a bank: accounts with KYC, transactions, fixed deposits, loans, and EMI / FD calculators.

## Features
| Module | What it does |
|---|---|
| Accounts & KYC | Savings / Current account, KYC details, minimum balance rule, 4-digit PIN stored as a **hash** |
| Transactions | Deposit, withdraw, transfer to another account, statement with running balance |
| Fixed Deposit | Open FD (quarterly compounding), maturity calculator, redeem / break FD with 1% penalty |
| Loans | Home / Car / Personal loan, EMI, eligibility check (EMIs <= 50% of income), pay EMI |
| Calculators | Public EMI and FD maturity calculators (no login needed) |

## Tech stack
Python 3, Flask, SQLite (SQL), Jinja2 templates, HTML/CSS, gunicorn (deployment), pytest (tests).

## Project structure
```
mini_banking_system/
├── app.py              # Flask routes (web layer)
├── banking.py          # all banking rules + formulas (business logic)
├── db.py               # database connection helpers
├── schema.sql          # SQL tables (customers, accounts, transactions, fixed_deposits, loans)
├── templates/          # HTML pages (Jinja2)
├── static/style.css    # styling
├── tests/              # 15 unit tests
├── requirements.txt    # Flask, gunicorn
├── Procfile            # start command for hosting
└── render.yaml         # one-click config for Render
```

## Run on your computer
```bash
python -m venv venv
venv\Scripts\activate          # Windows      (Mac/Linux: source venv/bin/activate)
pip install -r requirements.txt
python app.py
```
Open http://127.0.0.1:5000 , open an account, and log in with the account number shown after registration.

Run the tests: `pip install -r requirements-dev.txt` then `pytest`.

## Deploy (free)
**Option A - Render (easiest)**
1. Create a GitHub repository and push this folder (`git init`, `git add .`, `git commit -m "first commit"`, then push).
2. On render.com: New > Web Service > connect your repo. Render reads `render.yaml`
   (or set Build command `pip install -r requirements.txt`, Start command `gunicorn app:app`).
3. Wait for the build; your live link is `https://<name>.onrender.com`.
> Note: on Render's free plan the SQLite file is reset when the service redeploys or restarts, so demo data can disappear.
> For permanent data use PythonAnywhere (below) or switch to PostgreSQL.

**Option B - PythonAnywhere (SQLite data stays)**
1. Create a free account, upload the folder (or `git clone` it in a Bash console).
2. Web tab > Add a new web app > Flask > point the WSGI file to `app` from `app.py`.
3. In a Bash console: `pip install --user flask`, then reload the web app.

Set an environment variable `SECRET_KEY` to a long random string in production (Render does this automatically).

## How the important parts work
* **EMI** = P x r x (1+r)^n / ((1+r)^n - 1) where r = annual rate / 12 / 100 and n = months.
* **FD maturity** = P x (1 + rate/400)^(4t) (quarterly compounding, t in years).
* **Eligibility (FOIR)**: new EMI + existing EMIs must be <= 50% of monthly income. Max loan = EMI x ((1+r)^n - 1) / (r x (1+r)^n).
* **Minimum balance** is checked inside the SQL `UPDATE` itself, so two simultaneous requests cannot overdraw the account.
* Each action runs in **one database transaction**: if anything fails, everything is rolled back (important for transfers).
* Interest rates and rules are illustrative values, not ICICI Bank's real rates.

## Limitations / future improvements (good to mention honestly)
* No CSRF protection or PIN lockout after wrong attempts; a real bank would also use OTP / 2-factor.
* Money stored as decimal numbers rounded to 2 places; production systems store paise as integers.
* SQLite is great for a demo; PostgreSQL would be used for many users.
* Ideas: monthly interest on savings, admin panel, downloadable PDF statement, suspicious-transaction rules.

## Interview questions you should be ready for
1. **Why this project?** I wanted to understand how basic banking services work behind the scenes: accounts, transactions, deposits and loans.
2. **Where is data stored?** In an SQL database with 5 tables linked by foreign keys (customers, accounts, transactions, fixed_deposits, loans).
3. **How is the PIN protected?** It is hashed (never stored as plain text) using Werkzeug's `generate_password_hash`.
4. **What happens if a transfer fails halfway?** All steps run in one transaction, so the whole thing is rolled back - no money is lost or created.
5. **How is EMI calculated?** Using the EMI formula above; the same project also shows total interest and total payable.
6. **How do you decide loan eligibility?** EMIs must stay within 50% of income (FOIR). If not eligible, the app tells the maximum loan amount the person can get.
7. **What is the difference between FD and savings account?** Savings: money available any time, low interest. FD: money locked for a period, higher interest; breaking early costs a penalty.
8. **What would you improve?** OTP login, PIN lockout, PostgreSQL, interest on savings, admin panel.
