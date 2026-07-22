import io
import json
import math
import os
import random
import smtplib
import time
import urllib.parse
from datetime import date, datetime, timedelta
from email.mime.text import MIMEText
from functools import wraps

from flask import Flask, flash, redirect, render_template, request, send_file, session, url_for
from flask_sqlalchemy import SQLAlchemy
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas
from reportlab.platypus import Table, TableStyle
from werkzeug.security import check_password_hash, generate_password_hash
from sqlalchemy import text

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "iron-flow-secret-key-change-in-production")
app.config["SESSION_COOKIE_SECURE"] = os.environ.get("FLASK_ENV") == "production"
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.jinja_env.filters["normalize_phone"] = lambda p: normalize_phone(p) if p else ""

app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
    "DATABASE_URL",
    "postgresql://postgres.hhlortxhmfutdgcyyltm:Iron%26Flow%25123@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres"
)
if app.config["SQLALCHEMY_DATABASE_URI"].startswith("postgres://"):
    app.config["SQLALCHEMY_DATABASE_URI"] = app.config["SQLALCHEMY_DATABASE_URI"].replace("postgres://", "postgresql://", 1)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

FIXED_EMAIL = "madhuryaraghavan@gmail.com"
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD") or "rokn tifq dasy kqjq"


class Setting(db.Model):
    __tablename__ = "settings"
    key = db.Column(db.String(50), primary_key=True)
    value = db.Column(db.Text)


class Member(db.Model):
    __tablename__ = "members"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150))
    phone = db.Column(db.String(20))
    category = db.Column(db.String(50), nullable=False)
    plan_name = db.Column(db.String(100), nullable=False)
    joining_date = db.Column(db.Date)
    expiry_date = db.Column(db.Date)
    total_sessions = db.Column(db.Integer, default=0)
    sessions_used = db.Column(db.Integer, default=0)
    price = db.Column(db.Float, default=0)
    amount_paid = db.Column(db.Float, default=0)
    balance_amount = db.Column(db.Float, default=0)
    balance_due_date = db.Column(db.Date)
    status = db.Column(db.String(20), default="active")
    bill_number = db.Column(db.String(50))
    trainer = db.Column(db.String(100))
    notes = db.Column(db.Text)
    payment_mode = db.Column(db.String(30))
    paid_date = db.Column(db.Date)
    online_amount = db.Column(db.Float, default=0)
    cash_amount = db.Column(db.Float, default=0)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now())


class MembershipHistory(db.Model):
    __tablename__ = "membership_history"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    member_id = db.Column(db.Integer, db.ForeignKey("members.id", ondelete="CASCADE"))
    category = db.Column(db.String(50))
    plan_name = db.Column(db.String(100))
    start_date = db.Column(db.Date)
    expiry_date = db.Column(db.Date)
    total_sessions = db.Column(db.Integer)
    sessions_used = db.Column(db.Integer, default=0)
    price = db.Column(db.Float)
    amount_paid = db.Column(db.Float)
    balance_amount = db.Column(db.Float)
    balance_due_date = db.Column(db.Date)
    payment_mode = db.Column(db.String(30))
    paid_date = db.Column(db.Date)
    online_amount = db.Column(db.Float)
    cash_amount = db.Column(db.Float)
    renewed_at = db.Column(db.DateTime, default=lambda: datetime.now())


class Attendance(db.Model):
    __tablename__ = "attendance"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    member_id = db.Column(db.Integer, db.ForeignKey("members.id", ondelete="CASCADE"))
    date = db.Column(db.Date, nullable=False)
    check_in_time = db.Column(db.String(20), nullable=False)


class Enquiries(db.Model):
    __tablename__ = "enquiries"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(150), nullable=False)
    phone = db.Column(db.String(20))
    plan = db.Column(db.String(100))
    note = db.Column(db.Text)
    follow_up_date = db.Column(db.Date)
    status = db.Column(db.String(20), default="pending")
    created_at = db.Column(db.DateTime, default=lambda: datetime.now())


class Payment(db.Model):
    __tablename__ = "payments"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    member_id = db.Column(db.Integer, db.ForeignKey("members.id", ondelete="CASCADE"))
    amount = db.Column(db.Float, nullable=False)
    payment_date = db.Column(db.Date, nullable=False)
    payment_mode = db.Column(db.String(30), default="Cash")
    category = db.Column(db.String(50))
    plan_name = db.Column(db.String(100))
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now())


def send_otp_email(otp):
    if not EMAIL_PASSWORD:
        return False
    msg = MIMEText(f"Your Iron&Flow OTP is: {otp}\n\nThis code expires in 5 minutes.")
    msg["Subject"] = "Iron&Flow - OTP for Lock Screen"
    msg["From"] = FIXED_EMAIL
    msg["To"] = FIXED_EMAIL
    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as s:
            s.starttls()
            s.login(FIXED_EMAIL, EMAIL_PASSWORD)
            s.send_message(msg)
        return True
    except Exception:
        return False


def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("authenticated"):
            return redirect(url_for("index"))
        return f(*args, **kwargs)
    return decorated


CATEGORIES = ["transformation", "pilates", "club", "monthly"]

