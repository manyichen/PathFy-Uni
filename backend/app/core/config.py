import os

from dotenv import load_dotenv

load_dotenv()

# core/ 位于 app/core/，向上两级为 backend/
_BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def _env_bool(name: str, default: str = "false") -> bool:
    return str(os.getenv(name, default)).strip().lower() in ("1", "true", "yes", "on")


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret")
    TOKEN_EXPIRES_HOURS = int(os.getenv("TOKEN_EXPIRES_HOURS", "24"))

    MYSQL_HOST = os.getenv("MYSQL_HOST", "127.0.0.1")
    MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
    MYSQL_USER = os.getenv("MYSQL_USER", "root")
    MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "")
    MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "suilli_mizi")

    NEO4J_URI = os.getenv("NEO4J_URI", "bolt://127.0.0.1:7687")
    NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
    NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")
    NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")

    ARK_API_KEY = os.getenv("ARK_API_KEY", "")
    ARK_BASE_URL = os.getenv("ARK_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3")
    ARK_MODEL = os.getenv("ARK_MODEL", "doubao-seed-2-0-mini-260215")
    AI_MAX_RETURN_JOBS = int(os.getenv("AI_MAX_RETURN_JOBS", "40"))
    AI_CONTEXT_WINDOW = int(os.getenv("AI_CONTEXT_WINDOW", "6"))
    AI_LLM_TIMEOUT_SECONDS = int(os.getenv("AI_LLM_TIMEOUT_SECONDS", "90"))

    # 外发 LLM / 本地存储隐私（见 app/infrastructure/privacy.py）
    LLM_PRIVACY_MODE = _env_bool("LLM_PRIVACY_MODE", "true")
    LLM_MAX_TEXT_CHARS = int(os.getenv("LLM_MAX_TEXT_CHARS", "4000"))
    LLM_MAX_RESUME_CHARS = int(os.getenv("LLM_MAX_RESUME_CHARS", "6000"))
    LLM_MAX_FIELD_CHARS = int(os.getenv("LLM_MAX_FIELD_CHARS", "1200"))
    LLM_STORE_RAW_SNIPPETS = _env_bool("LLM_STORE_RAW_SNIPPETS", "false")
    LOCAL_STORE_RAW_RESUME_TEXT = _env_bool("LOCAL_STORE_RAW_RESUME_TEXT", "false")
    LOCAL_STORE_RAW_REVIEW_TEXT = _env_bool("LOCAL_STORE_RAW_REVIEW_TEXT", "false")
    LOCAL_STORE_RAW_CHAT_MESSAGES = _env_bool("LOCAL_STORE_RAW_CHAT_MESSAGES", "false")
    LOCAL_MAX_STORED_TEXT_CHARS = int(os.getenv("LOCAL_MAX_STORED_TEXT_CHARS", "4000"))
    DELETE_UPLOADED_RESUME_AFTER_OCR = _env_bool("DELETE_UPLOADED_RESUME_AFTER_OCR", "true")
    API_CACHE_NO_STORE = _env_bool("API_CACHE_NO_STORE", "true")

    FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://localhost:4321")
    MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "10"))
    # 简历原文件临时目录（Web 不可访问；OCR 完成后自动删除）
    RESUME_UPLOAD_DIR = os.path.abspath(
        os.getenv("RESUME_UPLOAD_DIR")
        or os.path.join(_BACKEND_ROOT, "private_uploads", "resumes")
    )
    OCR_APP_ID = os.getenv("OCR_APP_ID")
    OCR_API_KEY = os.getenv("OCR_API_KEY")
    OCR_SECRET_KEY = os.getenv("OCR_SECRET_KEY")

    DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY")

    MATCH_PREVIEW_MAX_SCAN = int(os.getenv("MATCH_PREVIEW_MAX_SCAN", "2000"))
    MATCH_PREVIEW_MAX_SCAN_HARD = int(os.getenv("MATCH_PREVIEW_MAX_SCAN_HARD", "8000"))
    MATCH_TOP_K_RETURN = int(os.getenv("MATCH_TOP_K_RETURN", "30"))
    MATCH_LLM_POOL_K = int(os.getenv("MATCH_LLM_POOL_K", "40"))
    MATCH_COARSE_SHAPE_WEIGHT = float(os.getenv("MATCH_COARSE_SHAPE_WEIGHT", "0.42"))
    MATCH_GAP_SOFT_MARGIN_FIT = float(os.getenv("MATCH_GAP_SOFT_MARGIN_FIT", "6"))
    MATCH_GAP_SOFT_MARGIN_STRETCH = float(os.getenv("MATCH_GAP_SOFT_MARGIN_STRETCH", "10"))
    MATCH_STRETCH_MATCH_SCORE_FLOOR = float(os.getenv("MATCH_STRETCH_MATCH_SCORE_FLOOR", "38"))
    MATCH_STRETCH_SORT_W_MATCH = float(os.getenv("MATCH_STRETCH_SORT_W_MATCH", "0.32"))
    MATCH_STRETCH_SORT_W_JOB_AVG = float(os.getenv("MATCH_STRETCH_SORT_W_JOB_AVG", "0.68"))
    DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
    MATCH_DEEPSEEK_MODEL = os.getenv("MATCH_DEEPSEEK_MODEL", "deepseek-chat")
    MATCH_LLM_TIMEOUT_SECONDS = float(os.getenv("MATCH_LLM_TIMEOUT_SECONDS", "120"))

    CAREER_DEEPSEEK_MODEL = os.getenv("CAREER_DEEPSEEK_MODEL", "deepseek-chat")
    CAREER_ARK_MODEL = os.getenv("CAREER_ARK_MODEL", "doubao-seed-2-0-lite-260215")
    CAREER_LLM_TIMEOUT_SECONDS = float(os.getenv("CAREER_LLM_TIMEOUT_SECONDS", "120"))
    CAREER_LLM_MAX_RETRIES = int(os.getenv("CAREER_LLM_MAX_RETRIES", "2"))
    CAREER_REVIEW_EXTRACT_TEMPERATURE = float(os.getenv("CAREER_REVIEW_EXTRACT_TEMPERATURE", "0.55"))
    CAREER_ENABLE_COPYWRITER = str(os.getenv("CAREER_ENABLE_COPYWRITER", "true")).strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )
    CAREER_ENABLE_PER_TARGET_COPYWRITER = str(
        os.getenv("CAREER_ENABLE_PER_TARGET_COPYWRITER", "true")
    ).strip().lower() in ("1", "true", "yes", "on")
    CAREER_ENABLE_REPLAN_LLM = str(os.getenv("CAREER_ENABLE_REPLAN_LLM", "true")).strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )
    CAREER_ENABLE_TREND_AUGMENT = str(
        os.getenv("CAREER_ENABLE_TREND_AUGMENT", "false")
    ).strip().lower() in ("1", "true", "yes", "on")
    CAREER_ENABLE_PUBLIC_INFO = str(
        os.getenv("CAREER_ENABLE_PUBLIC_INFO", "true")
    ).strip().lower() in ("1", "true", "yes", "on")
    CAREER_PUBLIC_INFO_CACHE_DAYS = int(os.getenv("CAREER_PUBLIC_INFO_CACHE_DAYS", "14"))
    CAREER_PUBLIC_INFO_MAX_SUMMARY_CHARS = int(os.getenv("CAREER_PUBLIC_INFO_MAX_SUMMARY_CHARS", "300"))
    CAREER_PUBLIC_SEARCH_MAX_CHARS = int(os.getenv("CAREER_PUBLIC_SEARCH_MAX_CHARS", "1200"))
    CAREER_ENABLE_GRAPH_RECOMMENDATIONS = str(
        os.getenv("CAREER_ENABLE_GRAPH_RECOMMENDATIONS", "true")
    ).strip().lower() in ("1", "true", "yes", "on")
    CAREER_ENABLE_RECOMMENDATION_LLM = str(
        os.getenv("CAREER_ENABLE_RECOMMENDATION_LLM", "true")
    ).strip().lower() in ("1", "true", "yes", "on")
    CAREER_ENABLE_PLAN_CUSTOMIZATION = str(
        os.getenv("CAREER_ENABLE_PLAN_CUSTOMIZATION", "true")
    ).strip().lower() in ("1", "true", "yes", "on")
    CAREER_LR_POOL_PER_TARGET = int(os.getenv("CAREER_LR_POOL_PER_TARGET", "18"))
    CAREER_COMP_POOL_PER_TARGET = int(os.getenv("CAREER_COMP_POOL_PER_TARGET", "10"))
    CAREER_LR_PER_TARGET = int(os.getenv("CAREER_LR_PER_TARGET", "6"))
    CAREER_COMP_PER_TARGET = int(os.getenv("CAREER_COMP_PER_TARGET", "3"))
