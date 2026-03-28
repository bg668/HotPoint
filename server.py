#!/usr/bin/env python3
import hashlib
import hmac
import json
import secrets
import sqlite3
import subprocess
import urllib.parse
import urllib.request
from datetime import datetime
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DB = ROOT / "data.db"
VENV_PY = Path.home() / ".agent-reach-venv/bin/python"

# 简单内存会话（MVP）
SESSIONS = {}
SESSION_COOKIE = "session_id"


def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def db_conn():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn


def hash_password(password, salt=None):
    if salt is None:
        salt = secrets.token_hex(16)
    pwd_hash = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 120000).hex()
    return f"{salt}${pwd_hash}"


def verify_password(password, stored):
    if not stored or "$" not in stored:
        return False
    salt, old_hash = stored.split("$", 1)
    new_hash = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 120000).hex()
    return hmac.compare_digest(old_hash, new_hash)


def init_db():
    conn = db_conn()
    c = conn.cursor()
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS sources (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          name TEXT UNIQUE,
          type TEXT,
          enabled INTEGER DEFAULT 1,
          last_status TEXT DEFAULT 'idle',
          last_run_at TEXT
        )
        """
    )
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS news (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          title TEXT,
          summary TEXT,
          url TEXT,
          source TEXT,
          published_at TEXT,
          created_at TEXT,
          favorite INTEGER DEFAULT 0,
          UNIQUE(title, source)
        )
        """
    )
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS logs (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          created_at TEXT,
          source TEXT,
          action TEXT,
          result TEXT,
          code INTEGER,
          summary TEXT
        )
        """
    )
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          username TEXT UNIQUE NOT NULL,
          password_hash TEXT NOT NULL,
          role TEXT NOT NULL DEFAULT 'user',
          invite_code_used TEXT,
          created_at TEXT NOT NULL
        )
        """
    )
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS invite_codes (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          code TEXT UNIQUE NOT NULL,
          enabled INTEGER NOT NULL DEFAULT 1,
          created_at TEXT NOT NULL
        )
        """
    )

    seeds = [
        ("微信公众号", "api"),
        ("V2EX", "web"),
        ("Reddit", "web"),
    ]
    for name, typ in seeds:
        c.execute("INSERT OR IGNORE INTO sources(name, type) VALUES (?, ?)", (name, typ))

    # 默认管理员: bg / dd0131uu
    c.execute("SELECT id FROM users WHERE username='bg'")
    if not c.fetchone():
        c.execute(
            "INSERT INTO users(username,password_hash,role,created_at) VALUES(?,?,?,?)",
            ("bg", hash_password("dd0131uu"), "admin", now_str()),
        )

    # 默认邀请码（可在平台管理页查看）
    c.execute(
        "INSERT OR IGNORE INTO invite_codes(code,enabled,created_at) VALUES(?,?,?)",
        ("AIHOT2026", 1, now_str()),
    )

    conn.commit()
    conn.close()


def add_log(source, action, result, code, summary):
    conn = db_conn()
    conn.execute(
        "INSERT INTO logs(created_at,source,action,result,code,summary) VALUES(?,?,?,?,?,?)",
        (now_str(), source, action, result, code, summary),
    )
    conn.commit()
    conn.close()


def update_source(name, status):
    conn = db_conn()
    conn.execute(
        "UPDATE sources SET last_status=?, last_run_at=? WHERE name=?",
        (status, now_str(), name),
    )
    conn.commit()
    conn.close()


def upsert_news(items):
    conn = db_conn()
    c = conn.cursor()
    inserted = 0
    for i in items:
        try:
            c.execute(
                """
                INSERT INTO news(title, summary, url, source, published_at, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    i.get("title", ""),
                    i.get("summary", ""),
                    i.get("url", ""),
                    i.get("source", ""),
                    i.get("published_at", ""),
                    now_str(),
                ),
            )
            inserted += 1
        except sqlite3.IntegrityError:
            pass
    conn.commit()
    conn.close()
    return inserted


def fetch_wechat(query="agent", limit=5):
    if not VENV_PY.exists():
        raise RuntimeError("~/.agent-reach-venv/bin/python 不存在")
    py = f"""
import asyncio, json
from miku_ai import get_wexin_article
async def main():
    items = await get_wexin_article({query!r}, {int(limit)})
    out=[]
    for a in items:
        out.append({{
            'title': a.get('title',''),
            'summary': a.get('snippet','')[:180],
            'url': a.get('url',''),
            'source': '微信公众号',
            'published_at': a.get('date','')
        }})
    print(json.dumps(out, ensure_ascii=False))
asyncio.run(main())
"""
    res = subprocess.run([str(VENV_PY), "-c", py], capture_output=True, text=True, timeout=40)
    if res.returncode != 0:
        raise RuntimeError(res.stderr.strip() or "wechat fetch failed")
    return json.loads(res.stdout.strip() or "[]")