PLANS = {
    "transformation": {
        "label": "90 Days Transformation",
        "total_sessions": 90,
        "validity_days": 120,
    },
    "pilates": [
        {"label": "1 Month - 3 days/week", "sessions_per_week": 3, "total_sessions": 12, "validity_days": 40},
        {"label": "1 Month - 5 days/week", "sessions_per_week": 5, "total_sessions": 20, "validity_days": 50},
        {"label": "3 Month - 3 days/week", "sessions_per_week": 3, "total_sessions": 36, "validity_days": 120},
        {"label": "3 Month - 5 days/week", "sessions_per_week": 5, "total_sessions": 60, "validity_days": 120},
        {"label": "6 Month - 3 days/week", "sessions_per_week": 3, "total_sessions": 72, "validity_days": 220},
        {"label": "6 Month - 5 days/week", "sessions_per_week": 5, "total_sessions": 120, "validity_days": 240},
    ],
    "club": {
        "label": "Club Package",
        "total_sessions": 20,
        "validity_days": 45,
    },
    "monthly": {
        "label": "1 Month Plan",
        "total_sessions": 20,
        "validity_days": 30,
    },
}


def dd(val):
    if val is None:
        return None
    if isinstance(val, date):
        return val
    if isinstance(val, str):
        try:
            return date.fromisoformat(val)
        except (ValueError, TypeError):
            return None
    return val


def update_expiry_status():
    today = date.today()
    Member.query.filter(
        (Member.sessions_used >= Member.total_sessions) | (Member.expiry_date < today)
    ).update({"status": "expired"})
    Member.query.filter(
        ~((Member.sessions_used >= Member.total_sessions) | (Member.expiry_date < today))
    ).update({"status": "active"})
    db.session.commit()


def get_plan_info(category, plan_label=None):
    if category in ("transformation", "club", "monthly"):
        return PLANS[category]
    elif category == "pilates" and plan_label:
        for p in PLANS["pilates"]:
            if p["label"] == plan_label:
                return p
    return None


def validate_category(category):
    return category in CATEGORIES


def get_setting(key):
    row = Setting.query.get(key)
    return row.value if row else None


def set_setting(key, value):
    row = Setting.query.get(key)
    if row:
        row.value = value
    else:
        db.session.add(Setting(key=key, value=value))
    db.session.commit()


def normalize_phone(phone):
    if not phone:
        return phone
    phone = phone.strip()
    if phone.startswith("+"):
        phone = phone[1:]
    if phone.startswith("91") and len(phone) == 12:
        return phone
    if len(phone) == 10 and phone.isdigit():
        return "91" + phone
    return phone


def clean_date(val):
    if not val or val.strip() == "":
        return None
    return val.strip()


def whatsapp_url(phone, message):
    phone = normalize_phone(phone)
    if not phone:
        return "#"
    return f"https://wa.me/{phone}?text={urllib.parse.quote(message)}"


def get_welcome_message(category, plan_name=None):
    if category == "transformation":
        return "Welcome to Iron&Flow! You have enrolled in our 90 Days Transformation program. Your journey to a new you starts now!"
    elif category == "pilates":
        pn = plan_name or "program"
        return f"Welcome to Iron&Flow! You have enrolled in our Pilates {pn}. Get ready to strengthen and tone!"
    elif category == "club":
        return "Welcome to Iron&Flow! You have enrolled in our Club Package. Enjoy premium access to all facilities!"
    return "Welcome to Iron&Flow!"


def get_reminder_message(name, remaining, plan_name):
    return f"Hi {name}, you have {remaining} sessions remaining in your {plan_name} at Iron&Flow."


def get_balance_message(name, balance_amount, plan_name):
    return f"Hi {name}, you have a pending balance of Rs.{balance_amount:.0f} for your {plan_name} at Iron&Flow. Please clear it at your earliest."


def get_category_stats(category):
    total = Member.query.filter_by(category=category).count()
    active = Member.query.filter_by(category=category, status="active").count()
    expired = Member.query.filter_by(category=category, status="expired").count()
    week_later = date.today() + timedelta(days=7)
    expiring = Member.query.filter(
        Member.category == category,
        Member.status == "active",
        ((Member.total_sessions - Member.sessions_used) <= db.func.ceil(Member.total_sessions * 0.2)) |
        ((Member.expiry_date.isnot(None)) & (Member.expiry_date <= week_later))
    ).count()
    return {"total": total, "active": active, "expired": expired, "expiring": expiring}


def get_balances(category):
    return Member.query.filter_by(category=category).filter(Member.balance_amount > 0).order_by(Member.balance_due_date).all()


@app.before_request
def before_request():
    if request.endpoint and request.endpoint != "static":
        try:
            update_expiry_status()
        except Exception:
            db.session.rollback()


@app.template_filter("datefmt")
def datefmt_filter(val, fmt="%d-%m-%Y"):
    if val is None:
        return "-"
    if isinstance(val, str):
        try:
            val = date.fromisoformat(val)
        except (ValueError, TypeError):
            return val
    if isinstance(val, (date, datetime)):
        return val.strftime(fmt)
    return str(val)


@app.template_filter("dateinput")
def dateinput_filter(val):
    if val is None:
        return ""
    if isinstance(val, str):
        try:
            val = date.fromisoformat(val)
        except (ValueError, TypeError):
            return val
    if isinstance(val, (date, datetime)):
        return val.strftime("%Y-%m-%d")
    return str(val)


@app.context_processor
def inject_globals():
    return {
        "categories": CATEGORIES,
        "category_labels": {
            "transformation": "90 Days Transformation",
            "pilates": "Pilates",
            "club": "Club Package",
            "monthly": "1 Month Plan",
        },
        "now": datetime.now(),
        "whatsapp_url": whatsapp_url,
    }


@app.route("/")
def index():
    stats = {}
    for cat in CATEGORIES:
        stats[cat] = get_category_stats(cat)
    today = date.today()
    today_count = Enquiries.query.filter(
        Enquiries.follow_up_date == today,
        db.or_(Enquiries.status.is_(None), Enquiries.status != "done")
    ).count()
    return render_template("index.html", stats=stats, today_enquiries=today_count)


