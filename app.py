from datetime import datetime
import os, random
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.secret_key = "dev-secret" 
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///hsa.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

QUALIFIED = {"pharmacy", "dental", "vision", "clinic", "medical_equipment"}

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)

class Account(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    balance_cents = db.Column(db.Integer, default=0)

class Card(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(db.Integer, db.ForeignKey("account.id"), nullable=False)
    last4 = db.Column(db.String(4), nullable=False)
    token = db.Column(db.String(32), nullable=False)  # pseudo PAN, not real
    exp_month = db.Column(db.Integer, nullable=False)
    exp_year = db.Column(db.Integer, nullable=False)
    active = db.Column(db.Boolean, default=True)

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(db.Integer, db.ForeignKey("account.id"), nullable=False)
    card_id = db.Column(db.Integer, db.ForeignKey("card.id"), nullable=True)
    merchant = db.Column(db.String(120), nullable=False)
    category = db.Column(db.String(64), nullable=False)
    amount_cents = db.Column(db.Integer, nullable=False)
    approved = db.Column(db.Boolean, default=False)
    reason = db.Column(db.String(200), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

def dollars_to_cents(d: str) -> int:
    parts = d.strip().split(".")
    if len(parts) == 1:
        return int(parts[0]) * 100
    whole, frac = parts[0], (parts[1] + "00")[:2]
    return int(whole) * 100 + int(frac)

def generate_card_token():
    digits = "".join(str(random.randint(0, 9)) for _ in range(16))
    return digits

# ---- Routes ----
@app.route("/", methods=["GET"])
def home():
    if session.get("account_id"):
        return redirect(url_for("dashboard"))
    return render_template("home.html")

@app.route("/register", methods=["POST"])
def register():
    name = request.form.get("name", "").strip()
    if not name:
        flash("Please enter your name.")
        return redirect(url_for("home"))
    
    # Check if user with this name already exists
    existing_user = User.query.filter_by(name=name).first()
    if existing_user:
        flash(f"Account with name '{name}' already exists. Please use the Login option or choose a different name.")
        return redirect(url_for("home"))
    
    user = User(name=name)
    db.session.add(user)
    db.session.commit()

    acct = Account(user_id=user.id, balance_cents=0)
    db.session.add(acct)
    db.session.commit()

    session["account_id"] = acct.id
    flash(f"Account created for {name}.")
    return redirect(url_for("dashboard"))

@app.route("/dashboard", methods=["GET"])
def dashboard():
    acct_id = session.get("account_id")
    if not acct_id:
        return redirect(url_for("home"))
    acct = Account.query.get(acct_id)
    user = User.query.get(acct.user_id)
    cards = Card.query.filter_by(account_id=acct.id, active=True).all()
    txns = Transaction.query.filter_by(account_id=acct.id).order_by(Transaction.created_at.desc()).all()
    return render_template("dashboard.html",
                           user=user, acct=acct, cards=cards, txns=txns,
                           qualified=sorted(list(QUALIFIED)))

@app.route("/deposit", methods=["POST"])
def deposit():
    acct_id = session.get("account_id")
    if not acct_id:
        return redirect(url_for("home"))
    amount = request.form.get("amount", "0").strip()
    try:
        cents = dollars_to_cents(amount)
        if cents <= 0:
            raise ValueError
    except Exception:
        flash("Enter a valid positive deposit amount.")
        return redirect(url_for("dashboard"))

    acct = Account.query.get(acct_id)
    acct.balance_cents += cents
    db.session.commit()
    flash(f"Deposited ${cents/100:.2f}.")
    return redirect(url_for("dashboard"))

@app.route("/issue-card", methods=["POST"])
def issue_card():
    acct_id = session.get("account_id")
    if not acct_id:
        return redirect(url_for("home"))
    token = generate_card_token()
    last4 = token[-4:]
    now = datetime.utcnow()
    exp_month, exp_year = 12, now.year + 1
    card = Card(account_id=acct_id, last4=last4, token=token, exp_month=exp_month, exp_year=exp_year, active=True)
    db.session.add(card)
    db.session.commit()
    flash(f"Issued virtual card •••• {last4} (exp {exp_month}/{exp_year}).")
    return redirect(url_for("dashboard"))

@app.route("/purchase", methods=["POST"])
def purchase():
    acct_id = session.get("account_id")
    if not acct_id:
        return redirect(url_for("home"))

    merchant = request.form.get("merchant", "").strip()
    category = request.form.get("category", "").strip()
    amount = request.form.get("amount", "0").strip()
    card_id = request.form.get("card_id")

    if not merchant or not category or not amount or not card_id:
        flash("Please fill all purchase fields.")
        return redirect(url_for("dashboard"))

    try:
        cents = dollars_to_cents(amount)
        if cents <= 0:
            raise ValueError
    except Exception:
        flash("Enter a valid positive purchase amount.")
        return redirect(url_for("dashboard"))

    acct = Account.query.get(acct_id)
    card = Card.query.filter_by(id=card_id, account_id=acct_id, active=True).first()

    approved, reason = False, ""
    if category not in QUALIFIED:
        approved, reason = False, "Category not HSA-qualified."
    elif card is None:
        approved, reason = False, "Invalid or inactive card."
    elif acct.balance_cents < cents:
        approved, reason = False, "Insufficient balance."
    else:
        approved, reason = True, "Approved."

    txn = Transaction(
        account_id=acct_id,
        card_id=card.id if card else None,
        merchant=merchant,
        category=category,
        amount_cents=cents,
        approved=approved,
        reason=reason,
    )
    db.session.add(txn)

    if approved:
        acct.balance_cents -= cents

    db.session.commit()
    flash(f"Purchase {'APPROVED' if approved else 'DECLINED'}: {reason}")
    return redirect(url_for("dashboard"))

@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("Logged out successfully.")
    return redirect(url_for("home"))

@app.route("/login", methods=["POST"])
def login():
    name = request.form.get("name", "").strip()
    if not name:
        flash("Please enter your name.")
        return redirect(url_for("home"))
    
    # Find existing user by name
    user = User.query.filter_by(name=name).first()
    if not user:
        flash(f"No account found for '{name}'. Please create a new account.")
        return redirect(url_for("home"))
    
    # Get the user's account
    acct = Account.query.filter_by(user_id=user.id).first()
    if not acct:
        flash("Account error. Please create a new account.")
        return redirect(url_for("home"))
    
    session["account_id"] = acct.id
    flash(f"Welcome back, {name}!")
    return redirect(url_for("dashboard"))

if __name__ == "__main__":
    if not os.path.exists("hsa.db"):
        with app.app_context():
            db.create_all()
    app.run(debug=True)
