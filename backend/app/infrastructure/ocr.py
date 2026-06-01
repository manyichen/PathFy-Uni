"""百度 OCR 与 PDF 转图（简历上传解析）。"""

from __future__ import annotations

import os

import fitz
from aip import AipOcr

from app.core.config import Config

# 未配置 OCR_* 时仍可启动应用，仅在调用 ocr_image 时初始化客户端
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


def ocr_image(file_path: str) -> str:
    with open(file_path, "rb") as f:
        img_data = f.read()
    result = _get_ocr_client().basicGeneral(img_data)
    words = result.get("words_result", [])
    return "\n".join([w["words"] for w in words])


def pdf_to_image(pdf_path: str) -> str:
    output_dir = os.path.join(os.path.dirname(pdf_path), "pdf_images")
    os.makedirs(output_dir, exist_ok=True)
    doc = fitz.open(pdf_path)
    page = doc.load_page(0)
    pix = page.get_pixmap()
    img_name = os.path.basename(pdf_path).replace(".pdf", ".png")
    img_path = os.path.join(output_dir, img_name)
    pix.save(img_path)
    return img_path