@app.route("/members")
def all_members():
    search = request.args.get("search", "").strip()
    if search:
        pattern = f"%{search}%"
        members = Member.query.filter(
            db.or_(
                Member.name.ilike(pattern),
                Member.phone.ilike(pattern),
                Member.bill_number.ilike(pattern)
            )
        ).order_by(Member.category, Member.id.desc()).all()
    else:
        members = Member.query.order_by(Member.category, Member.id.desc()).all()
    return render_template("all_members.html", members=members, search=search)


@app.route("/dashboard/<category>")
def category_dashboard(category):
    if not validate_category(category):
        flash("Invalid category", "error")
        return redirect(url_for("index"))
    stats = get_category_stats(category)
    return render_template("dashboard.html", category=category, stats=stats)


@app.route("/members/<category>")
def members_list(category):
    if not validate_category(category):
        flash("Invalid category", "error")
        return redirect(url_for("index"))
    search = request.args.get("search", "").strip()
    if search:
        pattern = f"%{search}%"
        members = Member.query.filter(
            Member.category == category,
            db.or_(
                Member.name.ilike(pattern),
                Member.phone.ilike(pattern),
                Member.bill_number.ilike(pattern)
            )
        ).order_by(Member.id.desc()).all()
    else:
        members = Member.query.filter_by(category=category).order_by(Member.id.desc()).all()
    return render_template("members.html", category=category, members=members, search=search)


@app.route("/members/add/<category>", methods=["GET", "POST"])
def add_member(category):
    if not validate_category(category):
        flash("Invalid category", "error")
        return redirect(url_for("index"))
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if not name:
            flash("Name is required", "error")
            return redirect(request.url)
        email = request.form.get("email", "").strip()
        phone = normalize_phone(request.form.get("phone", "").strip())
        plan_name = request.form.get("plan_name", "").strip()
        if category == "transformation":
            plan_name = "90 Days Transformation"
        elif category == "club":
            plan_name = "Club Package"
        elif category == "monthly":
            plan_name = "1 Month Plan"
        if not plan_name:
            flash("Plan is required", "error")
            return redirect(request.url)
        plan_info = get_plan_info(category, plan_name)
        if not plan_info:
            flash("Invalid plan selected", "error")
            return redirect(request.url)
        jd = clean_date(request.form.get("joining_date", ""))
        joining_date = dd(jd)
        expiry_date = None
        if joining_date:
            expiry_date = joining_date + timedelta(days=plan_info["validity_days"] - 1)
        total_sessions = plan_info["total_sessions"]
        price = _float(request.form.get("price"))
        payment_mode = request.form.get("payment_mode", "Cash")
        amount_paid = _float(request.form.get("amount_paid"))
        paid_date = dd(clean_date(request.form.get("paid_date", "")))
        online_amount = _float(request.form.get("online_amount"))
        cash_amount = _float(request.form.get("cash_amount"))
        balance_amount = _float(request.form.get("balance_amount"))
        balance_due_date = dd(clean_date(request.form.get("balance_due_date", "")))
        bill_number = request.form.get("bill_number", "").strip()
        trainer = request.form.get("trainer", "").strip()
        notes = request.form.get("notes", "").strip()
        member = Member(
            name=name, email=email, phone=phone, category=category, plan_name=plan_name,
            joining_date=joining_date, expiry_date=expiry_date, total_sessions=total_sessions,
            sessions_used=0, price=price, amount_paid=amount_paid, balance_amount=balance_amount,
            balance_due_date=balance_due_date, bill_number=bill_number, trainer=trainer, notes=notes,
            payment_mode=payment_mode, paid_date=paid_date, online_amount=online_amount,
            cash_amount=cash_amount, status="active"
        )
        db.session.add(member)
        db.session.flush()
        member_id = member.id
        history = MembershipHistory(
            member_id=member_id, category=category, plan_name=plan_name,
            start_date=joining_date, expiry_date=expiry_date, total_sessions=total_sessions,
            sessions_used=0, price=price, amount_paid=amount_paid, balance_amount=balance_amount,
            balance_due_date=balance_due_date, payment_mode=payment_mode, paid_date=paid_date,
            online_amount=online_amount, cash_amount=cash_amount
        )
        db.session.add(history)
        if amount_paid > 0:
            payment = Payment(
                member_id=member_id, amount=amount_paid,
                payment_date=paid_date or date.today(), payment_mode=payment_mode,
                category=category, plan_name=plan_name,
                notes=f"New membership payment for {plan_name}"
            )
            db.session.add(payment)
        db.session.commit()
        flash("Member added successfully!", "success")
        wa_url = whatsapp_url(phone, get_welcome_message(category, plan_name))
        return redirect(url_for("members_list", category=category, wa=wa_url))
    pilates_plans = PLANS["pilates"]
    today_str = date.today().isoformat()
    return render_template("add_member.html", category=category,
                           pilates_plans=pilates_plans, today=today_str, plans=PLANS)


def _float(val):
    try:
        return float(val) if val else 0
    except (ValueError, TypeError):
        return 0


@app.route("/member/<int:member_id>")
def member_detail(member_id):
    member = db.session.get(Member, member_id)
    if not member:
        flash("Member not found", "error")
        return redirect(url_for("index"))
    history = MembershipHistory.query.filter_by(member_id=member_id).order_by(MembershipHistory.renewed_at.desc()).all()
    payments = Payment.query.filter_by(member_id=member_id).order_by(Payment.payment_date.desc()).all()
    remaining = member.total_sessions - member.sessions_used
    welcome_msg = get_welcome_message(member.category, member.plan_name)
    reminder_msg = get_reminder_message(member.name, remaining, member.plan_name)
    balance_msg = get_balance_message(member.name, member.balance_amount, member.plan_name)
    return render_template("member_detail.html", member=member, history=history,
                           payments=payments, remaining=remaining,
                           welcome_msg=welcome_msg, reminder_msg=reminder_msg,
                           balance_msg=balance_msg, category=member.category)


