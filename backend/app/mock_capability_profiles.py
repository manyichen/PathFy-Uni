"""
虚构能力画像（八维与岗位 cap_req_* 同刻度 0–100，便于与人岗匹配粗算联调）。

字段名复用 cap_req_* / cap_conf_* 仅表示「数值形状与岗位接口一致」；
语义为学生侧供给分，正式模块可改为 cap_sup_* 等命名。
"""

from __future__ import annotations

import os
from typing import Any, Dict, List

from flask import Blueprint, jsonify

from .jobs import CONF_KEYS, DIM_KEYS

mock_profile_bp = Blueprint("mock_profile", __name__, url_prefix="/api/profile")


def _mock_api_enabled() -> bool:
    """
    显式 1/true 开启；显式 0/false 关闭。
    未配置时：FLASK_ENV 为 development/dev 则默认开启（便于本地联调，无需再抄一项到 .env）。
    """
    raw = os.getenv("ENABLE_MOCK_PROFILE_API", "").strip().lower()
    if raw in ("1", "true", "yes", "on"):
        return True
    if raw in ("0", "false", "no", "off"):
        return False
    env = os.getenv("FLASK_ENV", "").strip().lower()
    return env in ("development", "dev")


def _wrap_scores(raw: Dict[str, float]) -> Dict[str, float]:
    out: Dict[str, float] = {}
    for k in DIM_KEYS:
        out[k] = round(float(raw.get(k, 0.0)), 2)
    return out


def _wrap_conf(raw: Dict[str, float]) -> Dict[str, float]:
    out: Dict[str, float] = {}
    for k in CONF_KEYS:
        v = float(raw.get(k, 0.6))
        out[k] = round(min(1.0, max(0.0, v)), 4)
    return out


def _serialize_profile(profile: Dict[str, Any]) -> Dict[str, Any]:
    scores = _wrap_scores(profile["scores"])
    confidences = _wrap_conf(profile["confidences"])
    score_avg = round(sum(scores.values()) / len(DIM_KEYS), 2) if DIM_KEYS else 0.0
    conf_avg = round((sum(confidences.values()) / len(CONF_KEYS)) * 100, 2) if CONF_KEYS else 0.0
    base = {k: v for k, v in profile.items() if k not in ("scores", "confidences")}
    return {
        **base,
        "vector_kind": "student_supply",
        "scores": scores,
        "confidences": confidences,
        "score_avg": score_avg,
        "conf_avg": conf_avg,
    }


