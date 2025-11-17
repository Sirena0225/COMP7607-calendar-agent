# COMP7607-calendar-agent

## Calendar Agent

一个基于LLM的日历管理助手，支持自然语言交互来管理日程安排，可同步到Google Calendar。

### 项目结构
COMP7607-calendar-agent/
│
├── backend/            # 后端（FastAPI + SQLite + CalendarAgent）
│   ├── main.py                    # 主程序入口
│   ├── server.py                  # 提供给前端的入口（提供 /api/chat API）
│   ├── config.py                  # 配置文件
│   ├── models.py                  # Pydantic 数据模型
│   ├── database.py                # SQLite 数据库操作
│   ├── nlp_parser.py              # LLM 驱动的意图解析器
│   ├── qwen_client.py             # Qwen API 客户端（可替换成其他 LLM）
│   ├── calendar_agent.py          # 核心 Agent：语义识别 / 意图/回复生成
│   ├── calendar_config.py         # Google Calendar API 配置
│   ├── google_calendar_sync.py    # 同步到谷歌日历
│   ├── check_database.py          # 查看 SQLite 数据库内容
│   ├── debug_api.py               # Debug 接口（现已启用）
│   ├── calendar.db                # 本地 SQLite 数据库
│   ├── requirements.txt           # 后端依赖
│
└── frontend/          # 前端（React Native + Expo）
    ├── App.js
    ├── package.json
    ├── tsconfig.json
    ├── assets/
    └── src/
        ├── api/                   # Axios 封装与 API 调用
        ├── navigation/BottomTabs  # 底部导航
        └── screens/
            ├── ChatScreen.tsx     # 与后端 /api/chat 交互
            ├── CalendarScreen.tsx # 展示 SQLite 事件
            └── DebugScreen.tsx    # 调试意图解析、对话状态

前端依赖安装方法：
cd frontend
npm install
npx expo start

