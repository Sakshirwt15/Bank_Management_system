"""Business logic of the Mini Banking System.

Every function takes an open database connection (`db`). Functions raise
BankError when a banking rule is broken; the web layer shows that message
to the user and rolls the transaction back.
"""
import math
import random
from datetime import date, timedelta

from werkzeug.security import check_password_hash, generate_password_hash

# ----------------------------------------------------------------- rules
MIN_BALANCE = {"SAVINGS": 1000.0, "CURRENT": 5000.0}
ID_TYPES = ["Aadhaar", "PAN", "Passport", "Voter ID", "Driving Licence"]
FD_MIN_AMOUNT = 5000.0
FD_PENALTY_PERCENT = 1.0          # penalty on principal if FD is broken early
FD_RATE_SLABS = [(6, 5.75), (12, 6.50), (24, 7.00), (60, 6.75), (120, 6.50)]  # (up to months, % p.a.)
LOAN_RATES = {"HOME": 8.75, "CAR": 9.50, "PERSONAL": 11.00}                    # illustrative % p.a.
FOIR_LIMIT = 0.50                 # total EMIs may be at most 50% of monthly income
MAX_AMOUNT = 10_00_00_000         # 10 crore safety limit

CREDIT_TYPES = ("DEPOSIT", "TRANSFER_IN", "FD_REDEEM", "LOAN_DISBURSAL")


class BankError(Exception):
    """A banking rule was violated. The message is safe to show to the user."""


# ------------------------------------------------------------ formatting
def format_inr(value):
    """12345678.5 -> ₹1,23,45,678.50 (Indian digit grouping)."""
    value = float(value)
    whole, frac = f"{abs(value):.2f}".split(".")
    if len(whole) > 3:
        head, tail, parts = whole[:-3], whole[-3:], []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        whole = ",".join(parts + [tail])
    return f"{'-' if value < 0 else ''}₹{whole}.{frac}"


# --------------------------------------------------------------- parsing
def parse_amount(text):
    try:
        value = round(float(str(text).replace(",", "").strip()), 2)
    except (ValueError, TypeError):
        raise BankError("Please enter a valid amount.")
    if not math.isfinite(value) or value <= 0 or value > MAX_AMOUNT:
        raise BankError("Amount must be greater than zero and below ₹10 crore.")
    return value


def parse_int(text, label, low, high):
    try:
        value = int(str(text).strip())
    except (ValueError, TypeError):
        raise BankError(f"Please enter a valid {label}.")
    if not low <= value <= high:
        raise BankError(f"{label.capitalize()} must be between {low} and {high}.")
    return value


def parse_rate(text, low=0.0, high=40.0):
    try:
        value = float(str(text).strip())
    except (ValueError, TypeError):
        raise BankError("Please enter a valid interest rate.")
    if not math.isfinite(value) or not low <= value <= high:
        raise BankError(f"Interest rate must be between {low} and {high}%.")
    return value


# ---------------------------------------------------------- calculations
def calculate_emi(principal, annual_rate, months):
    """EMI = P * r * (1+r)^n / ((1+r)^n - 1), r = monthly interest rate."""
    r = annual_rate / 12 / 100
    if r == 0:
        return round(principal / months, 2)
    factor = (1 + r) ** months
    return round(principal * r * factor / (factor - 1), 2)


def max_loan_amount(emi, annual_rate, months):
    """Reverse of the EMI formula: the largest loan a given EMI can repay."""
    if emi <= 0:
        return 0.0
    r = annual_rate / 12 / 100
    if r == 0:
        return round(emi * months, 2)
    factor = (1 + r) ** months
    return round(emi * (factor - 1) / (r * factor), 2)


def fd_rate_for(months):
    for upto_months, rate in FD_RATE_SLABS:
        if months <= upto_months:
            return rate
    return FD_RATE_SLABS[-1][1]


def fd_maturity(principal, annual_rate, months):
    """Quarterly compounding: A = P * (1 + r/4) ^ (4t), r as a fraction."""
    return round(principal * (1 + annual_rate / 400) ** (4 * months / 12), 2)


def fd_quote(amount, months, rate=None):
    rate = fd_rate_for(months) if rate is None else rate
    maturity = fd_maturity(amount, rate, months)
    return {"amount": amount, "months": months, "rate": rate,
            "maturity": maturity, "interest": round(maturity - amount, 2)}


def emi_quote(amount, rate, months):
    emi = calculate_emi(amount, rate, months)
    total = round(emi * months, 2)
    return {"amount": amount, "rate": rate, "months": months, "emi": emi,
            "total_payable": total, "total_interest": round(total - amount, 2)}


# --------------------------------------------------------------- accounts
def get_account(db, account_id):
    return db.execute(
        "SELECT a.*, c.name AS customer_name, c.phone, c.email "
        "FROM accounts a JOIN customers c ON c.id = a.customer_id WHERE a.id = ?",
        (account_id,)).fetchone()


