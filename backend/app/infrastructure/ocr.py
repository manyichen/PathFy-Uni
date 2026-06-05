"""百度 OCR、PDF 文本抽取与 PDF 转图（能力画像材料解析）。"""

from __future__ import annotations

import os
from typing import List

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
        connect_timeout_ms = int(float(getattr(Config, "OCR_CONNECT_TIMEOUT_SECONDS", 3)) * 1000)
        socket_timeout_ms = int(float(getattr(Config, "OCR_SOCKET_TIMEOUT_SECONDS", 20)) * 1000)
        _ocr_client.setConnectionTimeoutInMillis(max(1000, connect_timeout_ms))
        _ocr_client.setSocketTimeoutInMillis(max(1000, socket_timeout_ms))
    return _ocr_client


def ocr_image(file_path: str) -> str:
    with open(file_path, "rb") as f:
        img_data = f.read()
    result = _get_ocr_client().basicGeneral(img_data)
    if not isinstance(result, dict):
        raise RuntimeError("OCR 返回格式异常")
    if result.get("error_code"):
        raise RuntimeError(f"OCR 失败: {result.get('error_msg') or result.get('error_code')}")
    words = result.get("words_result", [])
    return "\n".join([w["words"] for w in words])


def extract_pdf_text(pdf_path: str, *, max_pages: int = 12) -> str:
    """优先抽取文本型 PDF；扫描件会返回很少文本，调用方可再走 OCR。"""
    chunks: list[str] = []
    with fitz.open(pdf_path) as doc:
        for page_idx in range(min(len(doc), max_pages)):
            text = doc.load_page(page_idx).get_text("text").strip()
            if text:
                chunks.append(f"[PDF 第 {page_idx + 1} 页]\n{text}")
    return "\n\n".join(chunks)


def pdf_to_images(pdf_path: str, *, max_pages: int = 8) -> List[str]:
    output_dir = os.path.join(os.path.dirname(pdf_path), "pdf_images")
    os.makedirs(output_dir, exist_ok=True)
    paths: List[str] = []
    with fitz.open(pdf_path) as doc:
        for page_idx in range(min(len(doc), max_pages)):
            page = doc.load_page(page_idx)
            pix = page.get_pixmap()
            stem, _ = os.path.splitext(os.path.basename(pdf_path))
            img_path = os.path.join(output_dir, f"{stem}_p{page_idx + 1}.png")
            pix.save(img_path)
            paths.append(img_path)
    return paths


def pdf_to_image(pdf_path: str) -> str:
    paths = pdf_to_images(pdf_path, max_pages=1)
    if not paths:
        raise RuntimeError("PDF 转图片失败")
    return paths[0]