def fetch_v2ex(limit=5):
    url = "https://www.v2ex.com/api/topics/hot.json"
    req = urllib.request.Request(url, headers={"User-Agent": "aihot-monitor/1.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        data = json.loads(r.read().decode("utf-8"))
    out = []
    for x in data[:limit]:
        out.append(
            {
                "title": x.get("title", ""),
                "summary": (x.get("content", "") or "")[:180],
                "url": x.get("url", ""),
                "source": "V2EX",
                "published_at": str(x.get("created", "")),
            }
        )
    return out


def fetch_reddit(query="ai agent", limit=5):
    q = urllib.parse.quote(query)
    url = f"https://www.reddit.com/search.json?q={q}&sort=new&limit={int(limit)}"
    req = urllib.request.Request(url, headers={"User-Agent": "aihot-monitor/1.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        data = json.loads(r.read().decode("utf-8"))
    out = []
    for c in data.get("data", {}).get("children", []):
        d = c.get("data", {})
        out.append(
            {
                "title": d.get("title", ""),
                "summary": (d.get("selftext", "") or "")[:180],
                "url": f"https://reddit.com{d.get('permalink', '')}",
                "source": "Reddit",
                "published_at": str(d.get("created_utc", "")),
            }
        )
    return out


def run_collection(query="agent", limit=5):
    all_items = []

    for name, fn, args in [
        ("微信公众号", fetch_wechat, {"query": query, "limit": limit}),
        ("V2EX", fetch_v2ex, {"limit": limit}),
        ("Reddit", fetch_reddit, {"query": query, "limit": limit}),
    ]:
        try:
            items = fn(**args)
            n = upsert_news(items)
            update_source(name, "ok")
            add_log(name, "抓取", "成功", 200, f"获取 {len(items)} 条，入库 {n} 条")
            all_items.extend(items)
        except Exception as e:
            update_source(name, "err")
            add_log(name, "抓取", "失败", 500, str(e)[:180])

    return all_items


def query_all():
    conn = db_conn()
    sources = [dict(r) for r in conn.execute("SELECT * FROM sources ORDER BY id DESC")]
    logs = [dict(r) for r in conn.execute("SELECT * FROM logs ORDER BY id DESC LIMIT 200")]
    news = [dict(r) for r in conn.execute("SELECT * FROM news ORDER BY id DESC LIMIT 300")]
    conn.close()
    return {"sources": sources, "logs": logs, "news": news}


def list_users():
    conn = db_conn()
    rows = [
        dict(r)
        for r in conn.execute(
            "SELECT id, username, role, invite_code_used, created_at FROM users ORDER BY id DESC"
        )
    ]
    conn.close()
    return rows


def list_invite_codes():
    conn = db_conn()
    rows = [dict(r) for r in conn.execute("SELECT id, code, enabled, created_at FROM invite_codes ORDER BY id DESC")]
    conn.close()
    return rows


def check_invite_code(code):
    conn = db_conn()
    row = conn.execute("SELECT id FROM invite_codes WHERE code=? AND enabled=1", (code,)).fetchone()
    conn.close()
    return bool(row)


class Handler(BaseHTTPRequestHandler):
    def _json(self, obj, code=200, headers=None):
        data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        if headers:
            for k, v in headers.items():
                self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)

    def _serve_file(self, path):
        fp = ROOT / path
        if not fp.exists() or not fp.is_file():
            self.send_error(404)
            return
        ctype = "text/plain"
        if path.endswith(".html"):
            ctype = "text/html; charset=utf-8"
        elif path.endswith(".css"):
            ctype = "text/css; charset=utf-8"
        elif path.endswith(".js"):
            ctype = "application/javascript; charset=utf-8"
        data = fp.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _body(self):
        raw = self.rfile.read(int(self.headers.get("Content-Length", "0") or 0) or 0)
        if not raw:
            return {}
        return json.loads(raw.decode("utf-8") or "{}")

    def _cookies(self):
        cookie_header = self.headers.get("Cookie", "")
        c = SimpleCookie()
        c.load(cookie_header)
        return c

    def _current_user(self):
        cookies = self._cookies()
        sid = cookies.get(SESSION_COOKIE)
        if not sid:
            return None
        session = SESSIONS.get(sid.value)
        if not session:
            return None
        return session

    def _require_login(self):
        user = self._current_user()
        if not user:
            self._json({"ok": False, "error": "unauthorized"}, 401)
            return None
        return user

    def _require_admin(self):
        user = self._require_login()
        if not user:
            return None
        if user.get("role") != "admin":
            self._json({"ok": False, "error": "forbidden"}, 403)
            return None
        return user

    def do_GET(self):
        if self.path in ["/", "/index.html"]:
            return self._serve_file("index.html")
        if self.path == "/login":
            return self._serve_file("login.html")
        if self.path == "/register":
            return self._serve_file("register.html")
        if self.path == "/styles.css":
            return self._serve_file("styles.css")
        if self.path == "/app.js":
            return self._serve_file("app.js")
        if self.path == "/auth.js":
            return self._serve_file("auth.js")

        if self.path.startswith("/api/me"):
            user = self._current_user()
            if not user:
                return self._json({"ok": False, "error": "unauthorized"}, 401)
            return self._json({"ok": True, "user": user})

        if self.path.startswith("/api/state"):
            if not self._require_login():
                return
            return self._json(query_all())

        if self.path.startswith("/api/admin/users"):
            if not self._require_admin():
                return
            return self._json({"ok": True, "users": list_users()})

        if self.path.startswith("/api/admin/invite-codes"):
            if not self._require_admin():
                return
            return self._json({"ok": True, "invite_codes": list_invite_codes()})

        self.send_error(404)

    def do_POST(self):
        if self.path.startswith("/api/login"):
            try:
                body = self._body()
                username = (body.get("username") or "").strip()
                password = body.get("password") or ""
                if not username or not password:
                    return self._json({"ok": False, "error": "用户名和密码不能为空"}, 400)

                conn = db_conn()
                row = conn.execute(
                    "SELECT id, username, password_hash, role FROM users WHERE username=?", (username,)
                ).fetchone()
                conn.close()

                if not row or not verify_password(password, row["password_hash"]):
                    return self._json({"ok": False, "error": "用户名或密码错误"}, 401)

                sid = secrets.token_urlsafe(24)
                user = {"id": row["id"], "username": row["username"], "role": row["role"]}
                SESSIONS[sid] = user
                return self._json(
                    {"ok": True, "user": user},
                    headers={"Set-Cookie": f"{SESSION_COOKIE}={sid}; HttpOnly; Path=/; SameSite=Lax"},
                )
            except Exception as e:
                return self._json({"ok": False, "error": str(e)}, 500)

        if self.path.startswith("/api/logout"):
            cookies = self._cookies()
            sid = cookies.get(SESSION_COOKIE)
            if sid and sid.value in SESSIONS:
                del SESSIONS[sid.value]
            return self._json(
                {"ok": True},
                headers={"Set-Cookie": f"{SESSION_COOKIE}=; Max-Age=0; Path=/; SameSite=Lax"},
            )

        if self.path.startswith("/api/register"):
            try:
                body = self._body()
                username = (body.get("username") or "").strip()
                password = body.get("password") or ""
                invite_code = (body.get("invite_code") or "").strip()
                if not username or not password or not invite_code:
                    return self._json({"ok": False, "error": "请完整填写用户名、密码、邀请码"}, 400)
                if len(username) < 2 or len(username) > 32:
                    return self._json({"ok": False, "error": "用户名长度需在2-32之间"}, 400)
                if len(password) < 6:
                    return self._json({"ok": False, "error": "密码至少6位"}, 400)
                if not check_invite_code(invite_code):
                    return self._json({"ok": False, "error": "邀请码无效"}, 400)

                conn = db_conn()
                conn.execute(
                    "INSERT INTO users(username,password_hash,role,invite_code_used,created_at) VALUES(?,?,?,?,?)",
                    (username, hash_password(password), "user", invite_code, now_str()),
                )
                conn.commit()
                conn.close()
                return self._json({"ok": True})
            except sqlite3.IntegrityError:
                return self._json({"ok": False, "error": "用户名已存在"}, 400)
            except Exception as e:
                return self._json({"ok": False, "error": str(e)}, 500)

        if self.path.startswith("/api/collect"):
            if not self._require_login():
                return
            try:
                body = self._body()
                query = (body.get("query") or "agent").strip()[:80]
                limit = int(body.get("limit") or 5)
                limit = max(1, min(20, limit))
                run_collection(query=query, limit=limit)
                return self._json({"ok": True, "state": query_all()})
            except Exception as e:
                return self._json({"ok": False, "error": str(e)}, 500)

        self.send_error(404)


if __name__ == "__main__":
    init_db()
    server = ThreadingHTTPServer(("127.0.0.1", 8090), Handler)
    print("Server running: http://127.0.0.1:8090")
    server.serve_forever()
