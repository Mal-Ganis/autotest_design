"""
tests_target — 消费 AutoTestDesign 导出的 09_export_cases.json，
对目标应用 target-login-app 执行至少一条自动化验收。

运行前请确保目标应用已启动（默认 http://127.0.0.1:5000）：
  cd target-login-app && python app.py

执行：
  pytest tests_target/ -v
  pytest tests_target/ -v --export-json data/work/09_export_cases.json
"""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path

import pytest
import requests

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_EXPORT = ROOT / "data" / "work" / "09_export_cases.json"
MOCK_EXPORT = ROOT / "data" / "mock" / "09_export_cases.json"
BASE_URL = os.environ.get("TARGET_APP_URL", "http://127.0.0.1:5000")


def _load_export(path: Path) -> dict:
    if not path.is_file():
        pytest.skip(f"导出文件不存在：{path}（请先运行 launcher.py 或指定 --export-json）")
    with path.open(encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="session")
def export_data(request) -> dict:
    custom = request.config.getoption("export_json")
    path = Path(custom) if custom else DEFAULT_EXPORT
    if not path.is_file() and MOCK_EXPORT.is_file():
        path = MOCK_EXPORT
    return _load_export(path)


@pytest.fixture(scope="session")
def app_available() -> None:
    try:
        r = requests.get(f"{BASE_URL}/", timeout=2)
        if r.status_code >= 500:
            pytest.skip(f"目标应用不可用：{BASE_URL} 返回 {r.status_code}")
    except requests.RequestException as ex:
        pytest.skip(f"目标应用未启动（{BASE_URL}）：{ex}")


def test_export_has_cases_and_suites(export_data: dict) -> None:
    assert export_data.get("pipeline_stage") == "09_export"
    cases = export_data.get("cases") or []
    suites = export_data.get("suites") or []
    risk = export_data.get("risk") or {}
    assert len(cases) >= 1, "导出应至少包含一条用例"
    assert len(suites) >= 1, "导出应至少包含一个套件"
    assert (risk.get("requirements") or []), "导出应包含 risk.requirements"
    assert export_data.get("cases")[0].get("case_id"), "用例应有 case_id"


def test_export_risk_fields(export_data: dict) -> None:
    for row in (export_data.get("risk") or {}).get("requirements") or []:
        assert row.get("req_id")
        assert row.get("test_priority") in ("High", "Medium", "Low", "")


def test_login_username_length_from_export(export_data: dict, app_available: None) -> None:
    """消费导出 JSON：依据 FR-LOGIN-001 相关用例，验证用户名长度规则。"""
    cases = export_data.get("cases") or []
    login_cases = [
        c for c in cases
        if "FR-LOGIN-001" in (c.get("linked_req_ids") or "")
        or "用户名" in (c.get("title") or "")
    ]
    assert login_cases, "导出中应存在与用户名/FR-LOGIN-001 相关的用例"

    suffix = uuid.uuid4().hex[:6]
    valid_user = f"usr{suffix}"[:12]
    assert 3 <= len(valid_user) <= 20

    reg = requests.post(
        f"{BASE_URL}/api/register",
        json={
            "username": valid_user,
            "password": "Abcdef12",
            "confirm_password": "Abcdef12",
            "email": f"{valid_user}@example.com",
        },
        timeout=5,
    )
    assert reg.status_code == 200
    assert reg.json().get("code") == 0

    short_user = "ab"
    bad = requests.post(
        f"{BASE_URL}/api/register",
        json={
            "username": short_user,
            "password": "Abcdef12",
            "confirm_password": "Abcdef12",
            "email": "short@example.com",
        },
        timeout=5,
    )
    assert bad.status_code == 200
    body = bad.json()
    assert body.get("code") != 0
    assert "用户名" in (body.get("message") or "")


def test_login_api_success(export_data: dict, app_available: None) -> None:
    """基础冒烟：注册后登录成功，对应导出套件中 High/Medium 优先级场景。"""
    suffix = uuid.uuid4().hex[:8]
    user = f"test{suffix}"[:16]
    password = "TestPass1"

    requests.post(
        f"{BASE_URL}/api/register",
        json={
            "username": user,
            "password": password,
            "confirm_password": password,
            "email": f"{user}@test.local",
        },
        timeout=5,
    ).raise_for_status()

    session = requests.Session()
    login = session.post(
        f"{BASE_URL}/api/login",
        json={"username": user, "password": password},
        timeout=5,
    )
    assert login.status_code == 200
    assert login.json().get("code") == 0

    profile = session.get(f"{BASE_URL}/api/profile", timeout=5)
    assert profile.status_code == 200
    assert profile.json().get("data", {}).get("username") == user
