"""人岗匹配 HTTP 路由。"""

from flask import Blueprint, jsonify, request

from app.core.security import get_bearer_user_id
from app.domains.match.services import run_match_preview

match_bp = Blueprint("match", __name__, url_prefix="/api/match")


@match_bp.post("/preview")
def match_preview():
    body = request.get_json(silent=True) or {}
    jwt_user_id = get_bearer_user_id()
    data_out, err, status = run_match_preview(body, jwt_user_id)
    if err:
        return jsonify({"ok": False, "message": err}), status
    return jsonify({"ok": True, "data": data_out})
