import json
from fastapi import FastAPI, HTTPException
from typing import Dict, Any

class DebugAPI:
    def __init__(self, agent):
        self.agent = agent
        self.app = FastAPI()
        self.setup_debug_routes()
    
    def setup_debug_routes(self):
        # 1. 意图解析调试
        @self.app.post("/debug/parse_intent")
        async def debug_parse_intent(text: str):
            parsed = self.agent.nlp_parser.parse(text)
            return {
                "original_text": text,
                "intent_type": parsed.intent_type.value,
                "entities": parsed.entities,
                "confidence": parsed.confidence
            }
        
        # 2. 对话状态调试
        @self.app.get("/debug/conversation_state")
        async def get_conversation_state():
            return self.agent.conversation_context
        
        # 3. 数据库内容查看
        @self.app.get("/debug/calendar_events")
        async def get_all_events():
            # 获取所有事件（调试用）
            import sqlite3
            conn = sqlite3.connect("calendar.db")
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM events")
            rows = cursor.fetchall()
            conn.close()
            
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
            return {"events": events}
        
        # 4. 测试用例执行
        @self.app.post("/debug/run_test_case")
        async def run_test_case(test_case: Dict[str, Any]):
            # 执行单个测试用例
            user_input = test_case.get("input")
            expected_intent = test_case.get("expected_intent")
            
            result = await self.agent.process_input(user_input)
            return {
                "input": user_input,
                "expected": expected_intent,
                "actual_result": result
            }