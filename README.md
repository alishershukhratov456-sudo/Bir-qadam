# Bir Qadam — 30 kunlik interaktiv kundalik

A 30-day personal growth journal with chat, reminders, progress tracking, and an admin panel. Built with Flask + PostgreSQL.

---

## Deploy to Railway (recommended)

### 1 — Push to GitHub

```bash
git add .
git commit -m "ready for railway"
git remote add origin https://github.com/YOUR_USERNAME/bir-qadam.git
git push -u origin main
```

### 2 — Create a Railway project

1. Go to [railway.app](https://railway.app) → **New Project**
2. Choose **Deploy from GitHub repo** → select your repo
3. Railway will detect the `railway.toml` and start building automatically

### 3 — Add a PostgreSQL database

1. In your Railway project, click **+ New** → **Database** → **PostgreSQL**
2. Railway automatically creates a `DATABASE_URL` environment variable and links it to your web service — you don't need to copy anything manually

### 4 — Set environment variables

In your Railway web service → **Variables** tab, add:

| Variable | Value |
|---|---|
| `SECRET_KEY` | Any long random string — generate with `python -c "import secrets; print(secrets.token_hex(32))"` |
| `ADMIN_EMAIL` | The email you'll sign up with — gets admin rights on first startup |

`DATABASE_URL` is set automatically by Railway — do not add it manually.

### 5 — Deploy & sign up

After deploy, open your Railway URL, sign up with the `ADMIN_EMAIL` email, and you'll have admin access immediately.

---

## Migrate your existing accounts from SQLite

If you have accounts in a local `journal.db` that you want to move to the live PostgreSQL database, you can use the built-in upload route:

1. Make sure `UPLOAD_TOKEN` is set in Railway Variables (any password you choose)
2. Go to `https://your-app.railway.app/upload-db`
3. Enter your token and upload the `journal.db` file — the app will migrate all data automatically
4. After uploading, **remove `UPLOAD_TOKEN`** from Railway Variables to close the route

---

## Local development

```bash
# 1. Clone
git clone https://github.com/YOUR_USERNAME/bir-qadam.git
cd bir-qadam

# 2. Virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1      # Windows
# source .venv/bin/activate        # macOS/Linux

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set up local PostgreSQL
# Install PostgreSQL, then create a database:
# psql -U postgres -c "CREATE DATABASE bir_qadam;"

# 5. Configure environment
copy .env.example .env
# Edit .env: set SECRET_KEY and DATABASE_URL to your local postgres

# 6. Run
python app.py
```

For local dev without PostgreSQL, you can temporarily revert to SQLite by swapping the db() function — but Railway/production always uses PostgreSQL.

---

## Project structure

```
├── app.py                 # Flask app + all routes (PostgreSQL)
├── gunicorn.conf.py       # Gunicorn config
├── railway.toml           # Railway deploy config
├── requirements.txt       # Python dependencies
├── .env.example           # Environment variable template
├── static/
│   ├── style.css
│   ├── app.js
│   ├── reminders.js
│   ├── theme.js
│   └── photo1-7.png
└── templates/
    ├── index.html
    ├── auth.html
    ├── dashboard.html
    ├── chat.html
    ├── account_settings.html
    ├── admin.html
    └── admin_user.html
```
