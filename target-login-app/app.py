"""
目标应用：Web 登录系统（期末项目被测系统）
端口默认 5000；数据库 SQLite 自动初始化。
"""

import secrets
from datetime import datetime, timedelta

from flask import Flask, jsonify, request, session
from werkzeug.exceptions import HTTPException

from models import db, User, PasswordResetToken
from services import (
    validate_username,
    validate_password,
    validate_email,
    hash_password,
    verify_password,
    lock_deadline,
    is_locked,
    MAX_FAILED,
)


def create_app():
    app = Flask(
        __name__,
        static_folder="static",
        template_folder="templates",
    )
    app.config.from_object("config")

    db.init_app(app)

    def ok(message="OK", data=None, code=0):
        return jsonify({"code": code, "message": message, "data": data})

    def err(message, code=400, http_status=400):
        r = jsonify({"code": code, "message": message, "data": None})
        r.status_code = http_status
        return r

    @app.before_request
    def make_session_permanent():
        session.permanent = True

    @app.route("/")
    def index_page():
        from flask import send_from_directory

        return send_from_directory(app.static_folder, "index.html")

    @app.route("/register.html")
    def register_page():
        from flask import send_from_directory

        return send_from_directory(app.static_folder, "register.html")

    @app.route("/login.html")
    def login_page():
        from flask import send_from_directory

        return send_from_directory(app.static_folder, "login.html")

    @app.route("/profile.html")
    def profile_page():
        from flask import send_from_directory

        return send_from_directory(app.static_folder, "profile.html")

    @app.route("/reset.html")
    def reset_page():
        from flask import send_from_directory

        return send_from_directory(app.static_folder, "reset.html")

    @app.post("/api/register")
    def api_register():
        body = request.get_json(silent=True) or {}
        username = (body.get("username") or "").strip()
        password = body.get("password") or ""
        confirm = body.get("confirm_password") or ""
        email = (body.get("email") or "").strip()

        ok_u, msg_u = validate_username(username)
        if not ok_u:
            return err(msg_u, code=1001)
        ok_p, msg_p = validate_password(password)
        if not ok_p:
            return err(msg_p, code=1002)
        if password != confirm:
            return err("两次输入的密码不一致", code=1003)
        ok_e, msg_e = validate_email(email)
        if not ok_e:
            return err(msg_e, code=1004)

        if User.query.filter_by(username=username).first():
            return err("用户名已被占用", code=1005)

        user = User(
            username=username,
            password_hash=hash_password(password),
            email=email,
            failed_attempts=0,
            locked_until=None,
        )
        db.session.add(user)
        db.session.commit()
        return ok("注册成功", {"user_id": user.id})

    @app.post("/api/login")
    def api_login():
        body = request.get_json(silent=True) or {}
        username = (body.get("username") or "").strip()
        password = body.get("password") or ""

        if not username or not password:
            return err("用户名和密码不能为空", code=2001)

        user = User.query.filter_by(username=username).first()
        if user is None:
            return err("用户名或密码错误", code=2002, http_status=401)

        if is_locked(user.locked_until):
            return err("账户已锁定，请30分钟后重试", code=2003, http_status=403)

        if not verify_password(password, user.password_hash):
            user.failed_attempts = (user.failed_attempts or 0) + 1
            if user.failed_attempts >= MAX_FAILED:
                user.locked_until = lock_deadline()
            db.session.commit()
            return err("用户名或密码错误", code=2002, http_status=401)

        user.failed_attempts = 0
        user.locked_until = None
        db.session.commit()

        session["user_id"] = user.id
        return ok("登录成功", {"user_id": user.id, "username": user.username})

    @app.post("/api/logout")
    def api_logout():
        session.clear()
        return ok("已登出")

    @app.get("/api/profile")
    def api_profile():
        uid = session.get("user_id")
        if not uid:
            return err("未登录或会话已失效", code=3001, http_status=401)
        user = User.query.get(uid)
        if not user:
            session.clear()
            return err("用户不存在", code=3002, http_status=401)
        return ok(data=user.to_public_dict())

    @app.post("/api/reset-request")
    def api_reset_request():
        body = request.get_json(silent=True) or {}
        email = (body.get("email") or "").strip()
        ok_e, msg_e = validate_email(email)
        if not ok_e:
            return err(msg_e, code=4001)

        user = User.query.filter_by(email=email).first()
        generic = "若该邮箱已注册，将收到重置说明（本地演示请查看接口返回中的演示字段）"
        if not user:
            return ok(generic, {"demo": "邮箱未注册，无重置令牌"})

        token = secrets.token_hex(32)
        exp = datetime.utcnow() + timedelta(hours=1)
        PasswordResetToken.query.filter_by(user_id=user.id, used=False).update(
            {"used": True}
        )
        db.session.add(
            PasswordResetToken(user_id=user.id, token=token, expires_at=exp, used=False)
        )
        db.session.commit()
        return ok(
            generic,
            {
                "demo_reset_token": token,
                "demo_reset_link": f"/reset.html?token={token}",
                "expires_at": exp.isoformat() + "Z",
            },
        )

    @app.post("/api/reset")
    def api_reset():
        body = request.get_json(silent=True) or {}
        token = (body.get("token") or "").strip()
        new_pw = body.get("new_password") or ""
        confirm = body.get("confirm_password") or ""
        if not token:
            return err("缺少重置令牌", code=5001)
        ok_p, msg_p = validate_password(new_pw)
        if not ok_p:
            return err(msg_p, code=5002)
        if new_pw != confirm:
            return err("两次输入的密码不一致", code=5003)

        rec = PasswordResetToken.query.filter_by(token=token, used=False).first()
        if not rec or datetime.utcnow() > rec.expires_at:
            return err("重置令牌无效或已过期", code=5004, http_status=400)

        user = User.query.get(rec.user_id)
        if not user:
            return err("用户不存在", code=5005)

        user.password_hash = hash_password(new_pw)
        rec.used = True
        db.session.commit()
        return ok("密码已重置，请使用新密码登录")

    @app.errorhandler(Exception)
    def handle_unexpected(e):
        if isinstance(e, HTTPException):
            return e
        app.logger.exception("Unhandled: %s", e)
        return err("服务器内部错误", code=9999, http_status=500)

    return app


app = create_app()


def init_db():
    with app.app_context():
        db.create_all()


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000, debug=True)
