import os, json, re, secrets, random, smtplib
from datetime import date, datetime, timedelta
from functools import wraps
from contextlib import contextmanager
from email.message import EmailMessage

import psycopg2
import psycopg2.extras
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash

# ── App setup ────────────────────────────────────────────────────────────
app = Flask(__name__)

_secret = os.environ.get("SECRET_KEY", "")
if not _secret:
    import warnings
    warnings.warn(
        "SECRET_KEY not set — using a random key. "
        "Sessions will not persist across restarts. "
        "Set SECRET_KEY in your environment for production.",
        stacklevel=1,
    )
    _secret = secrets.token_hex(32)
app.secret_key = _secret

# DATABASE_URL is provided automatically by Railway when you add a Postgres plugin.
# Format: postgresql://user:password@host:port/dbname
DATABASE_URL = os.environ.get("DATABASE_URL", "")
if DATABASE_URL.startswith("postgres://"):
    # Railway (and Heroku) sometimes use the older postgres:// scheme;
    # psycopg2 requires postgresql://
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

USERNAME_RE = re.compile(r'^[a-zA-Z0-9_]{3,24}$')
SUPERADMIN_USERNAMES = ["alishershukhratov456", "alishershukhratov67"]
TWOFA_CODE_TTL_MINUTES = 10


# ── Database helpers ────────────────────────────────────────────────────────
@contextmanager
def db():
    """Yields a psycopg2 connection that commits on exit and closes on error."""
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def fetchone(conn, sql, params=()):
    cur = conn.cursor()
    cur.execute(sql, params)
    return cur.fetchone()


def fetchall(conn, sql, params=()):
    cur = conn.cursor()
    cur.execute(sql, params)
    return cur.fetchall()


def execute(conn, sql, params=()):
    cur = conn.cursor()
    cur.execute(sql, params)
    return cur


def is_superadmin_user(uid):
    if not uid:
        return False
    with db() as conn:
        u = fetchone(conn, "SELECT username FROM users WHERE id=%s", (uid,))
        return bool(u and u["username"].lower() in [s.lower() for s in SUPERADMIN_USERNAMES])


def generate_code():
    return f"{random.randint(100000, 999999):06d}"


def send_verification_email(email, code):
    smtp_host = os.environ.get("SMTP_HOST", "").strip()
    if not smtp_host:
        raise RuntimeError("SMTP_HOST is not configured")

    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    smtp_user = os.environ.get("SMTP_USERNAME", "").strip()
    smtp_password = os.environ.get("SMTP_PASSWORD", "").strip()
    smtp_from = os.environ.get("SMTP_FROM", smtp_user or "noreply@localhost").strip()

    msg = EmailMessage()
    msg["Subject"] = "Bir Qadam — email verification code"
    msg["From"] = smtp_from
    msg["To"] = email
    msg.set_content(
        "Your 6-digit verification code is: " + code + "\n\n"
        "This code expires in 10 minutes."
    )

    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.ehlo()
        if smtp_user and smtp_password:
            try:
                server.starttls()
            except smtplib.SMTPNotSupportedError:
                pass
            server.login(smtp_user, smtp_password)
        server.send_message(msg)


def store_verification_code(uid, code):
    expires_at = datetime.utcnow() + timedelta(minutes=TWOFA_CODE_TTL_MINUTES)
    with db() as conn:
        execute(conn,
            "UPDATE users SET verification_code=%s, verification_expires_at=%s WHERE id=%s",
            (code, expires_at, uid))
    return expires_at


def clear_verification_code(uid):
    with db() as conn:
        execute(conn,
            "UPDATE users SET verification_code=NULL, verification_expires_at=NULL WHERE id=%s",
            (uid,))


