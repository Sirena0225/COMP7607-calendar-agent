# COMP7607-calendar-agent

## Calendar Agent

一个基于LLM的日历管理助手，支持自然语言交互来管理日程安排，可同步到Google Calendar。

### 项目结构
calendar_agent/<br>
├── main.py   # 主程序入口<br>
├── config.py    # 配置文件<br>
├── models.py  # 数据模型定义<br>
├── database.py   # 数据库操作<br>
├── nlp_parser.py    # LLM驱动的解析器<br>
├── qwen_client.py     # Qwen API客户端 也可以换用其他llm 记得同时改config.py<br>
├── calendar_agent.py    # 核心Agent 语义识别问答<br>
├── calendar_config.py   # 调用Google日历api<br>
├── google_calendar_sync.py   # 启用Google日历同步<br>
├── calendar.db  # 日历数据库<br>
├── check_database.py  # 可以单独运行此py文件查询数据库内容<br>
├── debug-api.py  # 暂未使用<br>


### 更改
- static/index.html 中包含简单的前端代码 可以进行对话框交互 可视化日历
- 可识别三点 十一点 汉字
- 添加了可交互式的训练计划生成功能

### 开始
- 添加了openai 依赖 
- 将google canledar的json文件放在根目录 并改名为google-calendar-api.json
- 在config.py 中设置QWEN_API_KEY  QWEN_MODEL  GOOGLE_CALENDAR_API_KEY
- 如果是新加坡qwen api 在 qwen_client.py中修改base_url 默认为北京api
- 运行 python main.py    在浏览器打开http://0.0.0.0:8000


