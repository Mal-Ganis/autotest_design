# 目标应用：Web 登录系统

期末项目中的**被测系统**（非 AutoTestDesign 工具）。功能包含注册、登录（Cookie 会话）、连续失败 5 次锁定 30 分钟、密码重置（演示用 token）、统一 JSON 响应 `{ code, message, data }`。

## 环境

- Python 3.9+
- 依赖见 `requirements.txt`

## 启动（验收：本地 5000 端口）

```bash
cd autotest_design/target-login-app
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

浏览器访问：<http://127.0.0.1:5000/>

首次启动会自动创建 SQLite 数据库 `app.db` 并建表。

## API 摘要

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/register` | 注册 |
| POST | `/api/login` | 登录（设置会话） |
| POST | `/api/logout` | 登出 |
| GET | `/api/profile` | 需登录，返回公开用户信息（不含密码） |
| POST | `/api/reset-request` | 请求重置；演示环境在 JSON 中返回 `demo_reset_token` |
| POST | `/api/reset` | 使用 token 设置新密码 |

生产环境请设置环境变量 `LOGIN_APP_SECRET` 作为 Flask `SECRET_KEY`。