@app.route("/members/edit/<int:member_id>", methods=["GET", "POST"])
@require_auth
def edit_member(member_id):
    member = db.session.get(Member, member_id)
    if not member:
        flash("Member not found", "error")
        return redirect(url_for("index"))
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if not name:
            flash("Name is required", "error")
            return redirect(request.url)
        member.name = name
        member.email = request.form.get("email", "").strip()
        member.phone = normalize_phone(request.form.get("phone", "").strip())
        member.joining_date = dd(clean_date(request.form.get("joining_date", "")))
        member.expiry_date = dd(clean_date(request.form.get("expiry_date", "")))
        try:
            member.total_sessions = int(request.form.get("total_sessions", 0)) if request.form.get("total_sessions") else 0
        except ValueError:
            member.total_sessions = 0
        try:
            member.sessions_used = int(request.form.get("sessions_used", 0)) if request.form.get("sessions_used") else 0
        except ValueError:
            member.sessions_used = 0
        member.price = _float(request.form.get("price"))
        member.amount_paid = _float(request.form.get("amount_paid"))
        member.balance_amount = _float(request.form.get("balance_amount"))
        member.balance_due_date = dd(clean_date(request.form.get("balance_due_date", "")))
        member.bill_number = request.form.get("bill_number", "").strip()
        member.trainer = request.form.get("trainer", "").strip()
        member.notes = request.form.get("notes", "").strip()
        member.payment_mode = request.form.get("payment_mode", "Cash")
        member.paid_date = dd(clean_date(request.form.get("paid_date", "")))
        member.online_amount = _float(request.form.get("online_amount"))
        member.cash_amount = _float(request.form.get("cash_amount"))
        db.session.commit()
        flash("Member updated successfully!", "success")
        return redirect(url_for("member_detail", member_id=member_id))
    return render_template("edit_member.html", member=member, category=member.category)


@app.route("/mark-attendance/<int:member_id>", methods=["GET", "POST"])
def mark_attendance(member_id):
    member = db.session.get(Member, member_id)
    if not member:
        flash("Member not found", "error")
        return redirect(url_for("index"))
    if member.status == "expired":
        flash("Cannot mark attendance for expired member", "error")
        return redirect(url_for("member_detail", member_id=member_id))
    if member.sessions_used >= member.total_sessions:
        flash("All sessions used. Please renew membership.", "error")
        return redirect(url_for("member_detail", member_id=member_id))
    if request.method == "POST":
        dates_str = request.form.get("dates", "")
        dates_list = [d.strip() for d in dates_str.split(",") if d.strip()]
        if not dates_list:
            flash("Please select at least one date", "error")
            return redirect(request.url)
        remaining = member.total_sessions - member.sessions_used
        if len(dates_list) > remaining:
            flash(f"Only {remaining} session(s) remaining. You selected {len(dates_list)} dates.", "error")
            return redirect(request.url)
        now_dt = datetime.now()
        count = 0
        for adate in dates_list:
            att = Attendance(member_id=member_id, date=dd(adate), check_in_time=now_dt.time().isoformat())
            db.session.add(att)
            count += 1
        member.sessions_used = member.sessions_used + count
        latest_history = MembershipHistory.query.filter_by(member_id=member_id).order_by(MembershipHistory.renewed_at.desc()).first()
        if latest_history:
            latest_history.sessions_used = (latest_history.sessions_used or 0) + count
        db.session.commit()
        update_expiry_status()
        flash(f"Attendance marked for {count} day(s)!", "success")
        return redirect(url_for("member_detail", member_id=member_id))
    return render_template("attendance.html", member=member, category=member.category,
                           today=date.today().isoformat())


@app.route("/members/renew/<int:member_id>", methods=["GET", "POST"])
def renew_member(member_id):
    member = db.session.get(Member, member_id)
    if not member:
        flash("Member not found", "error")
        return redirect(url_for("index"))
    category = member.category
    if request.method == "POST":
        plan_name = request.form.get("plan_name", "").strip()
        if category == "transformation":
            plan_name = "90 Days Transformation"
        elif category == "club":
            plan_name = "Club Package"
        elif category == "monthly":
            plan_name = "1 Month Plan"
        if not plan_name:
            flash("Plan is required", "error")
            return redirect(request.url)
        plan_info = get_plan_info(category, plan_name)
        if not plan_info:
            flash("Invalid plan", "error")
            return redirect(request.url)
        jd = clean_date(request.form.get("joining_date", ""))
        joining_date = dd(jd)
        expiry_date = None
        if joining_date:
            expiry_date = joining_date + timedelta(days=plan_info["validity_days"] - 1)
        total_sessions = plan_info["total_sessions"]
        price = _float(request.form.get("price"))
        payment_mode = request.form.get("payment_mode", "Cash")
        amount_paid = _float(request.form.get("amount_paid"))
        paid_date = dd(clean_date(request.form.get("paid_date", "")))
        online_amount = _float(request.form.get("online_amount"))
        cash_amount = _float(request.form.get("cash_amount"))
        balance_amount = _float(request.form.get("balance_amount"))
        balance_due_date = dd(clean_date(request.form.get("balance_due_date", "")))
        member.plan_name = plan_name
        member.joining_date = joining_date
        member.expiry_date = expiry_date
        member.total_sessions = total_sessions
        member.sessions_used = 0
        member.price = price
        member.amount_paid = amount_paid
        member.balance_amount = balance_amount
        member.balance_due_date = balance_due_date
        member.status = "active"
        member.payment_mode = payment_mode
        member.paid_date = paid_date
        member.online_amount = online_amount
        member.cash_amount = cash_amount
        history = MembershipHistory(
            member_id=member_id, category=category, plan_name=plan_name,
            start_date=joining_date, expiry_date=expiry_date, total_sessions=total_sessions,
            sessions_used=0, price=price, amount_paid=amount_paid, balance_amount=balance_amount,
            balance_due_date=balance_due_date, payment_mode=payment_mode, paid_date=paid_date,
            online_amount=online_amount, cash_amount=cash_amount
        )
        db.session.add(history)
        if amount_paid > 0:
            payment = Payment(
                member_id=member_id, amount=amount_paid,
                payment_date=paid_date or date.today(), payment_mode=payment_mode,
                category=category, plan_name=plan_name,
                notes=f"Renewal payment for {plan_name}"
            )
            db.session.add(payment)
        db.session.commit()
        flash("Membership renewed successfully!", "success")
        return redirect(url_for("member_detail", member_id=member_id))
    pilates_plans = PLANS["pilates"]
    today_str = date.today().isoformat()
    return render_template("renew.html", member=member, category=category,
                           pilates_plans=pilates_plans, today=today_str, plans=PLANS)


