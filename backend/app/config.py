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
    # 粗排「形状 + 软缺口」：八维 Pearson 相关权重；岗位每维可高于学生 soft_margin 内不记缺口
    MATCH_COARSE_SHAPE_WEIGHT = float(os.getenv("MATCH_COARSE_SHAPE_WEIGHT", "0.42"))
    MATCH_GAP_SOFT_MARGIN_FIT = float(os.getenv("MATCH_GAP_SOFT_MARGIN_FIT", "6"))
    MATCH_GAP_SOFT_MARGIN_STRETCH = float(os.getenv("MATCH_GAP_SOFT_MARGIN_STRETCH", "10"))
    # 冲刺高质模式粗排：低于该 match_score 的岗位归入后段；权重和须与 match_preview._sort_ranked_for_goal 一致时可调
    MATCH_STRETCH_MATCH_SCORE_FLOOR = float(os.getenv("MATCH_STRETCH_MATCH_SCORE_FLOOR", "38"))
    MATCH_STRETCH_SORT_W_MATCH = float(os.getenv("MATCH_STRETCH_SORT_W_MATCH", "0.32"))
    MATCH_STRETCH_SORT_W_JOB_AVG = float(os.getenv("MATCH_STRETCH_SORT_W_JOB_AVG", "0.68"))
    DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
    MATCH_DEEPSEEK_MODEL = os.getenv("MATCH_DEEPSEEK_MODEL", "deepseek-chat")
    MATCH_LLM_TIMEOUT_SECONDS = float(os.getenv("MATCH_LLM_TIMEOUT_SECONDS", "120"))

    # 生涯报告：多模型编排与调用开关
    CAREER_PRIMARY_PROVIDER = os.getenv("CAREER_PRIMARY_PROVIDER", "deepseek")
    CAREER_SECONDARY_PROVIDER = os.getenv("CAREER_SECONDARY_PROVIDER", "qwen")
    CAREER_COPYWRITER_PROVIDER = os.getenv("CAREER_COPYWRITER_PROVIDER", "doubao")
    CAREER_DEEPSEEK_MODEL = os.getenv("CAREER_DEEPSEEK_MODEL", "deepseek-chat")
    CAREER_QWEN_MODEL = os.getenv("CAREER_QWEN_MODEL", "qwen-plus")
    CAREER_ARK_MODEL = os.getenv("CAREER_ARK_MODEL", "doubao-seed-2-0-lite-260215")
    CAREER_LLM_TIMEOUT_SECONDS = float(os.getenv("CAREER_LLM_TIMEOUT_SECONDS", "120"))
    CAREER_LLM_MAX_RETRIES = int(os.getenv("CAREER_LLM_MAX_RETRIES", "2"))
    # M3 复盘指标抽取：略提高随机性，减轻「全是 5 的倍数」的凑整倾向（0~2，默认 0.55）
    CAREER_REVIEW_EXTRACT_TEMPERATURE = float(os.getenv("CAREER_REVIEW_EXTRACT_TEMPERATURE", "0.55"))
    CAREER_ENABLE_COPYWRITER = str(os.getenv("CAREER_ENABLE_COPYWRITER", "true")).strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )
    CAREER_ENABLE_REPLAN_LLM = str(os.getenv("CAREER_ENABLE_REPLAN_LLM", "true")).strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )
    CAREER_ENABLE_TREND_AUGMENT = str(
        os.getenv("CAREER_ENABLE_TREND_AUGMENT", "true")
    ).strip().lower() in ("1", "true", "yes", "on")