def init_db():
    with db() as conn:
        execute(conn, """CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            username TEXT NOT NULL DEFAULT '',
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            start_date TEXT NOT NULL,
            is_admin INTEGER NOT NULL DEFAULT 0,
            is_private INTEGER NOT NULL DEFAULT 0,
            two_factor_enabled INTEGER NOT NULL DEFAULT 0,
            email_verified INTEGER NOT NULL DEFAULT 1,
            verification_code TEXT DEFAULT NULL,
            verification_expires_at TIMESTAMP DEFAULT NULL
        )""")
        execute(conn, """CREATE TABLE IF NOT EXISTS entries (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            day INTEGER NOT NULL,
            entry_date TEXT NOT NULL,
            mood INTEGER DEFAULT 0,
            rating INTEGER DEFAULT 0,
            answers TEXT NOT NULL DEFAULT '{}',
            completed INTEGER NOT NULL DEFAULT 0,
            UNIQUE(user_id, day),
            FOREIGN KEY(user_id) REFERENCES users(id)
        )""")
        execute(conn, """CREATE TABLE IF NOT EXISTS reminders (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            remind_at TEXT NOT NULL,
            message TEXT NOT NULL,
            fired INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )""")

        existing_cols = {
            r["column_name"]
            for r in fetchall(conn,
                "SELECT column_name FROM information_schema.columns WHERE table_name='users'")
        }
        if "is_admin" not in existing_cols:
            execute(conn, "ALTER TABLE users ADD COLUMN is_admin INTEGER NOT NULL DEFAULT 0")
        if "is_private" not in existing_cols:
            execute(conn, "ALTER TABLE users ADD COLUMN is_private INTEGER NOT NULL DEFAULT 0")
        if "username" not in existing_cols:
            execute(conn, "ALTER TABLE users ADD COLUMN username TEXT NOT NULL DEFAULT ''")
            rows = fetchall(conn, "SELECT id, email FROM users")
            for row in rows:
                base = row["email"].split("@")[0].lower()
                base = re.sub(r'[^a-z0-9_]', '_', base)[:20]
                candidate = base
                suffix = 1
                while fetchone(conn, "SELECT 1 FROM users WHERE username=%s AND id!=%s",
                               (candidate, row["id"])):
                    candidate = base + str(suffix)
                    suffix += 1
                execute(conn, "UPDATE users SET username=%s WHERE id=%s",
                        (candidate, row["id"]))
        if "two_factor_enabled" not in existing_cols:
            execute(conn, "ALTER TABLE users ADD COLUMN two_factor_enabled INTEGER NOT NULL DEFAULT 0")
        if "email_verified" not in existing_cols:
            execute(conn, "ALTER TABLE users ADD COLUMN email_verified INTEGER NOT NULL DEFAULT 1")
        if "verification_code" not in existing_cols:
            execute(conn, "ALTER TABLE users ADD COLUMN verification_code TEXT DEFAULT NULL")
        if "verification_expires_at" not in existing_cols:
            execute(conn, "ALTER TABLE users ADD COLUMN verification_expires_at TIMESTAMP DEFAULT NULL")

        # Promote superadmins
        for su in SUPERADMIN_USERNAMES:
            execute(conn, "UPDATE users SET is_admin=1 WHERE LOWER(username)=LOWER(%s)", (su,))

        # Promote by ADMIN_EMAIL env var
        admin_email = os.environ.get("ADMIN_EMAIL", "").strip().lower()
        if admin_email:
            execute(conn, "UPDATE users SET is_admin=1 WHERE LOWER(email)=%s", (admin_email,))


# ── Auth decorators ────────────────────────────────────────────────────────
def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("auth"))
        return fn(*args, **kwargs)
    return wrapper


def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user_id = session.get("user_id")
        if not user_id:
            return redirect(url_for("auth"))
        with db() as conn:
            user = fetchone(conn, "SELECT is_admin FROM users WHERE id=%s", (user_id,))
        if not user or not user["is_admin"]:
            flash("Bu sahifaga kirish uchun admin huquqi kerak.", "error")
            return redirect(url_for("dashboard"))
        return fn(*args, **kwargs)
    return wrapper


# ── Public pages ───────────────────────────────────────────────────────────
@app.route("/")
def index():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return render_template("index.html")