@app.route("/members/pay-balance/<int:member_id>", methods=["GET", "POST"])
def pay_balance(member_id):
    member = db.session.get(Member, member_id)
    if not member:
        flash("Member not found", "error")
        return redirect(url_for("index"))
    if request.method == "POST":
        amount = _float(request.form.get("amount"))
        if amount <= 0:
            flash("Invalid amount", "error")
            return redirect(request.url)
        payment_date = dd(clean_date(request.form.get("payment_date", "")))
        payment_mode = request.form.get("payment_mode", "Cash")
        new_balance = max(0, member.balance_amount - amount)
        member.balance_amount = new_balance
        member.amount_paid = (member.amount_paid or 0) + amount
        latest_history = MembershipHistory.query.filter_by(member_id=member_id).order_by(MembershipHistory.renewed_at.desc()).first()
        if latest_history:
            latest_history.balance_amount = new_balance
            latest_history.amount_paid = (latest_history.amount_paid or 0) + amount
        payment = Payment(
            member_id=member_id, amount=amount,
            payment_date=payment_date or date.today(), payment_mode=payment_mode,
            category=member.category, plan_name=member.plan_name,
            notes="Balance payment"
        )
        db.session.add(payment)
        db.session.commit()
        flash("Balance payment recorded!", "success")
        return redirect(url_for("member_detail", member_id=member_id))
    return render_template("pay_balance.html", member=member, category=member.category)


@app.route("/expiring/<category>")
def expiring_members(category):
    if not validate_category(category):
        flash("Invalid category", "error")
        return redirect(url_for("index"))
    week_later = date.today() + timedelta(days=7)
    members = Member.query.filter(
        Member.category == category,
        Member.status == "active",
        db.or_(
            (Member.total_sessions - Member.sessions_used) <= db.func.ceil(Member.total_sessions * 0.2),
            db.and_(Member.expiry_date.isnot(None), Member.expiry_date <= week_later)
        )
    ).order_by(Member.expiry_date).all()
    return render_template("expiring.html", category=category, members=members)


@app.route("/expired/<category>")
def expired_members(category):
    if not validate_category(category):
        flash("Invalid category", "error")
        return redirect(url_for("index"))
    members = Member.query.filter_by(category=category, status="expired").order_by(Member.expiry_date.desc()).all()
    return render_template("expired.html", category=category, members=members)


@app.route("/balances/<category>")
def pending_balances(category):
    if not validate_category(category):
        flash("Invalid category", "error")
        return redirect(url_for("index"))
    balances = get_balances(category)
    return render_template("balances.html", category=category, balances=balances)


@app.route("/admin/login")
def admin_login():
    return redirect(url_for("index"))


@app.route("/admin")
@require_auth
def admin_panel():
    year = request.args.get("year", str(date.today().year))
    try:
        year = int(year)
    except ValueError:
        year = date.today().year
    rows = db.session.execute(text("""
        SELECT to_char(payment_date, 'YYYY-MM') AS month,
               COUNT(DISTINCT member_id) AS new_members,
               SUM(amount) AS revenue
        FROM payments
        WHERE to_char(payment_date, 'YYYY') = :year
        GROUP BY month ORDER BY month
    """), {"year": str(year)}).mappings().all()
    total_revenue = db.session.execute(text("""
        SELECT COALESCE(SUM(amount), 0) AS total_revenue
        FROM payments WHERE to_char(payment_date, 'YYYY') = :year
    """), {"year": str(year)}).scalar()
    current_month_sales = db.session.execute(text("""
        SELECT COALESCE(SUM(amount), 0) AS total
        FROM payments
        WHERE to_char(payment_date, 'YYYY') = :year AND to_char(payment_date, 'MM') = :month
    """), {"year": str(year), "month": f"{datetime.now().month:02d}"}).scalar()
    total_members = Member.query.count()
    monthly_data = [dict(row) for row in rows]
    for row in monthly_data:
        row["pct"] = round((row["revenue"] / total_revenue * 100), 1) if total_revenue > 0 else 0
    return render_template("admin.html", year=year, monthly_data=monthly_data,
                           total_revenue=total_revenue,
                           current_month_sales=current_month_sales,
                           total_members=total_members)