def _generate_account_no(db):
    while True:
        number = "10" + "".join(random.choices("0123456789", k=9))
        if not db.execute("SELECT 1 FROM accounts WHERE account_no = ?", (number,)).fetchone():
            return number


def create_account(db, name, phone, email, id_type, id_number,
                   account_type, pin, confirm_pin, opening_amount):
    name, phone, email, id_number = name.strip(), phone.strip(), email.strip(), id_number.strip()
    if len(name) < 3:
        raise BankError("Please enter your full name.")
    if not (phone.isdigit() and len(phone) == 10):
        raise BankError("Phone number must be 10 digits.")
    if "@" not in email or "." not in email:
        raise BankError("Please enter a valid email address.")
    if id_type not in ID_TYPES or len(id_number) < 4:
        raise BankError("Please provide valid KYC details.")
    if account_type not in MIN_BALANCE:
        raise BankError("Choose a valid account type.")
    if not (pin.isdigit() and len(pin) == 4):
        raise BankError("PIN must be exactly 4 digits.")
    if pin != confirm_pin:
        raise BankError("PIN and confirm PIN do not match.")
    minimum = MIN_BALANCE[account_type]
    if opening_amount < minimum:
        raise BankError(f"Minimum opening deposit for a {account_type.title()} account is {format_inr(minimum)}.")

    customer_id = db.execute(
        "INSERT INTO customers (name, phone, email, id_type, id_number) VALUES (?, ?, ?, ?, ?)",
        (name, phone, email, id_type, id_number)).lastrowid
    account_no = _generate_account_no(db)
    account_id = db.execute(
        "INSERT INTO accounts (account_no, customer_id, account_type, pin_hash, balance) VALUES (?, ?, ?, ?, ?)",
        (account_no, customer_id, account_type, generate_password_hash(pin), opening_amount)).lastrowid
    _record(db, account_id, "DEPOSIT", opening_amount, opening_amount, "Opening deposit")
    return f"Account created! Your account number is {account_no}. Please log in."


def authenticate(db, account_no, pin):
    account = db.execute("SELECT * FROM accounts WHERE account_no = ?", (account_no.strip(),)).fetchone()
    if account and check_password_hash(account["pin_hash"], pin):
        return account
    return None


# ----------------------------------------------------------- transactions
def _record(db, account_id, txn_type, amount, balance_after, description):
    db.execute(
        "INSERT INTO transactions (account_id, txn_type, amount, balance_after, description) "
        "VALUES (?, ?, ?, ?, ?)", (account_id, txn_type, amount, balance_after, description))


def _credit(db, account_id, amount, txn_type, description):
    db.execute("UPDATE accounts SET balance = ROUND(balance + ?, 2) WHERE id = ?", (amount, account_id))
    balance = get_account(db, account_id)["balance"]
    _record(db, account_id, txn_type, amount, balance, description)
    return balance


def _debit(db, account_id, amount, txn_type, description):
    """Debit only if the minimum balance is still maintained afterwards.
    The check is part of the UPDATE itself, so it is safe even with two requests at once."""
    floor = MIN_BALANCE[get_account(db, account_id)["account_type"]]
    cursor = db.execute(
        "UPDATE accounts SET balance = ROUND(balance - ?, 2) WHERE id = ? AND balance - ? >= ?",
        (amount, account_id, amount, floor))
    if cursor.rowcount == 0:
        raise BankError(f"Insufficient funds. A minimum balance of {format_inr(floor)} must be maintained.")
    balance = get_account(db, account_id)["balance"]
    _record(db, account_id, txn_type, amount, balance, description)
    return balance


def deposit(db, account_id, amount):
    balance = _credit(db, account_id, amount, "DEPOSIT", "Cash deposit")
    return f"Deposited {format_inr(amount)}. New balance: {format_inr(balance)}."


def withdraw(db, account_id, amount):
    balance = _debit(db, account_id, amount, "WITHDRAWAL", "Cash withdrawal")
    return f"Withdrew {format_inr(amount)}. New balance: {format_inr(balance)}."


def transfer(db, from_account_id, to_account_no, amount):
    target = db.execute("SELECT * FROM accounts WHERE account_no = ?", (to_account_no.strip(),)).fetchone()
    if target is None:
        raise BankError("Beneficiary account not found.")
    if target["id"] == from_account_id:
        raise BankError("You cannot transfer money to your own account.")
    source_no = get_account(db, from_account_id)["account_no"]
    balance = _debit(db, from_account_id, amount, "TRANSFER_OUT", f"Transfer to {target['account_no']}")
    _credit(db, target["id"], amount, "TRANSFER_IN", f"Transfer from {source_no}")
    return f"Transferred {format_inr(amount)} to {target['account_no']}. New balance: {format_inr(balance)}."


def get_transactions(db, account_id, limit=50):
    return db.execute("SELECT * FROM transactions WHERE account_id = ? ORDER BY id DESC LIMIT ?",
                      (account_id, limit)).fetchall()


