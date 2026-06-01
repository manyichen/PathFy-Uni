"""跨域基础设施：Neo4j、LLM、OCR、薪资解析等。"""

from app.infrastructure.llm import build_ark_openai_client, call_ark_json, strip_json_fence
from app.infrastructure.neo4j import (
    CONF_KEYS,
    DIM_KEYS,
    PROMOTION_EDGE_SOURCES,
    neo4j_driver,
    neo4j_settings,
    serialize_job_row,
)
from app.infrastructure.ocr import ocr_image, pdf_to_image
from app.infrastructure.salary import normalize_salary_text, parse_salary_range, salary_matches_target

__all__ = [
    "CONF_KEYS",
    "DIM_KEYS",
    "PROMOTION_EDGE_SOURCES",
    "build_ark_openai_client",
    "call_ark_json",
    "neo4j_driver",
    "neo4j_settings",
    "normalize_salary_text",
    "ocr_image",
    "parse_salary_range",
    "pdf_to_image",
    "salary_matches_target",
    "serialize_job_row",
    "strip_json_fence",
]
