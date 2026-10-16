"""Mini Banking System - Flask web application (routes only; rules live in banking.py)."""
import os
from functools import wraps

from flask import Flask, flash, g, redirect, render_template, request, session, url_for

import banking
from db import close_db, get_db, init_db

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-only-change-me")
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
os.makedirs(app.instance_path, exist_ok=True)
app.config["DATABASE"] = os.environ.get("DATABASE_PATH", os.path.join(app.instance_path, "bank.db"))
app.teardown_appcontext(close_db)
app.jinja_env.filters["inr"] = banking.format_inr

with app.app_context():
    init_db()


# ---------------------------------------------------------------- helpers
@app.before_request
def load_logged_in_account():
    g.account = None
    account_id = session.get("account_id")
    if account_id:
        g.account = banking.get_account(get_db(), account_id)
        if g.account is None:
            session.clear()


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.account is None:
            flash("Please log in first.", "error")
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


def perform(action):
    """Run a banking action inside one DB transaction: commit on success, roll back on any error."""
    db = get_db()
    try:
        message = action(db)
        db.commit()
        flash(message, "success")
        return True
    except banking.BankError as error:
        db.rollback()
        flash(str(error), "error")
        return False


# ----------------------------------------------------------- public pages
@app.route("/")
def home():
    return render_template("home.html")


@app.route("/healthz")
def healthz():
    return {"status": "ok"}


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        f = request.form

        def action(db):
            return banking.create_account(
                db, f.get("name", ""), f.get("phone", ""), f.get("email", ""), f.get("id_type", ""),
                f.get("id_number", ""), f.get("account_type", ""), f.get("pin", ""), f.get("confirm_pin", ""),
                banking.parse_amount(f.get("opening_amount")))

        if perform(action):
            return redirect(url_for("login"))
    return render_template("register.html", form=request.form, id_types=banking.ID_TYPES,
                           min_balance=banking.MIN_BALANCE)


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        account = banking.authenticate(get_db(), request.form.get("account_no", ""), request.form.get("pin", ""))
        if account:
            session.clear()
            session["account_id"] = account["id"]
            return redirect(url_for("dashboard"))
        flash("Invalid account number or PIN.", "error")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("home"))


@app.route("/calculators", methods=["GET", "POST"])
def calculators():
    emi = fd = None
    if request.method == "POST":
        f = request.form
        try:
            amount = banking.parse_amount(f.get("amount"))
            months = banking.parse_int(f.get("months"), "tenure (months)", 1, 360)
            rate = banking.parse_rate(f.get("rate"))
            if f.get("calc") == "fd":
                fd = banking.fd_quote(amount, months, rate)
            else:
                emi = banking.emi_quote(amount, rate, months)
        except banking.BankError as error:
            flash(str(error), "error")
    return render_template("calculators.html", emi=emi, fd=fd, form=request.form)


# --------------------------------------------------- logged-in pages
@app.route("/dashboard")
@login_required
def dashboard():
    db, account_id = get_db(), g.account["id"]
    return render_template(
        "dashboard.html", transactions=banking.get_transactions(db, account_id, 5),
        fd_count=len(banking.list_fds(db, account_id)), loan_count=len(banking.list_loans(db, account_id)))


@app.post("/deposit")
@login_required
def deposit():
    perform(lambda db: banking.deposit(db, g.account["id"], banking.parse_amount(request.form.get("amount"))))
    return redirect(url_for("dashboard"))


@app.post("/withdraw")
@login_required
def withdraw():
    perform(lambda db: banking.withdraw(db, g.account["id"], banking.parse_amount(request.form.get("amount"))))
    return redirect(url_for("dashboard"))


@app.post("/transfer")
@login_required
def transfer():
    perform(lambda db: banking.transfer(db, g.account["id"], request.form.get("to_account", ""),
                                        banking.parse_amount(request.form.get("amount"))))
    return redirect(url_for("dashboard"))


@app.route("/statement")
@login_required
def statement():
    return render_template("statement.html", transactions=banking.get_transactions(get_db(), g.account["id"], 100),
                           credit_types=banking.CREDIT_TYPES)


@app.route("/fd", methods=["GET", "POST"])
@login_required
def fixed_deposit():
    db, preview = get_db(), None
    if request.method == "POST":
        try:
            amount = banking.parse_amount(request.form.get("amount"))
            months = banking.parse_int(request.form.get("months"), "tenure (months)", 6, 120)
            if request.form.get("action") == "open":
                if perform(lambda d: banking.open_fd(d, g.account["id"], amount, months)):
                    return redirect(url_for("fixed_deposit"))
            else:
                preview = banking.fd_quote(amount, months)
        except banking.BankError as error:
            flash(str(error), "error")
    return render_template("fd.html", preview=preview, fds=banking.list_fds(db, g.account["id"]),
                           slabs=banking.FD_RATE_SLABS, min_amount=banking.FD_MIN_AMOUNT,
                           penalty=banking.FD_PENALTY_PERCENT, form=request.form)


@app.post("/fd/<int:fd_id>/redeem")
@login_required
def redeem_fd(fd_id):
    perform(lambda db: banking.redeem_fd(db, g.account["id"], fd_id))
    return redirect(url_for("fixed_deposit"))


@app.route("/loan", methods=["GET", "POST"])
@login_required
def loan():
    db, quote = get_db(), None
    if request.method == "POST":
        f = request.form
        try:
            amount = banking.parse_amount(f.get("amount"))
            months = banking.parse_int(f.get("months"), "tenure (months)", 6, 360)
            income = banking.parse_amount(f.get("income"))
            if f.get("action") == "apply":
                if perform(lambda d: banking.apply_loan(d, g.account["id"], f.get("loan_type", ""),
                                                        amount, months, income)):
                    return redirect(url_for("loan"))
            else:
                quote = banking.loan_quote(db, g.account["id"], f.get("loan_type", ""), amount, months, income)
        except banking.BankError as error:
            flash(str(error), "error")
    return render_template("loan.html", quote=quote, loans=banking.list_loans(db, g.account["id"]),
                           rates=banking.LOAN_RATES, foir=int(banking.FOIR_LIMIT * 100), form=request.form)


@app.post("/loan/<int:loan_id>/pay")
@login_required
def pay_emi(loan_id):
    perform(lambda db: banking.pay_emi(db, g.account["id"], loan_id))
    return redirect(url_for("loan"))


if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1")
