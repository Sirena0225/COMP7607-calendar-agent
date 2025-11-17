import json
import asyncio
import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from calendar_agent import CalendarAgent
from database import SQLiteCalendar

async def main():
    print("=== Calendar Agent 启动 ===")
    print(f"使用Qwen模型: {os.getenv('QWEN_MODEL', 'qwen-turbo')}")
    
    # 初始化组件
    print("初始化数据库...")
    calendar = SQLiteCalendar()
    
    print("初始化Calendar Agent...")
    agent = CalendarAgent(calendar_interface=calendar)
    
    print("=== 交互式测试 ===")
    print("输入 'quit' 退出，输入 'help' 获取帮助")
    
    while True:
        user_input = input("\n请输入: ")
        
        if user_input.lower() == 'quit':
            break
        elif user_input.lower() == 'help':
            print("""
可用命令:
- 添加事件: "明天下午3点开会"
- 查询日程: "今天有什么安排"
- 列出日程: "显示本周日程"
- 帮助: "help"
- 退出: "quit"
            """)
            continue
        
        try:
            response = await agent.process_input(user_input)
            print(f"Agent: {response}")
        except Exception as e:
            print(f"错误: {e}")

if __name__ == "__main__":
    asyncio.run(main())