@app.route("/auth", methods=["GET", "POST"])
def auth():
    mode = request.args.get("mode", "login")
    if request.method == "POST":
        mode = request.form.get("mode", "login")
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if mode == "signup":
            name = request.form.get("name", "").strip()
            username = request.form.get("username", "").strip().lower()
            if not name or len(password) < 8:
                flash("Ism kiriting va kamida 8 belgili parol tanlang.", "error")
                return render_template("auth.html", mode=mode)
            if not USERNAME_RE.match(username):
                flash("Foydalanuvchi nomi 3-24 belgi, faqat harf/raqam/_ bo'lishi kerak.", "error")
                return render_template("auth.html", mode=mode)
            try:
                with db() as conn:
                    if fetchone(conn, "SELECT 1 FROM users WHERE username=%s", (username,)):
                        flash("Bu foydalanuvchi nomi band. Boshqasini tanlang.", "error")
                        return render_template("auth.html", mode=mode)
                    cur = execute(conn,
                        "INSERT INTO users(name,username,email,password_hash,start_date,email_verified,two_factor_enabled) "
                        "VALUES(%s,%s,%s,%s,%s,%s,%s) RETURNING id",
                        (name, username, email, generate_password_hash(password),
                         date.today().isoformat(), 0, 0))
                    user_id = cur.fetchone()["id"]
            except psycopg2.errors.UniqueViolation:
                flash("Bu email allaqachon ro'yxatdan o'tgan.", "error")
                return render_template("auth.html", mode=mode)

            session["pending_user_id"] = user_id
            session["pending_email"] = email
            session["pending_verification_type"] = "signup"
            code = generate_code()
            try:
                send_verification_email(email, code)
                store_verification_code(user_id, code)
            except Exception as exc:
                flash("Tasdiqlash kodi yuborilmadi. SMTP sozlamalari tekshirilishi kerak: " + str(exc), "error")
                with db() as conn:
                    execute(conn, "DELETE FROM users WHERE id=%s", (user_id,))
                session.pop("pending_user_id", None)
                session.pop("pending_email", None)
                session.pop("pending_verification_type", None)
                return render_template("auth.html", mode=mode)

            flash("Tasdiqlash kodi emailingizga yuborildi.", "success")
            return redirect(url_for("verify_code"))

        else:
            login_val = request.form.get("email", "").strip().lower()
            with db() as conn:
                user = fetchone(conn,
                    "SELECT * FROM users WHERE LOWER(email)=%s OR LOWER(username)=%s",
                    (login_val, login_val))
            if user and check_password_hash(user["password_hash"], password):
                if user["email_verified"] == 0:
                    session["pending_user_id"] = user["id"]
                    session["pending_email"] = user["email"]
                    session["pending_verification_type"] = "signup"
                    code = generate_code()
                    try:
                        send_verification_email(user["email"], code)
                        store_verification_code(user["id"], code)
                    except Exception as exc:
                        flash("Tasdiqlash kodi yuborilmadi: " + str(exc), "error")
                        return render_template("auth.html", mode=mode)
                    flash("Hisobingiz hali tasdiqlanmagan. Tasdiqlash kodi emailingizga yuborildi.", "success")
                    return redirect(url_for("verify_code"))

                if user["two_factor_enabled"]:
                    session["pending_user_id"] = user["id"]
                    session["pending_email"] = user["email"]
                    session["pending_verification_type"] = "login"
                    code = generate_code()
                    try:
                        send_verification_email(user["email"], code)
                        store_verification_code(user["id"], code)
                    except Exception as exc:
                        flash("2FA kodi yuborilmadi: " + str(exc), "error")
                        session.pop("pending_user_id", None)
                        session.pop("pending_email", None)
                        session.pop("pending_verification_type", None)
                        return render_template("auth.html", mode=mode)
                    flash("2FA kodi emailingizga yuborildi.", "success")
                    return redirect(url_for("verify_code"))

                session["user_id"] = user["id"]
                session["name"] = user["name"]
                return redirect(url_for("dashboard"))
            flash("Email / foydalanuvchi nomi yoki parol noto'g'ri.", "error")

    return render_template("auth.html", mode=mode)


@app.route("/verify-code", methods=["GET", "POST"])
def verify_code():
    pending_user_id = session.get("pending_user_id")
    if not pending_user_id:
        return redirect(url_for("auth"))

    if request.method == "POST":
        code = request.form.get("code", "").strip()
        with db() as conn:
            user = fetchone(conn, "SELECT * FROM users WHERE id=%s", (pending_user_id,))
        if not user:
            flash("Foydalanuvchi topilmadi.", "error")
            return redirect(url_for("auth"))

        expires_at = user["verification_expires_at"]
        if not user["verification_code"] or user["verification_code"] != code:
            flash("Noto'g'ri tasdiqlash kodi.", "error")
            return render_template("auth.html", mode="verify", email=session.get("pending_email"))
        if expires_at is None or datetime.utcnow() > expires_at:
            flash("Tasdiqlash kodi muddati tugagan. Yangi kod so'rang.", "error")
            return render_template("auth.html", mode="verify", email=session.get("pending_email"))

        with db() as conn:
            execute(conn,
                "UPDATE users SET email_verified=1, verification_code=NULL, verification_expires_at=NULL WHERE id=%s",
                (pending_user_id,))

        clear_verification_code(pending_user_id)

        session["user_id"] = user["id"]
        session["name"] = user["name"]
        session.pop("pending_user_id", None)
        session.pop("pending_email", None)
        session.pop("pending_verification_type", None)

        if user["two_factor_enabled"]:
            flash("2FA tasdiqlandi. Xush kelibsiz!", "success")
        else:
            flash("Email tasdiqlandi. Xush kelibsiz!", "success")
        return redirect(url_for("dashboard"))

    return render_template("auth.html", mode="verify", email=session.get("pending_email"))


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