# --------------------------------------------------------- fixed deposits
def open_fd(db, account_id, amount, months):
    if amount < FD_MIN_AMOUNT:
        raise BankError(f"Minimum FD amount is {format_inr(FD_MIN_AMOUNT)}.")
    quote = fd_quote(amount, months)
    _debit(db, account_id, amount, "FD_OPEN", f"Opened FD for {months} months @ {quote['rate']}%")
    start = date.today()
    db.execute(
        "INSERT INTO fixed_deposits (account_id, principal, interest_rate, tenure_months, "
        "maturity_amount, start_date, maturity_date) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (account_id, amount, quote["rate"], months, quote["maturity"],
         start.isoformat(), (start + timedelta(days=round(months * 30.4))).isoformat()))
    return (f"FD opened for {format_inr(amount)} at {quote['rate']}% p.a. "
            f"Maturity amount: {format_inr(quote['maturity'])}.")


def list_fds(db, account_id):
    today = date.today().isoformat()
    rows = db.execute("SELECT * FROM fixed_deposits WHERE account_id = ? ORDER BY id DESC", (account_id,)).fetchall()
    return [dict(row, matured=row["maturity_date"] <= today) for row in rows]


def redeem_fd(db, account_id, fd_id):
    fd = db.execute("SELECT * FROM fixed_deposits WHERE id = ? AND account_id = ? AND status = 'ACTIVE'",
                    (fd_id, account_id)).fetchone()
    if fd is None:
        raise BankError("Active FD not found.")
    if fd["maturity_date"] <= date.today().isoformat():
        payout, note = fd["maturity_amount"], "FD matured"
    else:
        payout = round(fd["principal"] * (1 - FD_PENALTY_PERCENT / 100), 2)
        note = f"FD closed early ({FD_PENALTY_PERCENT}% penalty, no interest)"
    db.execute("UPDATE fixed_deposits SET status = 'CLOSED' WHERE id = ?", (fd_id,))
    _credit(db, account_id, payout, "FD_REDEEM", f"{note} - FD #{fd_id}")
    return f"{note}. {format_inr(payout)} credited to your account."


# ------------------------------------------------------------------ loans
def _active_emi_total(db, account_id):
    return db.execute("SELECT COALESCE(SUM(emi), 0) FROM loans WHERE account_id = ? AND status = 'ACTIVE'",
                      (account_id,)).fetchone()[0]


def loan_quote(db, account_id, loan_type, amount, months, monthly_income):
    if loan_type not in LOAN_RATES:
        raise BankError("Choose a valid loan type.")
    if amount < 10_000:
        raise BankError("Minimum loan amount is ₹10,000.")
    rate = LOAN_RATES[loan_type]
    quote = emi_quote(amount, rate, months)
    allowed = max(round(monthly_income * FOIR_LIMIT - _active_emi_total(db, account_id), 2), 0.0)
    quote.update(loan_type=loan_type, allowed_emi=allowed, eligible=quote["emi"] <= allowed,
                 max_amount=max_loan_amount(allowed, rate, months))
    return quote


def apply_loan(db, account_id, loan_type, amount, months, monthly_income):
    quote = loan_quote(db, account_id, loan_type, amount, months, monthly_income)
    if not quote["eligible"]:
        raise BankError(
            f"Not eligible: the EMI of {format_inr(quote['emi'])} is more than your allowed EMI of "
            f"{format_inr(quote['allowed_emi'])}. You may be eligible for up to {format_inr(quote['max_amount'])}.")
    db.execute(
        "INSERT INTO loans (account_id, loan_type, principal, interest_rate, tenure_months, emi) "
        "VALUES (?, ?, ?, ?, ?, ?)", (account_id, loan_type, amount, quote["rate"], months, quote["emi"]))
    _credit(db, account_id, amount, "LOAN_DISBURSAL", f"{loan_type.title()} loan disbursed")
    return f"Loan approved! {format_inr(amount)} credited. Your EMI is {format_inr(quote['emi'])} per month."


def list_loans(db, account_id):
    return db.execute("SELECT * FROM loans WHERE account_id = ? ORDER BY id DESC", (account_id,)).fetchall()


def pay_emi(db, account_id, loan_id):
    loan = db.execute("SELECT * FROM loans WHERE id = ? AND account_id = ? AND status = 'ACTIVE'",
                      (loan_id, account_id)).fetchone()
    if loan is None:
        raise BankError("Active loan not found.")
    _debit(db, account_id, loan["emi"], "EMI_PAYMENT",
           f"EMI {loan['emis_paid'] + 1}/{loan['tenure_months']} - Loan #{loan_id}")
    paid = loan["emis_paid"] + 1
    db.execute("UPDATE loans SET emis_paid = ?, status = ? WHERE id = ?",
               (paid, "CLOSED" if paid >= loan["tenure_months"] else "ACTIVE", loan_id))
    return f"EMI of {format_inr(loan['emi'])} paid ({paid}/{loan['tenure_months']})."
