# COMP7607-calendar-agent

## Calendar Agent

一个基于LLM的日历管理助手，支持自然语言交互来管理日程安排，可同步到Google Calendar。

### 项目结构
COMP7607-calendar-agent/<br>
│<br>
├── backend/            # 后端（FastAPI + SQLite + CalendarAgent）<br>
│   ├── main.py                    # 主程序入口<br>
│   ├── server.py                  # 提供给前端的入口（提供 /api/chat API）<br>
│   ├── config.py                  # 配置文件<br>
│   ├── models.py                  # Pydantic 数据模型<br>
│   ├── database.py                # SQLite 数据库操作<br>
│   ├── nlp_parser.py              # LLM 驱动的意图解析器<br>
│   ├── qwen_client.py             # Qwen API 客户端（可替换成其他 LLM）<br>
│   ├── calendar_agent.py          # 核心 Agent：语义识别 / 意图/回复生成<br>
│   ├── calendar_config.py         # Google Calendar API 配置<br>
│   ├── google_calendar_sync.py    # 同步到谷歌日历<br>
│   ├── check_database.py          # 查看 SQLite 数据库内容<br>
│   ├── debug_api.py               # Debug 接口（现已启用）<br>
│   ├── calendar.db                # 本地 SQLite 数据库<br>
│   ├── requirements.txt           # 后端依赖<br>
│
└── frontend/          # 前端（React Native + Expo）<br>
    ├── App.js<br>
    ├── package.json<br>
    ├── tsconfig.json<br>
    ├── assets/<br>
    └── src/<br>
        ├── api/                   # Axios 封装与 API 调用<br>
        ├── navigation/BottomTabs  # 底部导航<br>
        └── screens/<br>
            ├── ChatScreen.tsx     # 与后端 /api/chat 交互<br>
            ├── CalendarScreen.tsx # 展示 SQLite 事件<br>
            └── DebugScreen.tsx    # 调试意图解析、对话状态<br>

前端依赖安装方法：<br>
cd frontend<br>
npm install<br>
npx expo start<br>

