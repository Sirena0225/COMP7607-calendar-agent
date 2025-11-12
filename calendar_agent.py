import asyncio
import re
from uuid import uuid4
from typing import Callable, Optional
from nlp_parser import LLMParser
from database import SQLiteCalendar
from config import APIConfig
from models import CalendarEvent, ParsedIntent, IntentType
from datetime import datetime, timedelta

class CalendarAgent:
    def __init__(self, calendar_interface: SQLiteCalendar):
        self.calendar = calendar_interface
        self.nlp_parser = LLMParser()
        self.conversation_context = {}
    
    async def process_input(self, user_input: str) -> str:
        """处理用户输入"""
        try:
            parsed_intent = self.nlp_parser.parse(user_input)
            
            print(f"[DEBUG] 意图类型: {parsed_intent.intent_type.value}")
            print(f"[DEBUG] 实体信息: {parsed_intent.entities}")
            
            if parsed_intent.confidence < 0.3:
                return "抱歉，我没有理解您的意思。您可以告诉我需要添加、修改或查询日程。"
            
            response = await self.execute_intent(parsed_intent)
            return response
            
        except Exception as e:
            print(f"[ERROR] 处理输入时出错: {e}")
            return f"处理过程中出现错误: {str(e)}"
    
    async def execute_intent(self, parsed_intent: ParsedIntent) -> str:
        """执行解析后的意图"""
        intent_type = parsed_intent.intent_type
        print(f"[DEBUG] 执行意图: {intent_type.value}")
        
        if intent_type == IntentType.ADD_EVENT:
            return await self.handle_add_event(parsed_intent)
        elif intent_type == IntentType.MODIFY_EVENT:
            return await self.handle_modify_event(parsed_intent)
        elif intent_type == IntentType.DELETE_EVENT:
            return await self.handle_delete_event(parsed_intent)
        elif intent_type == IntentType.QUERY_EVENTS:
            return await self.handle_query_events(parsed_intent)
        elif intent_type == IntentType.LIST_EVENTS:
            return await self.handle_list_events(parsed_intent)
        elif intent_type == IntentType.CONFIRM_ACTION:
            return await self.handle_confirm_action(parsed_intent)
        elif intent_type == IntentType.HELP:
            return self.handle_help(parsed_intent)
        else:
            return f"抱歉，我暂时无法处理这个请求。意图类型: {intent_type.value}"
    
    async def handle_add_event(self, parsed_intent: ParsedIntent) -> str:
        """处理添加事件"""
        print(f"[DEBUG] 处理添加事件，实体: {parsed_intent.entities}")
        
        entities = parsed_intent.entities
        
        # 从LLM解析的实体中提取信息
        title = entities.get('title', self._extract_title_from_text(parsed_intent.original_text))
        location = entities.get('location', self._extract_location_from_text(parsed_intent.original_text))
        description = entities.get('description', '')
        
        # 解析时间 - 先尝试从LLM实体获取，如果失败则从原始文本解析
        start_time = None
        end_time = None
        
        start_time_str = entities.get('start_time')
        if start_time_str and start_time_str.strip():
            try:
                start_time = datetime.fromisoformat(start_time_str)
            except:
                print(f"[DEBUG] LLM时间解析失败: {start_time_str}")
        
        if not start_time:
            # 从原始文本解析时间
            start_time, end_time = self._extract_datetime_from_text(parsed_intent.original_text)
        
        if not start_time:
            # 如果时间解析失败，询问用户
            self.conversation_context['pending_intent'] = parsed_intent
            self.conversation_context['pending_action'] = 'add_event'
            return f"请告诉我事件的时间，例如：'明天下午3点'。当前解析的标题是：{title}，地点：{location}"
        
        if not end_time:
            end_time = start_time + timedelta(hours=1)  # 默认1小时
        
        # 创建事件
        event = CalendarEvent(
            id=str(uuid4()),
            title=title,
            start_time=start_time,
            end_time=end_time,
            description=description,
            location=location
        )
        
        # 询问确认
        confirm_msg = f"即将添加事件：\n标题：{event.title}\n时间：{event.start_time.strftime('%Y-%m-%d %H:%M')}\n地点：{event.location}\n确认吗？"
        
        self.conversation_context['pending_event'] = event
        self.conversation_context['pending_action'] = 'add'
        
        return confirm_msg
    
    def _extract_title_from_text(self, text: str) -> str:
        """从文本中提取标题（备用方法）"""
        # 查找关键词后的文本
        keywords = ['参加', '会议', '讨论会', '约会', '活动', '讲座', '培训']
        for keyword in keywords:
            if keyword in text:
                start_idx = text.find(keyword) + len(keyword)
                title = text[start_idx:].strip()
                if title:
                    return title.strip('在，。！？')
        return '未命名事件'
    
    def _extract_location_from_text(self, text: str) -> str:
        """从文本中提取地点（备用方法）"""
        # 匹配 "在...教室" 或 "在...会议室" 等模式
        location_patterns = [
            r'在(.+?)[教室|会议室|办公室|地点|地方]',
            r'于(.+?)[教室|会议室|办公室|地点|地方]',
        ]
        
        for pattern in location_patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1).strip()
        
        return ''
    
    def _extract_datetime_from_text(self, text: str):
        """从文本中提取日期时间（备用方法）"""
        import re
        from datetime import datetime, timedelta
        
        text_lower = text.lower()
        
        # 匹配 "明天下午三点" 等相对时间
        if '明天' in text_lower:
            base_date = (datetime.now() + timedelta(days=1)).date()
            
            # 匹配 "下午三点" 或 "3点"
            time_match = re.search(r'(上午|下午|晚上)?(\d{1,2})[点时](\d{2})?', text_lower)
            if time_match:
                period, hour, minute = time_match.groups()
                hour = int(hour)
                minute = int(minute) if minute else 0
                
                # 处理上午下午转换
                if period == '下午' and hour <= 12:
                    hour += 12
                elif period == '晚上' and hour <= 12:
                    hour += 12
                elif period == '上午' and hour == 12:
                    hour = 0  # 12点上午是0点
                
                start_time = datetime.combine(base_date, datetime.min.time().replace(hour=hour, minute=minute))
                return start_time, start_time + timedelta(hours=1)
        
        # 匹配 "今天下午三点" 等
        elif '今天' in text_lower:
            base_date = datetime.now().date()
            time_match = re.search(r'(上午|下午|晚上)?(\d{1,2})[点时](\d{2})?', text_lower)
            if time_match:
                period, hour, minute = time_match.groups()
                hour = int(hour)
                minute = int(minute) if minute else 0
                
                if period == '下午' and hour <= 12:
                    hour += 12
                elif period == '晚上' and hour <= 12:
                    hour += 12
                elif period == '上午' and hour == 12:
                    hour = 0
                
                start_time = datetime.combine(base_date, datetime.min.time().replace(hour=hour, minute=minute))
                return start_time, start_time + timedelta(hours=1)
        
        # 匹配 "下午三点" 等绝对时间（今天）
        else:
            time_match = re.search(r'(上午|下午|晚上)?(\d{1,2})[点时](\d{2})?', text_lower)
            if time_match:
                period, hour, minute = time_match.groups()
                hour = int(hour)
                minute = int(minute) if minute else 0
                
                if period == '下午' and hour <= 12:
                    hour += 12
                elif period == '晚上' and hour <= 12:
                    hour += 12
                elif period == '上午' and hour == 12:
                    hour = 0
                
                start_time = datetime.combine(datetime.now().date(), datetime.min.time().replace(hour=hour, minute=minute))
                return start_time, start_time + timedelta(hours=1)
        
        return None, None
    
    async def handle_query_events(self, parsed_intent: ParsedIntent) -> str:
        """处理查询事件"""
        print(f"[DEBUG] 处理查询事件")
        
        start_date = datetime.now()
        end_date = start_date + timedelta(days=7)
        
        events = await self.calendar.list_events(start_date, end_date)
        
        if not events:
            return "在指定时间范围内没有找到事件。"
        
        result = "找到以下事件：\n"
        for i, event in enumerate(events, 1):
            result += f"{i}. {event.title} - {event.start_time.strftime('%m-%d %H:%M')}\n"
        
        return result
    
    async def handle_list_events(self, parsed_intent: ParsedIntent) -> str:
        """处理列出事件"""
        print(f"[DEBUG] 处理列出事件")
        
        start_date = datetime.now()
        end_date = start_date + timedelta(days=7)
        
        events = await self.calendar.list_events(start_date, end_date)
        
        if not events:
            return "未来7天内没有安排事件。"
        
        result = "未来7天的日程安排：\n"
        for i, event in enumerate(events, 1):
            result += f"{i}. {event.title} - {event.start_time.strftime('%m-%d %H:%M')}\n"
        
        return result
    
    async def handle_confirm_action(self, parsed_intent: ParsedIntent) -> str:
        """处理确认操作"""
        print(f"[DEBUG] 处理确认操作")
        
        if 'pending_event' in self.conversation_context:
            pending_event = self.conversation_context['pending_event']
            action = self.conversation_context.get('pending_action')
            
            print(f"[DEBUG] 待确认操作: {action}")
            
            if action == 'add':
                success = await self.calendar.add_event(pending_event)
                if success:
                    del self.conversation_context['pending_event']
                    del self.conversation_context['pending_action']
                    return f"事件 '{pending_event.title}' 已成功添加！"
                else:
                    return "添加事件失败，请重试。"
        
        return "没有待确认的操作。"
    
    def handle_help(self, parsed_intent: ParsedIntent) -> str:
        """处理帮助请求"""
        return """
我可以帮您管理日程，支持以下操作：
- 添加事件：如"明天下午3点开会"
- 查询日程：如"今天有什么安排"
- 列出日程：如"显示本周日程"
- 修改事件：如"修改明天的会议时间"
- 删除事件：如"删除明天的会议"

请输入您的需求，我会帮您处理。
        """
    
    async def handle_modify_event(self, parsed_intent: ParsedIntent) -> str:
        """处理修改事件"""
        return "正在处理事件修改..."
    
    async def handle_delete_event(self, parsed_intent: ParsedIntent) -> str:
        """处理删除事件"""
        return "正在处理事件删除..."