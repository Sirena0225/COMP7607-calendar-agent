class APIConfig:
    # LLM API配置
    # OPENAI_API_KEY = "openai-key"  # OpenAI GPT
    QWEN_API_KEY = "YOUR-QWEN-API-KEY"  # Qwen
    #QWEN_MODEL = "qwen-turbo"
    QWEN_MODEL = "qwen-plus"
    # CLAUDE_API_KEY = "claude-key"  # Claude
    
    # 日期解析API
    DATE_PARSER_MODEL = "dateutil.parser"
    
    # 数据库连接
    DB_CONNECTION_STRING = "sqlite:///calendar.db"

    MAX_RETRIES = 3
    TIMEOUT = 30 