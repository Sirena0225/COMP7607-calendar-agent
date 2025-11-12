class APIConfig:
    # LLM API配置
    # OPENAI_API_KEY = "openai-key"  # OpenAI GPT
    QWEN_API_KEY = "YOUR-QWEN-KEY"
    QWEN_MODEL = "qwen-turbo"
    # CLAUDE_API_KEY = "claude-key"  # Claude
    
    # 日期解析API
    DATE_PARSER_MODEL = "dateutil.parser"
    
    # 数据库连接
    DB_CONNECTION_STRING = "sqlite:///calendar.db"
    
    # 日历同步API
    GOOGLE_CALENDAR_API_KEY = "cfd5543e44290427888baf522a0ae89d26e6ec3a" # 测试用google日历api
    # OUTLOOK_CALENDAR_API_KEY = "your-outlook-key"

    MAX_RETRIES = 3
    TIMEOUT = 30 