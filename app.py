import os, json, re, secrets
import os, json, re, secrets
from datetime import date
from functools import wraps
from contextlib import contextmanager

import psycopg2
import psycopg2.extras
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash

# ── App setup ───────────────────────────────────────────────────────────[...]
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


# ── Database helpers ────────────────────────────────────────────────────────��[...]
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
            is_private INTEGER NOT NULL DEFAULT 0
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
        execute(conn, """CREATE TABLE IF NOT EXISTS messages (
            id SERIAL PRIMARY KEY,
            sender_id INTEGER NOT NULL,
            receiver_id INTEGER NOT NULL,
            body TEXT NOT NULL,
            sent_at TIMESTAMP NOT NULL DEFAULT NOW(),
            is_read INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY(sender_id) REFERENCES users(id),
            FOREIGN KEY(receiver_id) REFERENCES users(id)
        )""")
        execute(conn, """CREATE TABLE IF NOT EXISTS chat_groups (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            creator_id INTEGER NOT NULL,
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            FOREIGN KEY(creator_id) REFERENCES users(id)
        )""")
        execute(conn, """CREATE TABLE IF NOT EXISTS group_members (
            id SERIAL PRIMARY KEY,
            group_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            role TEXT NOT NULL DEFAULT 'member',
            joined_at TIMESTAMP NOT NULL DEFAULT NOW(),
            UNIQUE(group_id, user_id),
            FOREIGN KEY(group_id) REFERENCES chat_groups(id) ON DELETE CASCADE,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )""")
        execute(conn, """CREATE TABLE IF NOT EXISTS group_messages (
            id SERIAL PRIMARY KEY,
            group_id INTEGER NOT NULL,
            sender_id INTEGER NOT NULL,
            body TEXT NOT NULL,
            sent_at TIMESTAMP NOT NULL DEFAULT NOW(),
            FOREIGN KEY(group_id) REFERENCES chat_groups(id) ON DELETE CASCADE,
            FOREIGN KEY(sender_id) REFERENCES users(id)
        )""")

        # Rename old 'groups' table to 'chat_groups' if it exists
        execute(conn, """
            DO $$
            BEGIN
                IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name='groups')
                   AND NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name='chat_groups')
                THEN
                    ALTER TABLE groups RENAME TO chat_groups;
                END IF;
            END $$;
        """)
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

        # Promote superadmins
        for su in SUPERADMIN_USERNAMES:
            execute(conn, "UPDATE users SET is_admin=1 WHERE LOWER(username)=LOWER(%s)", (su,))

        # Promote by ADMIN_EMAIL env var
        admin_email = os.environ.get("ADMIN_EMAIL", "").strip().lower()
        if admin_email:
            execute(conn, "UPDATE users SET is_admin=1 WHERE LOWER(email)=%s", (admin_email,))


def chat_template_vars(uid):
    return {
        "superadmin_usernames": SUPERADMIN_USERNAMES,
        "superadmin_username": SUPERADMIN_USERNAMES[0] if SUPERADMIN_USERNAMES else None,
        "is_superadmin": is_superadmin_user(uid),
    }


# ── Auth decorators ────────────────────────────────────────────────────────��[...]
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


# ── Public pages ─────────────────────────────────────────────────────────��[...]
@app.route("/")
def index():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return render_template("index.html")


@app.route("/auth", methods=["GET", "POST"])
def auth():
    mode = request.args.get("mode", "login")
    if request.method == "POST":
        mode     = request.form.get("mode", "login")
        email    = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if mode == "signup":
            name     = request.form.get("name", "").strip()
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
                    execute(conn,
                        "INSERT INTO users(name,username,email,password_hash,start_date) "
                        "VALUES(%s,%s,%s,%s,%s)",
                        (name, username, email, generate_password_hash(password),
                         date.today().isoformat()))
            except psycopg2.errors.UniqueViolation:
                flash("Bu email allaqachon ro'yxatdan o'tgan.", "error")
                return render_template("auth.html", mode=mode)

            with db() as conn:
                user = fetchone(conn, "SELECT id,name FROM users WHERE email=%s", (email,))
            session["user_id"] = user["id"]
            session["name"]    = user["name"]
            return redirect(url_for("dashboard"))

        else:
            login_val = request.form.get("email", "").strip().lower()
            with db() as conn:
                user = fetchone(conn,
                    "SELECT * FROM users WHERE LOWER(email)=%s OR LOWER(username)=%s",
                    (login_val, login_val))
            if user and check_password_hash(user["password_hash"], password):
                session["user_id"] = user["id"]
                session["name"]    = user["name"]
                return redirect(url_for("dashboard"))
            flash("Email / foydalanuvchi nomi yoki parol noto'g'ri.", "error")

    return render_template("auth.html", mode=mode)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