@app.route("/admin/<category>")
@require_auth
def category_admin(category):
    if not validate_category(category):
        flash("Invalid category", "error")
        return redirect(url_for("index"))
    year = request.args.get("year", str(date.today().year))
    try:
        year = int(year)
    except ValueError:
        year = date.today().year
    rows = db.session.execute(text("""
        SELECT to_char(payment_date, 'YYYY-MM') AS month,
               COUNT(DISTINCT member_id) AS new_members,
               SUM(amount) AS revenue
        FROM payments
        WHERE to_char(payment_date, 'YYYY') = :year AND category = :category
        GROUP BY month ORDER BY month
    """), {"year": str(year), "category": category}).mappings().all()
    total_revenue = db.session.execute(text("""
        SELECT COALESCE(SUM(amount), 0) AS total_revenue
        FROM payments WHERE to_char(payment_date, 'YYYY') = :year AND category = :category
    """), {"year": str(year), "category": category}).scalar()
    current_month_sales = db.session.execute(text("""
        SELECT COALESCE(SUM(amount), 0) AS total
        FROM payments
        WHERE to_char(payment_date, 'YYYY') = :year AND to_char(payment_date, 'MM') = :month AND category = :category
    """), {"year": str(year), "month": f"{datetime.now().month:02d}", "category": category}).scalar()
    total_members = Member.query.filter_by(category=category).count()
    monthly_data = [dict(row) for row in rows]
    for row in monthly_data:
        row["pct"] = round((row["revenue"] / total_revenue * 100), 1) if total_revenue > 0 else 0
    return render_template("category_admin.html", category=category, year=year,
                           monthly_data=monthly_data, total_revenue=total_revenue,
                           current_month_sales=current_month_sales,
                           total_members=total_members)


@app.route("/admin/sales-detail")
@require_auth
def sales_detail():
    month = request.args.get("month", datetime.now().strftime("%Y-%m"))
    payments = db.session.execute(text("""
        SELECT p.*, m.name AS member_name, m.phone AS member_phone
        FROM payments p LEFT JOIN members m ON p.member_id = m.id
        WHERE to_char(p.payment_date, 'YYYY-MM') = :month
        ORDER BY p.payment_date DESC
    """), {"month": month}).mappings().all()
    return render_template("sales_detail.html", month=month, payments=payments, is_category=False)


@app.route("/admin/sales-detail/<category>")
@require_auth
def category_sales_detail(category):
    if not validate_category(category):
        flash("Invalid category", "error")
        return redirect(url_for("index"))
    month = request.args.get("month", datetime.now().strftime("%Y-%m"))
    payments = db.session.execute(text("""
        SELECT p.*, m.name AS member_name, m.phone AS member_phone
        FROM payments p LEFT JOIN members m ON p.member_id = m.id
        WHERE to_char(p.payment_date, 'YYYY-MM') = :month AND p.category = :category
        ORDER BY p.payment_date DESC
    """), {"month": month, "category": category}).mappings().all()
    return render_template("sales_detail.html", month=month, payments=payments,
                           category=category, is_category=True)


@app.route("/admin/download-report")
@require_auth
def download_annual_report():
    year = request.args.get("year", str(date.today().year))
    try:
        year = int(year)
    except ValueError:
        year = date.today().year
    data = db.session.execute(text("""
        SELECT to_char(payment_date, 'YYYY-MM') AS month,
               COUNT(DISTINCT member_id) AS new_members,
               SUM(amount) AS revenue
        FROM payments WHERE to_char(payment_date, 'YYYY') = :year
        GROUP BY month ORDER BY month
    """), {"year": str(year)}).mappings().all()
    total_revenue = db.session.execute(text("""
        SELECT COALESCE(SUM(amount), 0) AS total_revenue
        FROM payments WHERE to_char(payment_date, 'YYYY') = :year
    """), {"year": str(year)}).scalar()
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    width, height = A4
    c.setFont("Helvetica-Bold", 18)
    c.drawString(50, height - 50, f"Iron&Flow - Annual Report {year}")
    c.setFont("Helvetica", 12)
    c.drawString(50, height - 80, f"Grand Total Revenue: Rs.{total_revenue:,.2f}")
    table_data = [["Month", "New Members", "Revenue", "% of Year"]]
    for row in data:
        pct = round((row["revenue"] / total_revenue * 100), 1) if total_revenue > 0 else 0
        table_data.append([row["month"], str(row["new_members"]), f"Rs.{row['revenue']:,.2f}", f"{pct}%"])
    t = Table(table_data, colWidths=[120, 120, 180, 100])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a1a2e")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f5f5")]),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    t.wrapOn(c, width, height)
    t.drawOn(c, 50, height - 110 - len(table_data) * 22)
    c.save()
    buf.seek(0)
    return send_file(buf, mimetype="application/pdf",
                     as_attachment=True,
                     download_name=f"annual_report_{year}.pdf")


