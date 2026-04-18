import os
import requests
import json
from aip import AipOcr
from pyecharts.charts import Radar
from pyecharts import options as opts
import fitz
from app.config import Config

# ===================== 百度OCR（真实调用）=====================
ocr_client = AipOcr(
    Config.OCR_APP_ID,
    Config.OCR_API_KEY,
    Config.OCR_SECRET_KEY
)

def ocr_image(file_path):
    with open(file_path, "rb") as f:
        img_data = f.read()
    result = ocr_client.basicGeneral(img_data)
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

# ===================== 千问大模型评分（和队长统一）=====================
def score_resume(resume_text):
    api_key =Config.DASHSCOPE_API_KEY
    url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    prompt = f"""
你是专业大学生就业能力评估师，严格按8个维度0-100分评分，只输出标准JSON，无其他内容。

8个维度：
cap_req_theory: 专业理论知识
cap_req_cross: 交叉学科广度
cap_req_practice: 专业实践技能
cap_req_digital: 数字素养技能
cap_req_innovation: 创新创业能力
cap_req_teamwork: 团队协作能力
cap_req_social: 社会实践网络
cap_req_growth: 学习与发展潜力

简历内容：
{resume_text}

输出格式：
{{
    "cap_req_theory": 分数,
    "cap_req_cross": 分数,
    "cap_req_practice": 分数,
    "cap_req_digital": 分数,
    "cap_req_innovation": 分数,
    "cap_req_teamwork": 分数,
    "cap_req_social": 分数,
    "cap_req_growth": 分数
}}
"""

    payload = {
        "model": "qwen-turbo",
        "input": {"messages": [{"role": "user", "content": prompt}]},
        "parameters": {"temperature": 0.1, "result_format": "text"}
    }

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=30)
        data = resp.json()
        content = data["output"]["text"].strip()
        content = content.replace("```json", "").replace("```", "").strip()
        scores = json.loads(content)

        keys = [
            "cap_req_theory", "cap_req_cross", "cap_req_practice",
            "cap_req_digital", "cap_req_innovation", "cap_req_teamwork",
            "cap_req_social", "cap_req_growth"
        ]
        for k in keys:
            if k not in scores:
                scores[k] = 60
        return scores
    except Exception as e:
        print("千问调用失败:", e)
        return {k: 60 for k in [
            "cap_req_theory", "cap_req_cross", "cap_req_practice",
            "cap_req_digital", "cap_req_innovation", "cap_req_teamwork",
            "cap_req_social", "cap_req_growth"
        ]}

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