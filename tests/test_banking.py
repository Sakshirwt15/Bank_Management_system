import pathlib
import sqlite3

import pytest

import banking
from banking import BankError

SCHEMA = (pathlib.Path(__file__).parent.parent / "schema.sql").read_text()


@pytest.fixture
def db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    yield conn
    conn.close()


def make_account(db, amount=10000.0, account_type="SAVINGS", name="Test User"):
    banking.create_account(db, name, "9876543210", "t@example.com", "Aadhaar", "123456789012",
                           account_type, "1234", "1234", amount)
    row = db.execute("SELECT id, account_no FROM accounts ORDER BY id DESC LIMIT 1").fetchone()
    return row["id"], row["account_no"]


# ---------------------------------------------------------- formulas
def test_emi_matches_known_value():
    assert banking.calculate_emi(1_000_000, 10, 120) == pytest.approx(13215.07, abs=0.01)


def test_emi_zero_interest():
    assert banking.calculate_emi(120000, 0, 12) == 10000.0


def test_max_loan_is_reverse_of_emi():
    emi = banking.calculate_emi(500000, 9, 60)
    assert banking.max_loan_amount(emi, 9, 60) == pytest.approx(500000, abs=1)


def test_fd_maturity_quarterly_compounding():
    assert banking.fd_maturity(100000, 7, 12) == pytest.approx(107186.5, abs=1)


def test_inr_format():
    assert banking.format_inr(12345678.5) == "₹1,23,45,678.50"
    assert banking.format_inr(999) == "₹999.00"


# ------------------------------------------------------- transactions
def test_deposit_and_withdraw(db):
    acc, _ = make_account(db, 10000)
    banking.deposit(db, acc, 500)
    banking.withdraw(db, acc, 1500)
    assert banking.get_account(db, acc)["balance"] == 9000


def test_minimum_balance_is_enforced(db):
    acc, _ = make_account(db, 2000)
    with pytest.raises(BankError):
        banking.withdraw(db, acc, 1500)       # would leave 500 < 1000


def test_transfer_moves_money_and_logs_both_sides(db):
    a, _ = make_account(db, 10000)
    b, b_no = make_account(db, 5000, name="Other User")
    banking.transfer(db, a, b_no, 2000)
    assert banking.get_account(db, a)["balance"] == 8000
    assert banking.get_account(db, b)["balance"] == 7000
    assert banking.get_transactions(db, b, 1)[0]["txn_type"] == "TRANSFER_IN"


def test_transfer_to_unknown_or_own_account_fails(db):
    a, a_no = make_account(db, 10000)
    with pytest.raises(BankError):
        banking.transfer(db, a, "1000000000", 100)
    with pytest.raises(BankError):
        banking.transfer(db, a, a_no, 100)


def test_wrong_pin_rejected(db):
    _, number = make_account(db)
    assert banking.authenticate(db, number, "1234") is not None
    assert banking.authenticate(db, number, "9999") is None


def test_opening_deposit_below_minimum_rejected(db):
    with pytest.raises(BankError):
        make_account(db, 500)


# ----------------------------------------------------------------- FD
def test_open_and_break_fd(db):
    acc, _ = make_account(db, 20000)
    banking.open_fd(db, acc, 10000, 12)
    assert banking.get_account(db, acc)["balance"] == 10000
    fd = banking.list_fds(db, acc)[0]
    assert fd["maturity_amount"] > 10000 and not fd["matured"]
    banking.redeem_fd(db, acc, fd["id"])          # early: 1% penalty
    assert banking.get_account(db, acc)["balance"] == 19900
    with pytest.raises(BankError):
        banking.redeem_fd(db, acc, fd["id"])      # already closed


def test_fd_below_minimum_rejected(db):
    acc, _ = make_account(db, 20000)
    with pytest.raises(BankError):
        banking.open_fd(db, acc, 1000, 12)


# --------------------------------------------------------------- loans
def test_loan_eligibility_and_emi_payment(db):
    acc, _ = make_account(db, 5000)
    with pytest.raises(BankError):
        banking.apply_loan(db, acc, "PERSONAL", 500000, 24, 20000)    # EMI too high
    banking.apply_loan(db, acc, "PERSONAL", 100000, 24, 50000)
    loan = banking.list_loans(db, acc)[0]
    assert banking.get_account(db, acc)["balance"] == 105000
    banking.pay_emi(db, acc, loan["id"])
    assert banking.list_loans(db, acc)[0]["emis_paid"] == 1


def test_existing_emi_reduces_eligibility(db):
    acc, _ = make_account(db, 5000)
    banking.apply_loan(db, acc, "PERSONAL", 200000, 24, 30000)   # EMI ~9,321 of 15,000 allowed
    quote = banking.loan_quote(db, acc, "PERSONAL", 200000, 24, 30000)
    assert not quote["eligible"]