@app.route("/admin/download-report/<category>")
@require_auth
def category_download_report(category):
    if not validate_category(category):
        flash("Invalid category", "error")
        return redirect(url_for("index"))
    year = request.args.get("year", str(date.today().year))
    try:
        year = int(year)
    except ValueError:
        year = date.today().year
    data = db.session.execute(text("""
        SELECT to_char(payment_date, 'YYYY-MM') AS month,
               COUNT(DISTINCT member_id) AS new_members,
               SUM(amount) AS revenue
        FROM payments WHERE to_char(payment_date, 'YYYY') = :year AND category = :category
        GROUP BY month ORDER BY month
    """), {"year": str(year), "category": category}).mappings().all()
    total_revenue = db.session.execute(text("""
        SELECT COALESCE(SUM(amount), 0) AS total_revenue
        FROM payments WHERE to_char(payment_date, 'YYYY') = :year AND category = :category
    """), {"year": str(year), "category": category}).scalar()
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    width, height = A4
    cat_label = {"transformation": "90 Days Transformation", "pilates": "Pilates", "club": "Club Package", "monthly": "1 Month Plan"}
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, height - 50, f"Iron&Flow - {cat_label.get(category, category)} Report {year}")
    c.setFont("Helvetica", 12)
    c.drawString(50, height - 80, f"Total Revenue: Rs.{total_revenue:,.2f}")
    table_data = [["Month", "New Members", "Revenue", "% of Year"]]
    for row in data:
        pct = round((row["revenue"] / total_revenue * 100), 1) if total_revenue > 0 else 0
        table_data.append([row["month"], str(row["new_members"]), f"Rs.{row['revenue']:,.2f}", f"{pct}%"])
    t = Table(table_data, colWidths=[120, 120, 180, 100])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a1a2e")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f5f5")]),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    t.wrapOn(c, width, height)
    t.drawOn(c, 50, height - 110 - len(table_data) * 22)
    c.save()
    buf.seek(0)
    return send_file(buf, mimetype="application/pdf",
                     as_attachment=True,
                     download_name=f"{category}_report_{year}.pdf")


@app.route("/admin/download-members")
@require_auth
def download_members_pdf():
    members = Member.query.order_by(Member.category, Member.id).all()
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=landscape(A4))
    width, height = landscape(A4)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(30, height - 30, "Iron&Flow - All Members Report")
    table_data = [["ID", "Name", "Phone", "Plan", "Sessions", "Joining", "Expiry", "Status", "Balance"]]
    for m in members:
        sessions_str = f"{m.sessions_used}/{m.total_sessions}" if m.total_sessions else "-"
        joining = m.joining_date
        expiry = m.expiry_date
        table_data.append([
            str(m.id), m.name[:25], m.phone or "-",
            m.plan_name[:25], sessions_str,
            joining.strftime("%d-%m-%Y") if joining else "-",
            expiry.strftime("%d-%m-%Y") if expiry else "-",
            m.status, f"Rs.{m.balance_amount:.0f}" if m.balance_amount > 0 else "-"
        ])
    t = Table(table_data, colWidths=[35, 120, 90, 120, 65, 75, 75, 60, 65])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a1a2e")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ALIGN", (4, 0), (-1, -1), "CENTER"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f5f5")]),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    t.wrapOn(c, width, height)
    t.drawOn(c, 30, height - 55 - len(table_data) * 17)
    c.save()
    buf.seek(0)
    return send_file(buf, mimetype="application/pdf",
                     as_attachment=True,
                     download_name="all_members_report.pdf")


@app.route("/admin/download-members/<category>")
@require_auth
def category_download_members(category):
    if not validate_category(category):
        flash("Invalid category", "error")
        return redirect(url_for("index"))
    members = Member.query.filter_by(category=category).order_by(Member.id).all()
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=landscape(A4))
    width, height = landscape(A4)
    cat_label = {"transformation": "90 Days Transformation", "pilates": "Pilates", "club": "Club Package", "monthly": "1 Month Plan"}
    c.setFont("Helvetica-Bold", 16)
    c.drawString(30, height - 30, f"Iron&Flow - {cat_label.get(category, category)} Members Report")
    table_data = [["ID", "Name", "Phone", "Plan", "Sessions", "Joining", "Expiry", "Status", "Balance"]]
    for m in members:
        sessions_str = f"{m.sessions_used}/{m.total_sessions}" if m.total_sessions else "-"
        joining = m.joining_date
        expiry = m.expiry_date
        table_data.append([
            str(m.id), m.name[:25], m.phone or "-",
            m.plan_name[:25], sessions_str,
            joining.strftime("%d-%m-%Y") if joining else "-",
            expiry.strftime("%d-%m-%Y") if expiry else "-",
            m.status, f"Rs.{m.balance_amount:.0f}" if m.balance_amount > 0 else "-"
        ])
    t = Table(table_data, colWidths=[35, 120, 90, 120, 65, 75, 75, 60, 65])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a1a2e")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ALIGN", (4, 0), (-1, -1), "CENTER"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f5f5")]),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    t.wrapOn(c, width, height)
    t.drawOn(c, 30, height - 55 - len(table_data) * 17)
    c.save()
    buf.seek(0)
    return send_file(buf, mimetype="application/pdf",
                     as_attachment=True,
                     download_name=f"{category}_members_report.pdf")


@app.route("/api/check-setup")
def check_setup():
    return {"setup": bool(get_setting("app_password_hash"))}


@app.route("/api/send-otp", methods=["POST"])
def send_otp():
    otp = str(random.randint(100000, 999999))
    session["otp_code"] = otp
    session["otp_expiry"] = time.time() + 300
    ok = send_otp_email(otp)
    return {"success": ok, "error": None if ok else "Email not configured. Set EMAIL_PASSWORD env var."}


@app.route("/api/verify-otp", methods=["POST"])
def verify_otp():
    data = request.get_json()
    code = data.get("otp", "")
    stored = session.get("otp_code")
    expiry = session.get("otp_expiry", 0)
    if time.time() > expiry:
        session.pop("otp_code", None)
        session.pop("otp_expiry", None)
        return {"success": False, "error": "OTP expired"}, 400
    if code != stored:
        return {"success": False, "error": "Invalid OTP"}, 400
    session["otp_verified"] = True
    session.pop("otp_code", None)
    session.pop("otp_expiry", None)
    return {"success": True}


