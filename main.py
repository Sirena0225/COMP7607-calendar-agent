
import json
import os
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from datetime import datetime, date, timedelta
from calendar_agent import CalendarAgent
from database import SQLiteCalendar
from models import CalendarEvent

# 初始化FastAPI应用
app = FastAPI(title="Calendar AI Agent")

# 允许跨域请求（前端调用需要）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境需指定前端域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 谷歌日历配置（原有函数保留）
def setup_google_calendar():
    config_file = 'google-calendar-api.json'
    if os.path.exists(config_file):
        print(f"✓ 找到Google Calendar配置文件: {os.path.abspath(config_file)}")
    else:
        print(f"⚠ 未找到配置文件: {config_file}")
    os.environ['GOOGLE_CALENDAR_CREDENTIALS_FILE'] = os.path.abspath(config_file)


# 挂载静态文件目录（存放前端HTML/CSS/JS）
app.mount("/static", StaticFiles(directory="static"), name="static")

# 初始化日历组件
setup_google_calendar()
calendar_db = SQLiteCalendar()
agent = CalendarAgent(calendar_interface=calendar_db)


# 数据模型（前端请求格式）
class UserMessage(BaseModel):
    message: str


class DateRequest(BaseModel):
    date: str  # 格式: YYYY-MM-DD


# 🛠️ 修复：在 SQLiteCalendar 类中添加缺失的方法
async def get_events_by_date(self, target_date: date) -> list:
    """获取指定日期的事件"""
    try:
        start_datetime = datetime.combine(target_date, datetime.min.time())
        end_datetime = datetime.combine(target_date, datetime.max.time())
        events = await self.list_events(start_datetime, end_datetime)
        return events
    except Exception as e:
        print(f"获取日期事件错误: {e}")
        return []


async def get_events_by_month(self, year: int, month: int) -> list:
    """获取指定月份的事件"""
    try:
        start_date = datetime(year, month, 1)
        if month == 12:
            end_date = datetime(year + 1, 1, 1) - timedelta(seconds=1)
        else:
            end_date = datetime(year, month + 1, 1) - timedelta(seconds=1)
        events = await self.list_events(start_date, end_date)
        return events
    except Exception as e:
        print(f"获取月份事件错误: {e}")
        return []


# 🛠️ 修复：将方法添加到 SQLiteCalendar 实例
calendar_db.get_events_by_date = lambda target_date: get_events_by_date(calendar_db, target_date)
calendar_db.get_events_by_month = lambda year, month: get_events_by_month(calendar_db, year, month)


# 前端页面入口
@app.get("/")
async def get_frontend():
    return FileResponse("static/index.html")


