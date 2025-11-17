from fastapi import FastAPI, Body
from debug_api import DebugAPI
from calendar_agent import CalendarAgent
from database import SQLiteCalendar

app = FastAPI()

# 初始化数据库
calendar = SQLiteCalendar()

# 初始化日历智能助手 Agent
agent = CalendarAgent(calendar_interface=calendar)

# 注册调试路由
debug_api = DebugAPI(agent)
app.include_router(debug_api.router)

# 前端调用的聊天接口
@app.post("/api/chat")
async def chat(text: str = Body(...)):
    reply = await agent.process_input(text)
    return {"reply": reply}

@app.get("/")
def root():
    return {"status": "Backend running", "model": "qwen-turbo"}