# ── Dashboard ──────────────────────────────────────────────────────────��[...]
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


# ── Account settings ────────────────────────────────────────────────────────�[...]
@app.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    uid = session["user_id"]
    with db() as conn:
        user = fetchone(conn,
            "SELECT id,name,username,email,is_private FROM users WHERE id=%s", (uid,))

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

        return redirect(url_for("settings"))

    return render_template("account_settings.html", user=user)


# ── Chat helpers ─────────────────────────────────────────────────────────��[...]
def get_chat_sidebar_data(conn, uid):
    convos = fetchall(conn, """
        SELECT u.id, u.name, u.username, u.is_private,
               MAX(m.sent_at) AS last_at,
               SUM(CASE WHEN m.receiver_id=%s AND m.is_read=0 THEN 1 ELSE 0 END) AS unread
        FROM messages m
        JOIN users u ON u.id = CASE WHEN m.sender_id=%s THEN m.receiver_id ELSE m.sender_id END
        WHERE m.sender_id=%s OR m.receiver_id=%s
        GROUP BY u.id, u.name, u.username, u.is_private
        ORDER BY last_at DESC
    """, (uid, uid, uid, uid))

    my_groups = fetchall(conn, """
        SELECT g.id, g.name, g.description, g.creator_id, g.created_at,
               gm.role AS my_role,
               (SELECT COUNT(*) FROM group_members WHERE group_id=g.id) AS member_count,
               (SELECT MAX(gm2.sent_at) FROM group_messages gm2 WHERE gm2.group_id=g.id) AS last_at
        FROM chat_groups g
        JOIN group_members gm ON gm.group_id=g.id AND gm.user_id=%s
        ORDER BY COALESCE(last_at, g.created_at) DESC
    """, (uid,))

    all_users = fetchall(conn, """
        SELECT u.id, u.name, u.username, u.is_private, u.is_admin,
               (SELECT COUNT(*) FROM entries e WHERE e.user_id=u.id AND e.completed=1) AS completed_count
        FROM users u
        WHERE u.id != %s
        ORDER BY u.name ASC
    """, (uid,))

    return convos, my_groups, all_users


# ── Chat views ──────────────────────────────────────────────────────────�[...]
@app.route("/chat")
@login_required
def chat():
    uid = session["user_id"]
    with db() as conn:
        convos, my_groups, all_users = get_chat_sidebar_data(conn, uid)
    return render_template("chat.html", convos=convos, my_groups=my_groups,
                            all_users=all_users, my_id=uid, mode=None,
                            is_superadmin=is_superadmin_user(uid),
                            **chat_template_vars(uid))


@app.route("/chat/<string:username>")
@login_required
def chat_with(username):
    uid = session["user_id"]
    with db() as conn:
        partner = fetchone(conn,
            "SELECT id,name,username,is_private,is_admin FROM users WHERE username=%s", (username,))
        if not partner or partner["id"] == uid:
            flash("Foydalanuvchi topilmadi.", "error")
            return redirect(url_for("chat"))
        execute(conn,
            "UPDATE messages SET is_read=1 WHERE sender_id=%s AND receiver_id=%s",
            (partner["id"], uid))
        msgs = fetchall(conn, """
            SELECT m.id, m.sender_id, m.body, m.sent_at, m.is_read,
                   u.name AS sender_name
            FROM messages m
            JOIN users u ON u.id = m.sender_id
            WHERE (m.sender_id=%s AND m.receiver_id=%s)
               OR (m.sender_id=%s AND m.receiver_id=%s)
            ORDER BY m.sent_at ASC
        """, (uid, partner["id"], partner["id"], uid))
        convos, my_groups, all_users = get_chat_sidebar_data(conn, uid)
    return render_template("chat.html", convos=convos, my_groups=my_groups,
                            all_users=all_users, partner=partner,
                            msgs=msgs, my_id=uid, mode="dm",
                            is_superadmin=is_superadmin_user(uid),
                            **chat_template_vars(uid))


