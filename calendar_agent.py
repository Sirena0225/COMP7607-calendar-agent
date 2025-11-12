import asyncio
import re
from uuid import uuid4
from typing import Callable, Optional
from nlp_parser import LLMParser
from database import SQLiteCalendar
from config import APIConfig
from models import CalendarEvent, ParsedIntent, IntentType
from datetime import datetime, timedelta
from google_calendar_sync import GoogleCalendarSync

class CalendarAgent:
    def __init__(self, calendar_interface: SQLiteCalendar):
        self.calendar = calendar_interface
        self.nlp_parser = LLMParser()
        self.conversation_context = {}
        
        # 初始化Google Calendar同步
        try:
            self.google_calendar = GoogleCalendarSync()
            self.google_sync_enabled = True
            print("✓ Google Calendar同步已启用")
        except:
            self.google_calendar = None
            self.google_sync_enabled = False
            print("⚠ Google Calendar同步未配置")
    
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
        elif intent_type == IntentType.CANCEL_ACTION:
            return await self.handle_cancel_action(parsed_intent)
        elif intent_type == IntentType.HELP:
            return self.handle_help(parsed_intent)
        else:
            return f"抱歉，我暂时无法处理这个请求。意图类型: {intent_type.value}"
    
    async def handle_delete_event(self, parsed_intent: ParsedIntent) -> str:
        """处理删除事件"""
        print(f"[DEBUG] 处理删除事件，实体: {parsed_intent.entities}")
        
        original_text = parsed_intent.original_text.lower()
        
        # 检查是否是删除特定时间范围的事件
        if '明天' in original_text or '明天的所有' in original_text:
            # 删除明天的所有事件
            start_date = datetime.combine((datetime.now() + timedelta(days=1)).date(), datetime.min.time())
            end_date = datetime.combine((datetime.now() + timedelta(days=1)).date(), datetime.max.time())
            
            print(f"[DEBUG] 准备删除时间范围: {start_date} 到 {end_date}")
            
            # 获取要删除的事件
            events_to_delete = await self.calendar.list_events(start_date, end_date)
            
            if not events_to_delete:
                return "明天没有安排事件，无需删除。"
            
            # 存储待删除的事件ID到上下文
            self.conversation_context['events_to_delete'] = [event.id for event in events_to_delete]
            self.conversation_context['delete_range'] = (start_date, end_date)
            
            confirm_msg = f"找到 {len(events_to_delete)} 个明天的事件，确认删除吗？\n"
            for i, event in enumerate(events_to_delete, 1):
                confirm_msg += f"{i}. {event.title} - {event.start_time.strftime('%H:%M')}\n"
            
            return confirm_msg + "\n请输入'确认'删除或'取消'。"
        
        elif '今天' in original_text:
            # 删除今天的事件
            start_date = datetime.combine(datetime.now().date(), datetime.min.time())
            end_date = datetime.combine(datetime.now().date(), datetime.max.time())
            
            events_to_delete = await self.calendar.list_events(start_date, end_date)
            
            if not events_to_delete:
                return "今天没有安排事件，无需删除。"
            
            self.conversation_context['events_to_delete'] = [event.id for event in events_to_delete]
            self.conversation_context['delete_range'] = (start_date, end_date)
            
            confirm_msg = f"找到 {len(events_to_delete)} 个今天的事件，确认删除吗？\n"
            for i, event in enumerate(events_to_delete, 1):
                confirm_msg += f"{i}. {event.title} - {event.start_time.strftime('%H:%M')}\n"
            
            return confirm_msg + "\n请输入'确认'删除或'取消'。"
        
        else:
            # 删除特定事件（需要更多信息）
            return "请指定要删除的事件时间，例如：'删除明天的会议' 或 '删除明天下午3点的讨论会'。"
    
    async def handle_confirm_action(self, parsed_intent: ParsedIntent) -> str:
        """处理确认操作"""
        print(f"[DEBUG] 处理确认操作")
        
        # 检查是否有待删除的事件
        if 'events_to_delete' in self.conversation_context:
            event_ids = self.conversation_context['events_to_delete']
            delete_range = self.conversation_context['delete_range']
            
            success_count = 0
            for event_id in event_ids:
                success = await self.calendar.delete_event(event_id)
                if success:
                    success_count += 1
            
            # 清除上下文
            self.conversation_context.pop('events_to_delete', None)
            self.conversation_context.pop('delete_range', None)
            
            return f"成功删除 {success_count} 个事件。"
        
        # 原有的添加事件确认逻辑
        elif 'pending_event' in self.conversation_context:
            pending_event = self.conversation_context['pending_event']
            action = self.conversation_context.get('pending_action')
            
            print(f"[DEBUG] 待确认操作: {action}")
            print(f"[DEBUG] 待确认事件: {pending_event.title} at {pending_event.start_time}")
            
            if action == 'add':
                success = await self.calendar.add_event(pending_event)
                if success:
                    # 如果Google Calendar同步启用，也同步到Google
                    if self.google_sync_enabled and self.google_calendar:
                        sync_success = self.google_calendar.sync_event_to_google(pending_event)
                        if sync_success:
                            print(f"✓ 事件已同步到Google Calendar")
                    
                    del self.conversation_context['pending_event']
                    del self.conversation_context['pending_action']
                    return f"事件 '{pending_event.title}' 已成功添加！"
                else:
                    return "添加事件失败，请重试。"
        elif 'pending_action' in self.conversation_context and self.conversation_context['pending_action'] == 'add_event':
            return "请重新输入事件信息，我会尝试再次解析。"
        
        return "没有待确认的操作。"
    
    async def handle_add_event(self, parsed_intent: ParsedIntent) -> str:
        """处理添加事件"""
        print(f"[DEBUG] 处理添加事件，实体: {parsed_intent.entities}")
        
        entities = parsed_intent.entities
        
        # 从LLM解析的实体中提取信息
        title = entities.get('title', self._extract_title_from_text(parsed_intent.original_text))
        location = entities.get('location', self._extract_location_from_text(parsed_intent.original_text))
        description = entities.get('description', '')
        
        # 解析时间
        start_time = None
        end_time = None
        
        start_time_str = entities.get('start_time')
        if start_time_str and start_time_str.strip():
            try:
                start_time = datetime.fromisoformat(start_time_str) if hasattr(datetime, 'fromisoformat') else self._parse_datetime(start_time_str)
            except:
                print(f"[DEBUG] LLM时间解析失败: {start_time_str}")
        
        if not start_time:
            start_time, end_time = self._extract_datetime_from_text(parsed_intent.original_text)
        
        if not start_time:
            self.conversation_context['pending_intent'] = parsed_intent
            self.conversation_context['pending_action'] = 'add_event'
            return f"请告诉我事件的时间，例如：'明天下午3点'。当前解析的标题是：{title}，地点：{location}"
        
        if not end_time:
            end_time = start_time + timedelta(hours=1)
        
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
    
    async def handle_query_events(self, parsed_intent: ParsedIntent) -> str:
        """处理查询事件"""
        print(f"[DEBUG] 处理查询事件")
        
        # 根据用户输入确定查询时间范围
        original_text = parsed_intent.original_text.lower()
        
        if '今天' in original_text:
            start_date = datetime.combine(datetime.now().date(), datetime.min.time())
            end_date = datetime.combine(datetime.now().date(), datetime.max.time())
        elif '明天' in original_text:
            tomorrow = datetime.now().date() + timedelta(days=1)
            start_date = datetime.combine(tomorrow, datetime.min.time())
            end_date = datetime.combine(tomorrow, datetime.max.time())
        elif '本周' in original_text or '这周' in original_text:
            # 本周（从今天到7天后）
            start_date = datetime.combine(datetime.now().date(), datetime.min.time())
            end_date = start_date + timedelta(days=7)
        elif '下周' in original_text:
            # 下周
            next_week_start = datetime.now().date() + timedelta(days=7)
            start_date = datetime.combine(next_week_start, datetime.min.time())
            end_date = start_date + timedelta(days=7)
        else:
            # 默认查询未来7天
            start_date = datetime.combine(datetime.now().date(), datetime.min.time())
            end_date = start_date + timedelta(days=7)
        
        print(f"[DEBUG] 查询时间范围: {start_date} 到 {end_date}")
        
        events = await self.calendar.list_events(start_date, end_date)
        
        if not events:
            return f"在指定时间范围内没有找到事件（{start_date.strftime('%m-%d')} 到 {end_date.strftime('%m-%d')}）。"
        
        result = f"在{start_date.strftime('%m-%d')}到{end_date.strftime('%m-%d')}期间找到以下事件：\n"
        for i, event in enumerate(events, 1):
            result += f"{i}. {event.title} - {event.start_time.strftime('%m-%d %H:%M')}\n"
        
        return result
    
    async def handle_list_events(self, parsed_intent: ParsedIntent) -> str:
        """处理列出事件"""
        print(f"[DEBUG] 处理列出事件")
        
        # 根据用户输入确定时间范围
        original_text = parsed_intent.original_text.lower()
        
        if '今天' in original_text:
            start_date = datetime.combine(datetime.now().date(), datetime.min.time())
            end_date = datetime.combine(datetime.now().date(), datetime.max.time())
        elif '明天' in original_text:
            tomorrow = datetime.now().date() + timedelta(days=1)
            start_date = datetime.combine(tomorrow, datetime.min.time())
            end_date = datetime.combine(tomorrow, datetime.max.time())
        else:
            # 默认列出今天和未来7天的事件
            start_date = datetime.combine(datetime.now().date(), datetime.min.time())
            end_date = start_date + timedelta(days=7)
        
        print(f"[DEBUG] 列出事件时间范围: {start_date} 到 {end_date}")
        
        events = await self.calendar.list_events(start_date, end_date)
        
        if not events:
            return f"在指定时间范围内没有安排事件（{start_date.strftime('%m-%d')} 到 {end_date.strftime('%m-%d')}）。"
        
        result = f"{start_date.strftime('%m-%d')}到{end_date.strftime('%m-%d')}的日程安排：\n"
        for i, event in enumerate(events, 1):
            result += f"{i}. {event.title} - {event.start_time.strftime('%m-%d %H:%M')}\n"
        
        return result
    
    def _extract_title_from_text(self, text: str) -> str:
        """从文本中提取标题"""
        keywords = ['参加', '会议', '讨论会', '约会', '活动', '讲座', '培训']
        for keyword in keywords:
            if keyword in text:
                start_idx = text.find(keyword) + len(keyword)
                title = text[start_idx:].strip()
                if title:
                    return title.strip('在，。！？')
        return '未命名事件'
    
    def _extract_location_from_text(self, text: str) -> str:
        """从文本中提取地点"""
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
        """从文本中提取日期时间"""
        import re
        from datetime import datetime, timedelta
        
        text_lower = text.lower()
        
        if '明天' in text_lower:
            base_date = (datetime.now() + timedelta(days=1)).date()
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
    
    def _parse_datetime(self, datetime_str: str) -> datetime:
        """解析日期时间字符串 - 兼容旧版本Python"""
        try:
            # 尝试使用 fromisoformat (Python 3.7+)
            if hasattr(datetime, 'fromisoformat'):
                return datetime.fromisoformat(datetime_str)
            else:
                # 对于旧版本Python，使用其他方法解析
                import dateutil.parser
                return dateutil.parser.parse(datetime_str)
        except:
            # 如果都失败，尝试手动解析
            try:
                # 常见的ISO格式: 2024-01-15 14:30:00
                return datetime.strptime(datetime_str, '%Y-%m-%d %H:%M:%S.%f')
            except:
                try:
                    return datetime.strptime(datetime_str, '%Y-%m-%d %H:%M:%S')
                except:
                    # 最后尝试解析日期部分
                    return datetime.strptime(datetime_str.split(' ')[0], '%Y-%m-%d')
    
    async def handle_cancel_action(self, parsed_intent: ParsedIntent) -> str:
        """处理取消操作"""
        print(f"[DEBUG] 处理取消操作")
        
        if 'pending_event' in self.conversation_context or 'pending_action' in self.conversation_context:
            self.conversation_context.clear()
            return "操作已取消。"
        
        return "没有待取消的操作。"
    
    def handle_help(self, parsed_intent: ParsedIntent) -> str:
        """处理帮助请求"""
        return """
我可以帮您管理日程，支持以下操作：
- 添加事件：如"明天下午3点开会"
- 查询日程：如"今天有什么安排"、"明天的日程"、"本周日程"
- 列出日程：如"显示本周日程"、"列出明天的日程"
- 删除事件：如"删除明天的日程"、"删除今天的会议"
- 修改事件：如"修改明天的会议时间"

请输入您的需求，我会帮您处理。
        """
    
    async def handle_modify_event(self, parsed_intent: ParsedIntent) -> str:
        """处理修改事件"""
        return "正在处理事件修改..."