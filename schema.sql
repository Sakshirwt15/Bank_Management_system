-- Mini Banking System: database schema (SQLite)
CREATE TABLE IF NOT EXISTS customers (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    phone       TEXT NOT NULL,
    email       TEXT NOT NULL,
    id_type     TEXT NOT NULL,          -- KYC document type
    id_number   TEXT NOT NULL,          -- KYC document number
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS accounts (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    account_no   TEXT NOT NULL UNIQUE,
    customer_id  INTEGER NOT NULL REFERENCES customers(id),
    account_type TEXT NOT NULL CHECK (account_type IN ('SAVINGS', 'CURRENT')),
    pin_hash     TEXT NOT NULL,         -- PIN is stored hashed, never as plain text
    balance      REAL NOT NULL CHECK (balance >= 0),
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS transactions (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id    INTEGER NOT NULL REFERENCES accounts(id),
    txn_type      TEXT NOT NULL,
    amount        REAL NOT NULL,
    balance_after REAL NOT NULL,
    description   TEXT NOT NULL,
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS fixed_deposits (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id      INTEGER NOT NULL REFERENCES accounts(id),
    principal       REAL NOT NULL,
    interest_rate   REAL NOT NULL,
    tenure_months   INTEGER NOT NULL,
    maturity_amount REAL NOT NULL,
    start_date      TEXT NOT NULL,
    maturity_date   TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'CLOSED'))
);

CREATE TABLE IF NOT EXISTS loans (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id    INTEGER NOT NULL REFERENCES accounts(id),
    loan_type     TEXT NOT NULL,
    principal     REAL NOT NULL,
    interest_rate REAL NOT NULL,
    tenure_months INTEGER NOT NULL,
    emi           REAL NOT NULL,
    emis_paid     INTEGER NOT NULL DEFAULT 0,
    status        TEXT NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'CLOSED')),
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_txn_account ON transactions(account_id);
CREATE INDEX IF NOT EXISTS idx_fd_account  ON fixed_deposits(account_id);
CREATE INDEX IF NOT EXISTS idx_loan_account ON loans(account_id);
