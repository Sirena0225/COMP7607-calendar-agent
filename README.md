# COMP7607-calendar-agent

calendar_agent/
├── main.py   # 主程序入口
├── config.py    # 配置文件
├── models.py  # 数据模型定义
├── database.py   # 数据库操作
├── nlp_parser.py    # LLM驱动的解析器
├── qwen_client.py     # Qwen API客户端 也可以换用其他llm 记得同时改config.py
├── calendar_agent.py   # 核心Agent 语义识别问答
├── calendar_config.py   # 调用Google日历api
├── google_calendar_sync.py   # 启用Google日历同步
├── calendar.db  # 日历数据库
├── check_database.py  # 可以单独运行此py文件查询数据库内容
├── debug-api.py  # 暂未使用