@app.route("/chat/group/<int:group_id>")
@login_required
def chat_group(group_id):
    uid = session["user_id"]
    with db() as conn:
        my_membership = fetchone(conn,
            "SELECT role FROM group_members WHERE group_id=%s AND user_id=%s", (group_id, uid))
        if not my_membership:
            flash("Siz bu guruh a'zosi emassiz.", "error")
            return redirect(url_for("chat"))
        group = fetchone(conn,
            "SELECT id, name, description, creator_id, created_at FROM chat_groups WHERE id=%s", (group_id,))
        if not group:
            flash("Guruh topilmadi.", "error")
            return redirect(url_for("chat"))
        group_members = fetchall(conn, """
            SELECT u.id, u.name, u.username, u.is_admin AS site_admin, gm.role, gm.joined_at
            FROM group_members gm
            JOIN users u ON u.id = gm.user_id
            WHERE gm.group_id = %s
            ORDER BY CASE gm.role WHEN 'owner' THEN 1 WHEN 'admin' THEN 2 ELSE 3 END, u.name ASC
        """, (group_id,))
        msgs = fetchall(conn, """
            SELECT gm.id, gm.sender_id, u.name AS sender_name, u.username AS sender_username,
                   gmem.role AS sender_role, gm.body, gm.sent_at
            FROM group_messages gm
            JOIN users u ON u.id = gm.sender_id
            LEFT JOIN group_members gmem ON gmem.group_id = gm.group_id AND gmem.user_id = gm.sender_id
            WHERE gm.group_id = %s
            ORDER BY gm.sent_at ASC
        """, (group_id,))
        convos, my_groups, all_users = get_chat_sidebar_data(conn, uid)
    return render_template("chat.html", convos=convos, my_groups=my_groups,
                            all_users=all_users, active_group=group,
                            group_members=group_members, my_role=my_membership["role"],
                            msgs=msgs, my_id=uid, mode="group",
                            is_superadmin=is_superadmin_user(uid),
                            **chat_template_vars(uid))


# ── Search & user APIs ───────────────────────────────────────────────────────��[...]
@app.route("/api/search")
@login_required
def search_users():
    q = request.args.get("q", "").strip()
    if len(q) < 2:
        return jsonify([])
    uid = session["user_id"]
    with db() as conn:
        rows = fetchall(conn, """
            SELECT id, name, username, is_private,
                   (SELECT COUNT(*) FROM entries e WHERE e.user_id=users.id AND e.completed=1) AS completed_count
            FROM users
            WHERE (username ILIKE %s OR name ILIKE %s) AND id != %s
            ORDER BY username
            LIMIT 20
        """, (f"%{q}%", f"%{q}%", uid))
    return jsonify([{
        "id":         r["id"],
        "name":       r["name"],
        "username":   r["username"],
        "is_private": bool(r["is_private"]),
        "completed":  r["completed_count"] if not r["is_private"] else None
    } for r in rows])


@app.route("/api/all-users")
@login_required
def get_all_users():
    uid = session["user_id"]
    with db() as conn:
        rows = fetchall(conn, """
            SELECT u.id, u.name, u.username, u.is_private, u.is_admin,
                   (SELECT COUNT(*) FROM entries e WHERE e.user_id=u.id AND e.completed=1) AS completed_count
            FROM users u
            WHERE u.id != %s
            ORDER BY u.name ASC
        """, (uid,))
    return jsonify([{
        "id":         r["id"],
        "name":       r["name"],
        "username":   r["username"],
        "is_private": bool(r["is_private"]),
        "is_admin":   bool(r["is_admin"]),
        "completed":  r["completed_count"] if not r["is_private"] else None
    } for r in rows])


