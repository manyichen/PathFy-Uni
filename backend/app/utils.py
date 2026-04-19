import os
import requests
import json
from typing import Dict, Tuple

from aip import AipOcr
from pyecharts.charts import Radar
from pyecharts import options as opts
import fitz

from app.config import Config
from app.jobs import CONF_KEYS, DIM_KEYS

# 百度 OCR：未配置 OCR_* 时仍可启动应用，仅在调用 ocr_image 时初始化客户端
_ocr_client = None


def _get_ocr_client():
    global _ocr_client
    if _ocr_client is None:
        app_id = str(Config.OCR_APP_ID or "").strip()
        api_key = str(Config.OCR_API_KEY or "").strip()
        secret = str(Config.OCR_SECRET_KEY or "").strip()
        if not (app_id and api_key and secret):
            raise RuntimeError("未配置 OCR_APP_ID / OCR_API_KEY / OCR_SECRET_KEY，无法使用百度 OCR")
        _ocr_client = AipOcr(app_id, api_key, secret)
    return _ocr_client


def ocr_image(file_path):
    with open(file_path, "rb") as f:
        img_data = f.read()
    result = _get_ocr_client().basicGeneral(img_data)
    words = result.get("words_result", [])
    return "\n".join([w["words"] for w in words])

def pdf_to_image(pdf_path):
    output_dir = os.path.join(os.path.dirname(pdf_path), "pdf_images")
    os.makedirs(output_dir, exist_ok=True)
    doc = fitz.open(pdf_path)
    page = doc.load_page(0)
    pix = page.get_pixmap()
    img_name = os.path.basename(pdf_path).replace(".pdf", ".png")
    img_path = os.path.join(output_dir, img_name)
    pix.save(img_path)
    return img_path

def _default_scores() -> Dict[str, int]:
    return {k: 60 for k in DIM_KEYS}


def _default_confidences() -> Dict[str, float]:
    return {k: 0.55 for k in CONF_KEYS}


def _clamp_score(v) -> int:
    try:
        x = int(round(float(v)))
    except (TypeError, ValueError):
        return 60
    return max(0, min(100, x))


def _clamp_conf(v) -> float:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return 0.55
    return round(max(0.0, min(1.0, x)), 4)


# ===================== 千问大模型评分（八维分数 + 八维置信度，与人岗匹配口径一致）=====================
def score_resume(resume_text: str) -> Tuple[Dict[str, int], Dict[str, float]]:
    """
    返回 (scores, confidences)。
    scores 键为 cap_req_*（0–100）；confidences 键为 cap_conf_*（0–1），表示该维打分的证据强度。
    """
    api_key = Config.DASHSCOPE_API_KEY
    url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    prompt = f"""
你是专业大学生就业能力评估师。根据简历文本，为 8 个能力维度给出 0–100 的供给分，
并为每一维给出 0–1 的置信度（cap_conf_*）：表示你在该维上打分的证据充分程度
（简历中该维相关经历越具体、可核验，置信度越高；越模糊或缺证据则越低）。

8 个分数维度（cap_req_*）：
cap_req_theory: 专业理论知识
cap_req_cross: 交叉学科广度
cap_req_practice: 专业实践技能
cap_req_digital: 数字素养技能
cap_req_innovation: 创新创业能力
cap_req_teamwork: 团队协作能力
cap_req_social: 社会实践网络
cap_req_growth: 学习与发展潜力

8 个置信度（cap_conf_*，与上列一一对应）：
cap_conf_theory, cap_conf_cross, cap_conf_practice, cap_conf_digital,
cap_conf_innovation, cap_conf_teamwork, cap_conf_social, cap_conf_growth

简历内容：
{resume_text}

只输出一个标准 JSON 对象，不要其它文字。格式示例：
{{
    "cap_req_theory": 72,
    "cap_req_cross": 55,
    "cap_req_practice": 68,
    "cap_req_digital": 60,
    "cap_req_innovation": 50,
    "cap_req_teamwork": 65,
    "cap_req_social": 48,
    "cap_req_growth": 70,
    "cap_conf_theory": 0.72,
    "cap_conf_cross": 0.55,
    "cap_conf_practice": 0.70,
    "cap_conf_digital": 0.60,
    "cap_conf_innovation": 0.45,
    "cap_conf_teamwork": 0.65,
    "cap_conf_social": 0.50,
    "cap_conf_growth": 0.68
}}
"""

    payload = {
        "model": "qwen-turbo",
        "input": {"messages": [{"role": "user", "content": prompt}]},
        "parameters": {"temperature": 0.1, "result_format": "text"},
    }

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=30)
        data = resp.json()
        content = data["output"]["text"].strip()
        content = content.replace("```json", "").replace("```", "").strip()
        parsed = json.loads(content)

        scores: Dict[str, int] = {}
        for k in DIM_KEYS:
            scores[k] = _clamp_score(parsed.get(k, 60))

        confidences: Dict[str, float] = {}
        for k in CONF_KEYS:
            confidences[k] = _clamp_conf(parsed.get(k, 0.55))

        return scores, confidences
    except Exception as e:
        print("千问调用失败:", e)
        return _default_scores(), _default_confidences()

def create_radar_chart(scores):
    data = [[
        scores["cap_req_theory"], scores["cap_req_cross"], scores["cap_req_practice"],
        scores["cap_req_digital"], scores["cap_req_innovation"], scores["cap_req_teamwork"],
        scores["cap_req_social"], scores["cap_req_growth"]
    ]]
    radar = (
        Radar()
        .add_schema(
            schema=[
                opts.RadarIndicatorItem(name="专业理论", max_=100),
                opts.RadarIndicatorItem(name="交叉广度", max_=100),
                opts.RadarIndicatorItem(name="专业实践", max_=100),
                opts.RadarIndicatorItem(name="数字素养", max_=100),
                opts.RadarIndicatorItem(name="创新能力", max_=100),
                opts.RadarIndicatorItem(name="团队协作", max_=100),
                opts.RadarIndicatorItem(name="社会实践", max_=100),
                opts.RadarIndicatorItem(name="学习成长", max_=100),
            ]
        )
        .add("能力画像", data)
        .set_global_opts(title_opts=opts.TitleOpts(title="个人能力画像图谱"))
    )
    return radar.render_embed()