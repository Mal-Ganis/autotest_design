"""tests_target 公共配置。"""

from __future__ import annotations


def pytest_addoption(parser):
    parser.addoption(
        "--export-json",
        action="store",
        default=None,
        help="指定 09_export_cases.json 路径（默认 data/work/09_export_cases.json）",
    )