# ── Direct chat API ────────────────────────────────────────────────────────��[...]
@app.route("/api/chat/<int:partner_id>", methods=["POST"])
@login_required
def send_message(partner_id):
    uid  = session["user_id"]
    body = (request.get_json(silent=True) or {}).get("body", "").strip()
    if not body or len(body) > 2000:
        return jsonify(ok=False, error="Xabar bo'sh yoki juda uzun."), 400
    with db() as conn:
        partner = fetchone(conn, "SELECT id FROM users WHERE id=%s", (partner_id,))
        if not partner:
            return jsonify(ok=False, error="Foydalanuvchi topilmadi."), 404
        cur = execute(conn,
            "INSERT INTO messages(sender_id,receiver_id,body) VALUES(%s,%s,%s) RETURNING id,sent_at",
            (uid, partner_id, body))
        row = cur.fetchone()
    return jsonify(ok=True, id=row["id"],
                   sent_at=str(row["sent_at"]), body=body)


@app.route("/api/chat/<int:partner_id>/poll")
@login_required
def poll_messages(partner_id):
    uid   = session["user_id"]
    after = request.args.get("after", "1970-01-01 00:00:00")
    with db() as conn:
        msgs = fetchall(conn, """
            SELECT m.id, m.sender_id, m.body, m.sent_at
            FROM messages m
            WHERE ((m.sender_id=%s AND m.receiver_id=%s)
                OR (m.sender_id=%s AND m.receiver_id=%s))
              AND m.sent_at > %s
            ORDER BY m.sent_at ASC
        """, (uid, partner_id, partner_id, uid, after))
        execute(conn,
            "UPDATE messages SET is_read=1 WHERE sender_id=%s AND receiver_id=%s",
            (partner_id, uid))
    return jsonify([{"id": m["id"], "sender_id": m["sender_id"],
                     "body": m["body"], "sent_at": str(m["sent_at"])} for m in msgs])


# ── Groups API ──────────────────────────────────────────────────────────�[...]
@app.route("/api/groups", methods=["GET", "POST"])
@login_required
def api_groups():
    uid = session["user_id"]
    if request.method == "POST":
        data        = request.get_json(silent=True) or {}
        name        = (data.get("name") or "").strip()
        description = (data.get("description") or "").strip()
        member_ids  = data.get("member_ids") or []
        if not name or len(name) > 80:
            return jsonify(ok=False, error="Guruh nomi 1 dan 80 belgigacha bo'lishi kerak."), 400
        with db() as conn:
            cur = execute(conn,
                "INSERT INTO chat_groups(name, description, creator_id) VALUES(%s,%s,%s) RETURNING id",
                (name, description, uid))
            gid = cur.fetchone()["id"]
            execute(conn,
                "INSERT INTO group_members(group_id, user_id, role) VALUES(%s,%s,'owner')",
                (gid, uid))
            for mid in member_ids:
                try:
                    mid = int(mid)
                    if mid != uid:
                        execute(conn,
                            "INSERT INTO group_members(group_id, user_id, role) "
                            "VALUES(%s,%s,'member') ON CONFLICT DO NOTHING",
                            (gid, mid))
                except (ValueError, TypeError):
                    pass
        return jsonify(ok=True, group_id=gid)

    with db() as conn:
        groups = fetchall(conn, """
            SELECT g.id, g.name, g.description, g.creator_id, g.created_at,
                   gm.role AS my_role,
                   (SELECT COUNT(*) FROM group_members WHERE group_id=g.id) AS member_count
            FROM chat_groups g
            JOIN group_members gm ON gm.group_id=g.id AND gm.user_id=%s
            ORDER BY g.id DESC
        """, (uid,))
    return jsonify([dict(g) for g in groups])