@app.route("/api/set-password", methods=["POST"])
def set_password():
    if not session.get("otp_verified"):
        return {"success": False, "error": "OTP not verified"}, 401
    data = request.get_json()
    password = data.get("password", "")
    if len(password) < 4:
        return {"success": False, "error": "Password too short"}, 400
    set_setting("app_password_hash", generate_password_hash(password))
    session.pop("otp_verified", None)
    session["authenticated"] = True
    return {"success": True}


@app.route("/api/verify-login", methods=["POST"])
def verify_login():
    data = request.get_json()
    password = data.get("password", "")
    stored_hash = get_setting("app_password_hash")
    if stored_hash and check_password_hash(stored_hash, password):
        session["authenticated"] = True
        return {"success": True}
    return {"success": False, "error": "Wrong password"}, 401


@app.route("/api/reset-password", methods=["POST"])
def reset_password():
    if not session.get("otp_verified"):
        return {"success": False, "error": "OTP not verified"}, 401
    data = request.get_json()
    password = data.get("password", "")
    if len(password) < 4:
        return {"success": False, "error": "Password too short"}, 400
    set_setting("app_password_hash", generate_password_hash(password))
    session.pop("otp_verified", None)
    return {"success": True}


@app.route("/api/logout", methods=["POST"])
def logout():
    session.pop("authenticated", None)
    return {"success": True}


@app.route("/admin/setup-initial", methods=["GET", "POST"])
def setup_initial():
    existing = get_setting("master_admin_password_hash")
    if existing:
        return redirect(url_for("index"))
    if request.method == "POST":
        password = request.form.get("password", "")
        if password:
            set_setting("master_admin_password_hash", generate_password_hash(password))
            flash("Master admin password set!", "success")
            return redirect(url_for("index"))
        flash("Password is required", "error")
    return render_template("setup.html")


@app.route("/member/delete/<int:member_id>", methods=["POST"])
def delete_member(member_id):
    member = db.session.get(Member, member_id)
    if member:
        db.session.delete(member)
        db.session.commit()
    flash("Member deleted", "success")
    return redirect(url_for("index"))


@app.route("/enquiries")
@require_auth
def enquiries_list():
    today = date.today()
    rows = Enquiries.query.order_by(Enquiries.created_at.desc()).all()
    for r in rows:
        r.is_today = (r.follow_up_date == today and (r.status is None or r.status != "done"))
    today_list = Enquiries.query.filter(
        Enquiries.follow_up_date == today,
        db.or_(Enquiries.status.is_(None), Enquiries.status != "done")
    ).order_by(Enquiries.created_at.desc()).all()
    return render_template("enquiries.html", enquiries=rows, today_list=today_list, today=today)


@app.route("/today-enquiries")
@require_auth
def today_enquiries():
    today = date.today()
    rows = Enquiries.query.filter(
        Enquiries.follow_up_date == today,
        db.or_(Enquiries.status.is_(None), Enquiries.status != "done")
    ).order_by(Enquiries.created_at.desc()).all()
    return render_template("today_enquiries.html", today_list=rows)


@app.route("/enquiries/add", methods=["POST"])
@require_auth
def enquiry_add():
    name = request.form.get("name", "").strip()
    phone = request.form.get("phone", "").strip()
    plan = request.form.get("plan", "").strip()
    note = request.form.get("note", "").strip()
    follow_up_date = dd(request.form.get("follow_up_date", "").strip())
    if not name:
        flash("Name is required", "error")
        return redirect(url_for("enquiries_list"))
    e = Enquiries(name=name, phone=phone, plan=plan, note=note, follow_up_date=follow_up_date)
    db.session.add(e)
    db.session.commit()
    flash("Enquiry added", "success")
    return redirect(url_for("enquiries_list"))


@app.route("/enquiries/update-date/<int:enquiry_id>", methods=["POST"])
@require_auth
def enquiry_update_date(enquiry_id):
    new_date = dd(request.form.get("follow_up_date", "").strip())
    e = db.session.get(Enquiries, enquiry_id)
    if e:
        e.follow_up_date = new_date
        e.status = "pending"
        db.session.commit()
    flash("Follow-up date updated", "success")
    ref = request.referrer or ""
    return redirect(url_for("today_enquiries") if "today" in ref else url_for("enquiries_list"))


@app.route("/enquiries/mark-done/<int:enquiry_id>", methods=["POST"])
@require_auth
def enquiry_mark_done(enquiry_id):
    e = db.session.get(Enquiries, enquiry_id)
    if e:
        e.status = "done"
        db.session.commit()
    flash("Enquiry marked done", "success")
    ref = request.referrer or ""
    return redirect(url_for("today_enquiries") if "today" in ref else url_for("enquiries_list"))


@app.route("/enquiries/update-note/<int:enquiry_id>", methods=["POST"])
@require_auth
def enquiry_update_note(enquiry_id):
    note = request.form.get("note", "").strip()
    e = db.session.get(Enquiries, enquiry_id)
    if e:
        e.note = note
        db.session.commit()
    flash("Note updated", "success")
    ref = request.referrer or ""
    return redirect(url_for("today_enquiries") if "today" in ref else url_for("enquiries_list"))


@app.route("/enquiries/delete/<int:enquiry_id>", methods=["POST"])
@require_auth
def enquiry_delete(enquiry_id):
    e = db.session.get(Enquiries, enquiry_id)
    if e:
        db.session.delete(e)
        db.session.commit()
    flash("Enquiry deleted", "success")
    return redirect(url_for("enquiries_list"))


with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(debug=True)