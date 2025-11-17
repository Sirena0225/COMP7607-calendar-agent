from fastapi import APIRouter, Body

class DebugAPI:
    def __init__(self, agent):
        self.agent = agent
        self.router = APIRouter()

        # 解析意图
        @self.router.post("/debug/parse_intent")
        async def parse_intent(text: str = Body(...)):
            return await self.agent.parser.parse(text)

        # 查看对话上下文
        @self.router.get("/debug/conversation_state")
        async def conversation_state():
            return self.agent.conversation_context

        # 查看数据库所有事件
        @self.router.get("/debug/calendar_events")
        async def calendar_events():
            return {"events": self.agent.calendar_interface.get_all_events()}

        # 测试用例运行
        @self.router.post("/debug/run_test_case")
        async def run_test_case(data: dict = Body(...)):
            user_input = data.get("input")
            expected_intent = data.get("expected_intent")
            actual_reply = await self.agent.process_input(user_input)
            return {
                "input": user_input,
                "expected_intent": expected_intent,
                "actual_result": actual_reply
            }