@app.route("/api/group/<int:group_id>/send", methods=["POST"])
@login_required
def send_group_message(group_id):
    uid  = session["user_id"]
    body = (request.get_json(silent=True) or {}).get("body", "").strip()
    if not body or len(body) > 2000:
        return jsonify(ok=False, error="Xabar bo'sh yoki juda uzun."), 400
    with db() as conn:
        member = fetchone(conn,
            "SELECT role FROM group_members WHERE group_id=%s AND user_id=%s", (group_id, uid))
        if not member:
            return jsonify(ok=False, error="Siz bu guruh a'zosi emassiz."), 403
        cur = execute(conn,
            "INSERT INTO group_messages(group_id, sender_id, body) VALUES(%s,%s,%s) RETURNING id,sent_at",
            (group_id, uid, body))
        row = cur.fetchone()
        sender = fetchone(conn, "SELECT name, username FROM users WHERE id=%s", (uid,))
    return jsonify(ok=True, id=row["id"], sent_at=str(row["sent_at"]), body=body,
                   sender_id=uid, sender_name=sender["name"], sender_role=member["role"])


@app.route("/api/group/<int:group_id>/poll")
@login_required
def poll_group_messages(group_id):
    uid   = session["user_id"]
    after = request.args.get("after", "1970-01-01 00:00:00")
    with db() as conn:
        member = fetchone(conn,
            "SELECT role FROM group_members WHERE group_id=%s AND user_id=%s", (group_id, uid))
        if not member:
            return jsonify([]), 403
        msgs = fetchall(conn, """
            SELECT gm.id, gm.sender_id, gm.body, gm.sent_at,
                   u.name AS sender_name, u.username AS sender_username,
                   gmem.role AS sender_role
            FROM group_messages gm
            JOIN users u ON u.id = gm.sender_id
            LEFT JOIN group_members gmem ON gmem.group_id = gm.group_id AND gmem.user_id = gm.sender_id
            WHERE gm.group_id = %s AND gm.sent_at > %s
            ORDER BY gm.sent_at ASC
        """, (group_id, after))
    return jsonify([{**dict(m), "sent_at": str(m["sent_at"])} for m in msgs])


@app.route("/api/group/<int:group_id>/details")
@login_required
def group_details(group_id):
    uid = session["user_id"]
    with db() as conn:
        my_membership = fetchone(conn,
            "SELECT role FROM group_members WHERE group_id=%s AND user_id=%s", (group_id, uid))
        if not my_membership:
            return jsonify(ok=False, error="Siz bu guruh a'zosi emassiz."), 403
        group = fetchone(conn,
            "SELECT id, name, description, creator_id, created_at FROM chat_groups WHERE id=%s", (group_id,))
        members = fetchall(conn, """
            SELECT u.id, u.name, u.username, gm.role, gm.joined_at
            FROM group_members gm
            JOIN users u ON u.id = gm.user_id
            WHERE gm.group_id = %s
            ORDER BY CASE gm.role WHEN 'owner' THEN 1 WHEN 'admin' THEN 2 ELSE 3 END, u.name ASC
        """, (group_id,))
    return jsonify(ok=True, group=dict(group), my_role=my_membership["role"],
                   members=[dict(m) for m in members])


@app.route("/api/group/<int:group_id>/members", methods=["POST"])
@login_required
def add_group_member(group_id):
    uid        = session["user_id"]
    data       = request.get_json(silent=True) or {}
    target_uid = data.get("user_id")
    if not target_uid:
        return jsonify(ok=False, error="Foydalanuvchi ko'rsatilmadi."), 400
    with db() as conn:
        my_membership = fetchone(conn,
            "SELECT role FROM group_members WHERE group_id=%s AND user_id=%s", (group_id, uid))
        if not my_membership or my_membership["role"] not in ("owner", "admin"):
            return jsonify(ok=False, error="Faqat guruh egasi yoki admin a'zo qo'sha oladi."), 403
        if not fetchone(conn, "SELECT id FROM users WHERE id=%s", (target_uid,)):
            return jsonify(ok=False, error="Foydalanuvchi topilmadi."), 404
        try:
            execute(conn,
                "INSERT INTO group_members(group_id, user_id, role) VALUES(%s,%s,'member')",
                (group_id, target_uid))
        except psycopg2.errors.UniqueViolation:
            return jsonify(ok=False, error="Bu foydalanuvchi allaqachon guruhda."), 400
    return jsonify(ok=True)