# ── Dashboard ────────────────────────────────────────────────────────────
@app.route("/dashboard")
@login_required
def dashboard():
    with db() as conn:
        rows     = fetchall(conn, "SELECT * FROM entries WHERE user_id=%s", (session["user_id"],))
        user_row = fetchone(conn, "SELECT is_admin FROM users WHERE id=%s", (session["user_id"],))
    entries = {
        str(r["day"]): {
            "mood":       r["mood"],
            "rating":     r["rating"],
            "answers":    json.loads(r["answers"]),
            "completed":  bool(r["completed"]),
            "entry_date": str(r["entry_date"])
        } for r in rows
    }
    is_admin = bool(user_row and user_row["is_admin"])
    is_super = is_superadmin_user(session["user_id"])
    return render_template("dashboard.html", name=session.get("name", "Do'st"),
                           entries=entries, is_admin=is_admin, is_superadmin=is_super)


# ── Account settings ────────────────────────────────────────────────────────
@app.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    uid = session["user_id"]
    with db() as conn:
        user = fetchone(conn,
            "SELECT id,name,username,email,is_private,two_factor_enabled FROM users WHERE id=%s", (uid,))

    if request.method == "POST":
        action = request.form.get("action")

        if action == "profile":
            new_name     = request.form.get("name", "").strip()
            new_username = request.form.get("username", "").strip().lower()
            is_private   = 1 if request.form.get("is_private") else 0
            if not new_name:
                flash("Ism bo'sh bo'lmasin.", "error")
                return redirect(url_for("settings"))
            if not USERNAME_RE.match(new_username):
                flash("Foydalanuvchi nomi 3-24 belgi, faqat harf/raqam/_ bo'lishi kerak.", "error")
                return redirect(url_for("settings"))
            with db() as conn:
                clash = fetchone(conn,
                    "SELECT 1 FROM users WHERE username=%s AND id!=%s", (new_username, uid))
                if clash:
                    flash("Bu foydalanuvchi nomi band.", "error")
                    return redirect(url_for("settings"))
                execute(conn,
                    "UPDATE users SET name=%s, username=%s, is_private=%s WHERE id=%s",
                    (new_name, new_username, is_private, uid))
            session["name"] = new_name
            flash("Profil yangilandi.", "success")

        elif action == "password":
            old_pw = request.form.get("old_password", "")
            new_pw = request.form.get("new_password", "")
            with db() as conn:
                u = fetchone(conn, "SELECT password_hash FROM users WHERE id=%s", (uid,))
            if not check_password_hash(u["password_hash"], old_pw):
                flash("Eski parol noto'g'ri.", "error")
                return redirect(url_for("settings"))
            if len(new_pw) < 8:
                flash("Yangi parol kamida 8 belgi bo'lishi kerak.", "error")
                return redirect(url_for("settings"))
            with db() as conn:
                execute(conn, "UPDATE users SET password_hash=%s WHERE id=%s",
                        (generate_password_hash(new_pw), uid))
            flash("Parol yangilandi.", "success")

        elif action == "twofa":
            enable = request.form.get("two_factor_enabled") == "on"
            with db() as conn:
                current = fetchone(conn, "SELECT email, two_factor_enabled FROM users WHERE id=%s", (uid,))
            if enable and not current["two_factor_enabled"]:
                code = generate_code()
                try:
                    send_verification_email(current["email"], code)
                    store_verification_code(uid, code)
                    with db() as conn:
                        execute(conn, "UPDATE users SET two_factor_enabled=1 WHERE id=%s", (uid,))
                    flash("2FA yoqildi. 6 xonali kod emailingizga yuborildi.", "success")
                except Exception as exc:
                    flash("2FA yoqib bo'lmadi. SMTP sozlamalari tekshirilishi kerak: " + str(exc), "error")
            elif not enable and current["two_factor_enabled"]:
                with db() as conn:
                    execute(conn, "UPDATE users SET two_factor_enabled=0 WHERE id=%s", (uid,))
                    clear_verification_code(uid)
                flash("2FA o'chirildi.", "success")
            else:
                flash("2FA holati o'zgarmadi.", "info")

        return redirect(url_for("settings"))

    return render_template("account_settings.html", user=user)


