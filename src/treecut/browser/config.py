"""XHS Work Browser V0.1 — 配置（§51：configs/xhs_work_browser.yaml 或现有配置体系等价文件）。

采用现有 TreeCut 数据目录约定：运行时配置位于
  {data_root}/config/xhs_work_browser.yaml
仓库内 configs/xhs_work_browser.yaml 为默认模板（不含任何敏感信息）。

安全纪律：配置只含导航所需静态 URL（origin 级，无 query/signed），
不保存 cookie / authorization / xsec_token / session / 凭证。
"""
from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from treecut.platform.paths import RuntimePaths

DEFAULT_CONFIG_PATH = "config/xhs_work_browser.yaml"

DEFAULT_SESSION_MARKERS = {
    "creator": {
        "login": ["扫码登录", "登录后查看", "请登录", "登录小红书"],
        "valid": ["发布笔记", "创作中心", "笔记管理", "数据中心", "工作台",
                  "我的笔记", "数据概览", "内容管理"],
        "expired": ["登录已过期", "请重新登录", "登录状态已失效", "session expired"],
    },
    "spotlight": {
        "login": ["扫码登录", "请登录"],
        "valid": ["推广", "广告管理", "创建广告", "数据概览", "计划", "单元",
                  "创意", "消耗", "展现", "点击", "转化", "报表", "账户"],
        "expired": ["登录已过期", "请重新登录", "登录状态已失效", "session expired"],
    },
    "frontend": {
        "login": ["扫码登录", "立即登录", "登录后可见"],
        "valid": ["首页", "发现", "关注", "我的", "推荐", "视频", "笔记"],
        "expired": ["登录已过期", "请重新登录", "登录状态已失效", "session expired"],
    },
}


@dataclass
class XhsWorkBrowserConfig:
    workspace_id: str = "B007"
    # 空 → data_root/browser_profiles（见 workspace_manager）
    profile_root: str = ""
    # TreeCut Local Service（§17 localhost HTTP / health）
    treecut_local_url: str = "http://127.0.0.1:28888"
    treecut_health_timeout_seconds: float = 3.0
    # Browser Runtime（§2）：优先现有 Chromium/Edge persistent context
    browser_channel: str = "msedge"
    headless: bool = False
    # 固定窗口：3 Fixed Functional Tabs（Creator / Spotlight / Frontend）（§13-16）
    expected_tab_count: int = 3
    allow_temporary_popup: int = 1
    # 统一 Retry Policy（§22）
    retry_max_attempts: int = 3
    retry_delay_seconds: float = 2.0
    # 导航目标：仅 origin 级静态 URL，无 query（安全纪律）
    creator_home_url: str = "https://creator.xiaohongshu.com/"
    spotlight_home_url: str = "https://ad.xiaohongshu.com/"
    frontend_home_url: str = "https://www.xiaohongshu.com/"
    # Session 判定 marker（§11：页面能打开 ≠ SESSION_VALID；三站分别判定）
    session_markers: dict = field(
        default_factory=lambda: {k: dict(v) for k, v in DEFAULT_SESSION_MARKERS.items()}
    )

    def validate(self) -> None:
        if not self.workspace_id or not self.workspace_id.strip():
            raise ValueError("workspace_id 不能为空")
        if self.expected_tab_count != 3:
            raise ValueError("V0.1.1 固定 3 个功能 Tab（expected_tab_count=3）")
        if not (0 <= self.allow_temporary_popup <= 2):
            raise ValueError("allow_temporary_popup 必须在 0–2 之间")
        if not (1 <= self.retry_max_attempts <= 5):
            raise ValueError("retry_max_attempts 必须在 1–5 之间")
        if not self.treecut_local_url.startswith("http"):
            raise ValueError("treecut_local_url 必须是 http(s) URL")
        for kind in ("creator", "spotlight", "frontend"):
            if kind not in self.session_markers:
                raise ValueError(f"session_markers 缺少 {kind}")


def _deep_merge(default: dict, override: dict) -> dict:
    merged = dict(default)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def config_path(paths: RuntimePaths | None = None) -> Path:
    paths = paths or RuntimePaths.discover()
    return paths.data_root / DEFAULT_CONFIG_PATH


def load_config(paths: RuntimePaths | None = None) -> XhsWorkBrowserConfig:
    """加载运行时配置；不存在则写入默认配置。未知字段丢弃，值做校验。"""
    path = config_path(paths)
    raw: dict = {}
    if path.is_file():
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            if not isinstance(data, dict):
                raise ValueError("配置必须是 YAML 映射")
            raw = data
        except (OSError, yaml.YAMLError, ValueError):
            raw = {}
    defaults = dataclasses.asdict(XhsWorkBrowserConfig())
    merged = _deep_merge(defaults, raw)
    allowed = set(XhsWorkBrowserConfig.__dataclass_fields__)
    config = XhsWorkBrowserConfig(**{k: v for k, v in merged.items() if k in allowed})
    config.validate()
    if raw != merged or not path.is_file():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            yaml.safe_dump(merged, allow_unicode=True, sort_keys=False), encoding="utf-8"
        )
    return config