@app.route("/api/group/<int:group_id>/members/<int:target_id>/role", methods=["POST"])
@login_required
def update_group_member_role(group_id, target_id):
    uid      = session["user_id"]
    data     = request.get_json(silent=True) or {}
    new_role = (data.get("role") or "").strip().lower()
    if new_role not in ("admin", "member"):
        return jsonify(ok=False, error="Noto'g'ri rol tanlandi."), 400
    with db() as conn:
        my_membership = fetchone(conn,
            "SELECT role FROM group_members WHERE group_id=%s AND user_id=%s", (group_id, uid))
        is_super = is_superadmin_user(uid)
        if not is_super and (not my_membership or my_membership["role"] != "owner"):
            return jsonify(ok=False, error="Faqat guruh egasi admin tayinlashi mumkin."), 403
        target = fetchone(conn,
            "SELECT role FROM group_members WHERE group_id=%s AND user_id=%s", (group_id, target_id))
        if not target:
            return jsonify(ok=False, error="Guruh a'zosi topilmadi."), 404
        if target["role"] == "owner":
            return jsonify(ok=False, error="Guruh egasining rolini o'zgartirib bo'lmaydi."), 400
        execute(conn,
            "UPDATE group_members SET role=%s WHERE group_id=%s AND user_id=%s",
            (new_role, group_id, target_id))
    return jsonify(ok=True)


@app.route("/api/group/<int:group_id>/members/<int:target_id>", methods=["DELETE"])
@login_required
def remove_group_member(group_id, target_id):
    uid = session["user_id"]
    with db() as conn:
        my_membership = fetchone(conn,
            "SELECT role FROM group_members WHERE group_id=%s AND user_id=%s", (group_id, uid))
        if not my_membership:
            return jsonify(ok=False, error="Ruxsat yo'q."), 403
        target = fetchone(conn,
            "SELECT role FROM group_members WHERE group_id=%s AND user_id=%s", (group_id, target_id))
        if not target:
            return jsonify(ok=False, error="A'zo topilmadi."), 404
        if target_id == uid:
            if target["role"] == "owner":
                return jsonify(ok=False, error="Guruh egasi guruhni tark eta olmaydi."), 400
            execute(conn, "DELETE FROM group_members WHERE group_id=%s AND user_id=%s", (group_id, uid))
            return jsonify(ok=True, left=True)
        if my_membership["role"] == "owner":
            execute(conn, "DELETE FROM group_members WHERE group_id=%s AND user_id=%s", (group_id, target_id))
            return jsonify(ok=True)
        elif my_membership["role"] == "admin":
            if target["role"] in ("owner", "admin"):
                return jsonify(ok=False, error="Admin boshqa adminni yoki egasini chiqara olmaydi."), 403
            execute(conn, "DELETE FROM group_members WHERE group_id=%s AND user_id=%s", (group_id, target_id))
            return jsonify(ok=True)
        return jsonify(ok=False, error="A'zolarni chiqarish huquqiga ega emassiz."), 403


@app.route("/api/group/<int:group_id>", methods=["DELETE"])
@login_required
def delete_group(group_id):
    uid = session["user_id"]
    with db() as conn:
        my_membership = fetchone(conn,
            "SELECT role FROM group_members WHERE group_id=%s AND user_id=%s", (group_id, uid))
        user_row = fetchone(conn, "SELECT is_admin FROM users WHERE id=%s", (uid,))
        is_site_admin = bool(user_row and user_row["is_admin"])
        if not is_site_admin and (not my_membership or my_membership["role"] != "owner"):
            return jsonify(ok=False, error="Faqat guruh egasi guruhni o'chira oladi."), 403
        execute(conn, "DELETE FROM group_messages WHERE group_id=%s", (group_id,))
        execute(conn, "DELETE FROM group_members WHERE group_id=%s", (group_id,))
        execute(conn, "DELETE FROM chat_groups WHERE id=%s", (group_id,))
    return jsonify(ok=True)


# ── Entry API ──────────────────────────────────────────────────────────��[...]
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


# ── Reminders ──────────────────────────────────────────────────────────��[...]
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


# ── Admin ────────────────────────────────────────────────────────────[...]
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