# 处理用户消息的API（用于对话框）
@app.post("/api/message")
async def process_message(msg: UserMessage):
    try:
        response = await agent.process_input(msg.message)
        return {"response": response}
    except Exception as e:
        print(f"处理消息错误: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# 获取指定日期的日程（用于日视图）
@app.post("/api/day-schedule")
async def get_day_schedule(req: DateRequest):
    try:
        target_date = datetime.strptime(req.date, "%Y-%m-%d").date()
        print(f"[DEBUG] 获取日日程: {req.date}")

        # 🛠️ 修复：使用正确的方法获取事件
        events = await calendar_db.get_events_by_date(target_date)
        print(f"[DEBUG] 找到 {len(events)} 个事件")

        # 🛠️ 修复：确保事件数据正确序列化
        events_data = []
        for event in events:
            event_dict = {
                "id": event.id,
                "title": event.title,
                "start_time": event.start_time.isoformat() if event.start_time else None,
                "end_time": event.end_time.isoformat() if event.end_time else None,
                "description": event.description,
                "location": event.location,
                "attendees": event.attendees or []
            }
            events_data.append(event_dict)

        return {
            "date": req.date,
            "events": events_data
        }
    except Exception as e:
        print(f"获取日日程错误: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# 获取指定月份的日程（用于月视图）
@app.get("/api/month-schedule/{year}/{month}")
async def get_month_schedule(year: int, month: int):
    try:
        print(f"[DEBUG] 获取月日程: {year}-{month}")

        # 🛠️ 修复：使用正确的方法获取事件
        events = await calendar_db.get_events_by_month(year, month)
        print(f"[DEBUG] 找到 {len(events)} 个事件")

        # 🛠️ 修复：确保事件数据正确序列化
        events_data = []
        for event in events:
            event_dict = {
                "id": event.id,
                "title": event.title,
                "start_time": event.start_time.isoformat() if event.start_time else None,
                "end_time": event.end_time.isoformat() if event.end_time else None,
                "description": event.description,
                "location": event.location,
                "attendees": event.attendees or []
            }
            events_data.append(event_dict)

        return {
            "year": year,
            "month": month,
            "events": events_data
        }
    except Exception as e:
        print(f"获取月日程错误: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# 🛠️ 修复：添加调试API端点
@app.get("/api/debug/events")
async def debug_all_events():
    """调试接口：获取所有事件"""
    try:
        # 使用数据库的原始方法获取所有事件
        conn = calendar_db.conn if hasattr(calendar_db, 'conn') else None
        if not conn:
            import sqlite3
            conn = sqlite3.connect('calendar.db')

        cursor = conn.cursor()
        cursor.execute('SELECT * FROM events ORDER BY start_time')
        rows = cursor.fetchall()

        events = []
        for row in rows:
            events.append({
                "id": row[0],
                "title": row[1],
                "start_time": row[2],
                "end_time": row[3],
                "description": row[4],
                "location": row[5]
            })

        return {"total_events": len(rows), "events": events}
    except Exception as e:
        return {"error": str(e)}


# WebSocket连接（可选，用于实时消息）
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)["message"]
            response = await agent.process_input(message)
            await websocket.send_text(json.dumps({"response": response}))
    except WebSocketDisconnect:
        print("WebSocket连接断开")


# 🛠️ 修复：添加健康检查端点
@app.get("/health")
async def health_check():
    """健康检查端点"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

# 在 main.py 中添加训练计划API端点

@app.get("/api/workout-plans")
async def get_workout_plans():
    """获取所有训练计划"""
    try:
        workout_plans = await calendar_db.get_workout_plans()
        return {
            "workout_plans": [plan.to_dict() for plan in workout_plans]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/workout-plans")
async def delete_all_workout_plans():
    """删除所有训练计划"""
    try:
        success = await calendar_db.delete_workout_plans()
        events_deleted = await calendar_db.delete_workout_events()
        return {
            "success": success,
            "events_deleted": events_deleted,
            "message": f"删除了 {events_deleted} 个训练事件"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# 在 main.py 中添加任务分解API端点

@app.get("/api/task-breakdowns")
async def get_task_breakdowns():
    """获取所有任务分解"""
    try:
        task_breakdowns = await calendar_db.get_task_breakdowns()
        return {
            "task_breakdowns": [breakdown.to_dict() for breakdown in task_breakdowns]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/task-breakdowns")
async def delete_all_task_breakdowns():
    """删除所有任务分解"""
    try:
        success = await calendar_db.delete_task_breakdowns()
        return {
            "success": success,
            "message": "所有任务分解已删除"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# 在 main.py 中添加删除任务分解的 API 端点
@app.delete("/api/task-breakdowns")
async def delete_all_task_breakdowns():
    """删除所有任务分解"""
    try:
        success = await calendar_db.delete_all_task_breakdowns()
        return {
            "success": success,
            "message": "所有任务分解已删除"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/task-breakdowns/{title}")
async def delete_task_breakdown_by_title(title: str):
    """根据标题删除任务分解"""
    try:
        success = await calendar_db.delete_task_breakdown_by_title(title)
        return {
            "success": success,
            "message": f"标题包含 '{title}' 的任务分解已删除"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/task-breakdowns")
async def get_all_task_breakdowns():
    """获取所有任务分解"""
    try:
        task_breakdowns = await calendar_db.get_all_task_breakdowns()
        return {
            "task_breakdowns": [breakdown.to_dict() for breakdown in task_breakdowns]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    # 启动服务，默认端口8000
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)