# 与 Neo4j 岗位八维粗排联调用的几条虚构人设（非真实个人数据）
_RAW_PROFILES: Dict[str, Dict[str, Any]] = {
    "fake_cs_intern": {
        "id": "fake_cs_intern",
        "display_name": "虚构：陈小研（应届·偏后端工程）",
        "education": "计算机科学与技术 · 本科 · 2026 届（测试数据）",
        "city_pref": "杭州 / 上海",
        "skills_hint": ["Python", "MySQL", "Redis", "Git", "基础 Vue"],
        "resume_excerpt": "两段 Web 后端实习，参与订单接口与监控脚本；校实验室做过推荐系统课程设计。（纯属测试文案）",
        "scores": {
            "cap_req_theory": 58,
            "cap_req_cross": 52,
            "cap_req_practice": 78,
            "cap_req_digital": 82,
            "cap_req_innovation": 48,
            "cap_req_teamwork": 62,
            "cap_req_social": 38,
            "cap_req_growth": 70,
        },
        "confidences": {
            "cap_conf_theory": 0.70,
            "cap_conf_cross": 0.62,
            "cap_conf_practice": 0.82,
            "cap_conf_digital": 0.85,
            "cap_conf_innovation": 0.55,
            "cap_conf_teamwork": 0.68,
            "cap_conf_social": 0.50,
            "cap_conf_growth": 0.72,
        },
    },
    "fake_product_generalist": {
        "id": "fake_product_generalist",
        "display_name": "虚构：李可维（偏产品 / 交叉背景）",
        "education": "信息管理与信息系统 · 本科（测试数据）",
        "city_pref": "北京",
        "skills_hint": ["需求文档", "SQL", "Figma", "数据分析入门", "跨部门沟通"],
        "resume_excerpt": "学生社团外联部长，两段产品运营实习；独立负责过小程序活动页需求评审。（纯属测试文案）",
        "scores": {
            "cap_req_theory": 50,
            "cap_req_cross": 72,
            "cap_req_practice": 60,
            "cap_req_digital": 58,
            "cap_req_innovation": 65,
            "cap_req_teamwork": 80,
            "cap_req_social": 74,
            "cap_req_growth": 76,
        },
        "confidences": {
            "cap_conf_theory": 0.58,
            "cap_conf_cross": 0.74,
            "cap_conf_practice": 0.66,
            "cap_conf_digital": 0.60,
            "cap_conf_innovation": 0.70,
            "cap_conf_teamwork": 0.80,
            "cap_conf_social": 0.78,
            "cap_conf_growth": 0.75,
        },
    },
    "fake_sales_marketing": {
        "id": "fake_sales_marketing",
        "display_name": "虚构：王拓（偏市场与客户侧）",
        "education": "市场营销 · 本科（测试数据）",
        "city_pref": "广州",
        "skills_hint": ["客户拜访", "活动策划", "PPT", "新媒体运营"],
        "resume_excerpt": "校园推广项目负责人，实习做过渠道拓展与复盘；几乎无技术项目经历。（纯属测试文案）",
        "scores": {
            "cap_req_theory": 35,
            "cap_req_cross": 55,
            "cap_req_practice": 62,
            "cap_req_digital": 42,
            "cap_req_innovation": 52,
            "cap_req_teamwork": 78,
            "cap_req_social": 85,
            "cap_req_growth": 68,
        },
        "confidences": {
            "cap_conf_theory": 0.55,
            "cap_conf_cross": 0.62,
            "cap_conf_practice": 0.70,
            "cap_conf_digital": 0.52,
            "cap_conf_innovation": 0.60,
            "cap_conf_teamwork": 0.78,
            "cap_conf_social": 0.82,
            "cap_conf_growth": 0.65,
        },
    },
}


def get_mock_profile_raw(profile_id: str) -> Dict[str, Any] | None:
    """返回未序列化的虚构画像 dict，供人岗粗排等模块读取（与 ENABLE_MOCK_PROFILE_API 无关）。"""
    return _RAW_PROFILES.get(profile_id)


def _disabled_response():
    return (
        jsonify(
            {
                "ok": False,
                "message": "虚构画像接口已关闭（ENABLE_MOCK_PROFILE_API=0）。开发环境可删除该项或设为 1，或设置 FLASK_ENV=development。",
            }
        ),
        403,
    )


@mock_profile_bp.get("/mocks")
def list_mock_profiles():
    if not _mock_api_enabled():
        return _disabled_response()
    items: List[Dict[str, Any]] = []
    for key in _RAW_PROFILES:
        p = _serialize_profile(_RAW_PROFILES[key])
        items.append(
            {
                "id": p["id"],
                "display_name": p["display_name"],
                "education": p.get("education"),
                "city_pref": p.get("city_pref"),
                "score_avg": p["score_avg"],
                "conf_avg": p["conf_avg"],
            }
        )
    return jsonify({"ok": True, "data": {"profiles": items, "note": "测试用虚构数据，勿当真实简历"}})


@mock_profile_bp.get("/mocks/<profile_id>")
def get_mock_profile(profile_id: str):
    if not _mock_api_enabled():
        return _disabled_response()
    raw = _RAW_PROFILES.get(profile_id)
    if not raw:
        return jsonify({"ok": False, "message": f"未知 profile_id: {profile_id}"}), 404
    return jsonify({"ok": True, "data": _serialize_profile(raw)})