# ── Entry API ─────────────────────────────────────────────────────────────
@app.route("/api/entry/<int:day>", methods=["POST"])
@login_required
def save_entry(day):
    if not 1 <= day <= 30:
        return jsonify(ok=False, error="Kun noto'g'ri"), 400
    with db() as conn:
        existing = fetchone(conn,
            "SELECT completed FROM entries WHERE user_id=%s AND day=%s",
            (session["user_id"], day))
    if existing and existing["completed"]:
        return jsonify(ok=False, error="Bu kun allaqachon yakunlangan va tahrirlash mumkin emas."), 403

    payload = request.get_json(silent=True) or {}
    mood    = max(0, min(5, int(payload.get("mood",   0) or 0)))
    rating  = max(0, min(5, int(payload.get("rating", 0) or 0)))
    answers = payload.get("answers", {})
    if not isinstance(answers, dict):
        return jsonify(ok=False, error="Javoblar noto'g'ri"), 400

    with db() as conn:
        execute(conn, """
            INSERT INTO entries(user_id,day,entry_date,mood,rating,answers,completed)
            VALUES(%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (user_id,day) DO UPDATE SET
                entry_date=EXCLUDED.entry_date,
                mood=EXCLUDED.mood,
                rating=EXCLUDED.rating,
                answers=EXCLUDED.answers,
                completed=EXCLUDED.completed
        """, (session["user_id"], day, date.today().isoformat(), mood, rating,
              json.dumps(answers, ensure_ascii=False), int(bool(payload.get("completed")))))
    return jsonify(ok=True)


@app.route("/api/entries")
@login_required
def get_entries():
    with db() as conn:
        rows = fetchall(conn,
            "SELECT day,mood,rating,completed,entry_date FROM entries WHERE user_id=%s",
            (session["user_id"],))
    return jsonify({str(r["day"]): dict(r) for r in rows})


# ── Reminders ─────────────────────────────────────────────────────────────
@app.route("/api/reminders", methods=["GET"])
@login_required
def get_reminders():
    with db() as conn:
        rows = fetchall(conn,
            "SELECT id,remind_at,message,fired FROM reminders WHERE user_id=%s ORDER BY remind_at",
            (session["user_id"],))
    return jsonify([dict(r) for r in rows])


@app.route("/api/reminders", methods=["POST"])
@login_required
def create_reminder():
    payload   = request.get_json(silent=True) or {}
    remind_at = payload.get("remind_at", "").strip()
    message   = payload.get("message",   "").strip()
    if not remind_at or not message:
        return jsonify(ok=False, error="remind_at and message are required"), 400
    with db() as conn:
        cur = execute(conn,
            "INSERT INTO reminders(user_id,remind_at,message) VALUES(%s,%s,%s) RETURNING id",
            (session["user_id"], remind_at, message))
        rid = cur.fetchone()["id"]
    return jsonify(ok=True, id=rid)


@app.route("/api/reminders/<int:rid>", methods=["DELETE"])
@login_required
def delete_reminder(rid):
    with db() as conn:
        execute(conn, "DELETE FROM reminders WHERE id=%s AND user_id=%s", (rid, session["user_id"]))
    return jsonify(ok=True)


@app.route("/api/reminders/<int:rid>/fire", methods=["POST"])
@login_required
def fire_reminder(rid):
    with db() as conn:
        execute(conn, "UPDATE reminders SET fired=1 WHERE id=%s AND user_id=%s", (rid, session["user_id"]))
    return jsonify(ok=True)


