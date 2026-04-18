import os

from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret")
    TOKEN_EXPIRES_HOURS = int(os.getenv("TOKEN_EXPIRES_HOURS", "24"))

    MYSQL_HOST = os.getenv("MYSQL_HOST", "47.104.168.245")
    MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
    MYSQL_USER = os.getenv("MYSQL_USER", "suilli")
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

    FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://localhost:4321")
    # 在Config类中添加以下配置
    OCR_APP_ID = os.getenv("OCR_APP_ID")
    OCR_API_KEY = os.getenv("OCR_API_KEY")
    OCR_SECRET_KEY = os.getenv("OCR_SECRET_KEY")

    DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY")

    # 人岗匹配 POST /api/match/preview（与 tools/job_eval 可共用 DEEPSEEK_API_KEY）
    MATCH_PREVIEW_MAX_SCAN = int(os.getenv("MATCH_PREVIEW_MAX_SCAN", "2000"))
    MATCH_PREVIEW_MAX_SCAN_HARD = int(os.getenv("MATCH_PREVIEW_MAX_SCAN_HARD", "8000"))
    MATCH_TOP_K_RETURN = int(os.getenv("MATCH_TOP_K_RETURN", "30"))
    MATCH_LLM_POOL_K = int(os.getenv("MATCH_LLM_POOL_K", "40"))
    DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
    MATCH_DEEPSEEK_MODEL = os.getenv("MATCH_DEEPSEEK_MODEL", "deepseek-chat")
    MATCH_LLM_TIMEOUT_SECONDS = float(os.getenv("MATCH_LLM_TIMEOUT_SECONDS", "120"))