# ── Admin ────────────────────────────────────────────────────────────────
@app.route("/admin")
@admin_required
def admin():
    uid = session["user_id"]
    with db() as conn:
        users = fetchall(conn, """
            SELECT u.id, u.name, u.username, u.email, u.start_date, u.is_admin,
                   COUNT(e.id) AS entries_count,
                   COALESCE(SUM(e.completed),0) AS completed_count
            FROM users u LEFT JOIN entries e ON e.user_id=u.id
            GROUP BY u.id, u.name, u.username, u.email, u.start_date, u.is_admin
            ORDER BY u.id DESC
        """)
        stats = fetchone(conn, """
            SELECT COUNT(*) AS total_users,
                   COALESCE(SUM(is_admin),0) AS total_admins FROM users
        """)
        total_entries   = fetchone(conn, "SELECT COUNT(*) AS c FROM entries")["c"]
        total_reminders = fetchone(conn, "SELECT COUNT(*) AS c FROM reminders WHERE fired=0")["c"]
    return render_template("admin.html", users=users,
                            total_users=stats["total_users"],
                            total_admins=stats["total_admins"],
                            total_entries=total_entries,
                            total_reminders=total_reminders,
                            is_superadmin=is_superadmin_user(uid))


@app.route("/api/admin/users/<int:target_id>/role", methods=["POST"])
@login_required
def admin_toggle_user_role(target_id):
    uid = session["user_id"]
    if not is_superadmin_user(uid):
        return jsonify(ok=False, error="Faqat superadmin bu amalni bajarishi mumkin."), 403
    data       = request.get_json(silent=True) or {}
    make_admin = 1 if data.get("is_admin") else 0
    with db() as conn:
        target = fetchone(conn, "SELECT id, username FROM users WHERE id=%s", (target_id,))
        if not target:
            return jsonify(ok=False, error="Foydalanuvchi topilmadi."), 404
        if target["username"].lower() in [s.lower() for s in SUPERADMIN_USERNAMES] and make_admin == 0:
            return jsonify(ok=False, error="Bosh administratorning huquqini bekor qilib bo'lmaydi."), 400
        execute(conn, "UPDATE users SET is_admin=%s WHERE id=%s", (make_admin, target_id))
    return jsonify(ok=True, is_admin=bool(make_admin))


@app.route("/api/admin/users/<int:target_id>/reset-password", methods=["POST"])
@login_required
def admin_reset_user_password(target_id):
    uid = session["user_id"]
    if not is_superadmin_user(uid):
        return jsonify(ok=False, error="Faqat superadmin parollarni yangilash huquqiga ega."), 403
    data         = request.get_json(silent=True) or {}
    new_password = (data.get("password") or "").strip()
    if len(new_password) < 6:
        return jsonify(ok=False, error="Parol kamida 6 ta belgi bo'lishi kerak."), 400
    with db() as conn:
        if not fetchone(conn, "SELECT id FROM users WHERE id=%s", (target_id,)):
            return jsonify(ok=False, error="Foydalanuvchi topilmadi."), 404
        execute(conn, "UPDATE users SET password_hash=%s WHERE id=%s",
                (generate_password_hash(new_password), target_id))
    return jsonify(ok=True)


@app.route("/api/admin/reminders")
@admin_required
def admin_get_reminders():
    with db() as conn:
        rows = fetchall(conn, """
            SELECT r.id, r.user_id, u.name AS user_name, u.email,
                   r.remind_at, r.message, r.fired
            FROM reminders r JOIN users u ON u.id=r.user_id
            ORDER BY r.fired ASC, r.remind_at ASC
        """)
    return jsonify([dict(r) for r in rows])


@app.route("/api/admin/reminders/<int:rid>", methods=["DELETE"])
@admin_required
def admin_delete_reminder(rid):
    with db() as conn:
        execute(conn, "DELETE FROM reminders WHERE id=%s", (rid,))
    return jsonify(ok=True)


@app.route("/admin/user/<int:uid>")
@admin_required
def admin_user_detail(uid):
    with db() as conn:
        user = fetchone(conn,
            "SELECT id,name,username,email,start_date FROM users WHERE id=%s", (uid,))
        if not user:
            flash("Foydalanuvchi topilmadi.", "error")
            return redirect(url_for("admin"))
        entries = fetchall(conn,
            "SELECT day,entry_date,mood,rating,completed,answers FROM entries WHERE user_id=%s ORDER BY day",
            (uid,))
    entries_list = [{
        "day":        e["day"],
        "entry_date": str(e["entry_date"]),
        "mood":       e["mood"],
        "rating":     e["rating"],
        "completed":  bool(e["completed"]),
        "answers":    json.loads(e["answers"])
    } for e in entries]
    return render_template("admin_user.html", user=user, entries=entries_list)


init_db()

if __name__ == "__main__":
    app.run(debug=False)
