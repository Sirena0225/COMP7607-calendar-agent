import re
from uuid import uuid4
from typing import Callable, Optional
from nlp_parser import LLMParser
from database import SQLiteCalendar
from config import APIConfig
from models import CalendarEvent, ParsedIntent, IntentType, UserProfile, WorkoutPlan
from datetime import datetime, timedelta
import os
from conflict_resolver import ConflictResolver


class CalendarAgent:
    def __init__(self, calendar_interface: SQLiteCalendar):
        self.calendar = calendar_interface
        self.nlp_parser = LLMParser()
        self.conversation_context = {}
        self.conversation_timeout = 30 * 60  # 30分钟超时
        self.last_interaction_time = None
        self.google_calendar = None
        self.google_sync_enabled = False

        # 🏋️ 新增：训练计划生成器
        self.workout_generator = WorkoutPlanGenerator()

        # 🛠️ 新增：冲突解析器
        self.conflict_resolver = ConflictResolver(calendar_interface)

        # 🛠️ 修复：先初始化基础组件，再初始化Google Calendar
        print("初始化基础组件...")


    def _cleanup_expired_conversation(self):
        """清理过期的对话上下文"""
        if self.last_interaction_time:
            current_time = datetime.now()
            time_diff = (current_time - self.last_interaction_time).total_seconds()
            if time_diff > self.conversation_timeout:
                print(f"[DEBUG] 清理过期的对话上下文")
                self.conversation_context.clear()

    def _is_in_workout_plan_conversation(self) -> bool:
        """检查是否在训练计划对话中"""
        return ('workout_plan_stage' in self.conversation_context and
                self.conversation_context['workout_plan_stage'] not in ['completed', 'confirmation'])

    async def process_input(self, user_input: str) -> str:
        """处理用户输入"""
        try:
            # 🏋️ 修复：清理过期对话
            self._cleanup_expired_conversation()
            self.last_interaction_time = datetime.now()

            # 🏋️ 修复：首先检查是否有待确认的训练计划
            if 'pending_workout_plan' in self.conversation_context:
                # 检查用户输入是否是确认或取消
                if user_input.strip() in ['确认', '确定', '是的', '好的', '是']:
                    # 创建确认意图
                    confirm_intent = ParsedIntent(
                        intent_type=IntentType.CONFIRM_ACTION,
                        entities={'action': 'confirm', 'raw_text': user_input},
                        confidence=1.0,
                        original_text=user_input
                    )
                    return await self.handle_confirm_action(confirm_intent)
                elif user_input.strip() in ['取消', '不要', '不是', '否', '不']:
                    # 创建取消意图
                    cancel_intent = ParsedIntent(
                        intent_type=IntentType.CANCEL_ACTION,
                        entities={'action': 'cancel', 'raw_text': user_input},
                        confidence=1.0,
                        original_text=user_input
                    )
                    return await self.handle_cancel_action(cancel_intent)


            # 🏋️ 修复：首先检查是否在训练计划对话中
            if self._is_in_workout_plan_conversation():
                print(f"[DEBUG] 在训练计划对话中，直接继续对话")
                return await self._continue_workout_plan_conversation_directly(user_input)

            parsed_intent = self.nlp_parser.parse(user_input)
            # 如果用户只输入数字且存在可选事件列表，将其视为确认/选择操作（用于选择要删除/修改的事件）
            if user_input.strip().isdigit() and 'available_events' in self.conversation_context:
                parsed_intent = ParsedIntent(
                    intent_type=IntentType.CONFIRM_ACTION,
                    entities={'selection_index': int(user_input.strip())},
                    confidence=1.0,
                    original_text=user_input
                )
            else:
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

    async def _continue_workout_plan_conversation_directly(self, user_input: str) -> str:
        """直接继续训练计划对话（不经过意图解析）"""
        # 🏋️ 修复：检查是否在确认阶段
        if self.conversation_context.get('workout_plan_stage') == 'confirmation':
            # 在确认阶段，让 process_input 处理确认/取消
            return await self.process_input(user_input)

        # 创建一个临时的ParsedIntent对象
        temp_intent = ParsedIntent(
            intent_type=IntentType.CREATE_WORKOUT_PLAN,
            entities={'raw_text': user_input},
            confidence=1.0,
            original_text=user_input
        )

        return await self._continue_workout_plan_conversation(temp_intent)

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
        # 🏋️ 新增：训练计划意图处理
        elif intent_type == IntentType.CREATE_WORKOUT_PLAN:
            return await self.handle_create_workout_plan(parsed_intent)
        elif intent_type == IntentType.DELETE_WORKOUT_PLANS:
            return await self.handle_delete_workout_plans(parsed_intent)
        else:
            return f"抱歉，我暂时无法处理这个请求。意图类型: {intent_type.value}"

    async def handle_modify_event(self, parsed_intent: ParsedIntent) -> str:
        """处理修改事件 - 使用智能标题提取"""
        print(f"[DEBUG] 处理修改事件，实体: {parsed_intent.entities}")
        print(f"[DEBUG] 原始文本: '{parsed_intent.original_text}'")

        original_text = parsed_intent.original_text
        entities = parsed_intent.entities

        # 从文本中提取新的时间
        new_start_time, new_end_time = self._extract_datetime_from_text(original_text)
        print(f"[DEBUG] 解析到新时间: {new_start_time} 到 {new_end_time}")

        if not new_start_time:
            return "请提供新的时间信息，例如：'修改明天的会议到下午5点'"

        # 🛠️ 修复：使用智能标题提取
        event_title = self._extract_event_title_intelligently(original_text, entities)
        print(f"[DEBUG] 最终确定的事件标题: '{event_title}'")

        # 查找需要修改的事件
        search_start = datetime.combine(datetime.now().date(), datetime.min.time())
        search_end = datetime.combine((datetime.now() + timedelta(days=2)).date(), datetime.max.time())

        all_events = await self.calendar.list_events(search_start, search_end)
        print(f"[DEBUG] 在时间范围内找到 {len(all_events)} 个事件")

        # 🛠️ 修复：完全重写事件匹配逻辑
        matching_events = []

        # 首先尝试精确匹配
        exact_matches = []
        partial_matches = []
        time_matches = []

        for event in all_events:
            print(f"[DEBUG] 检查事件: '{event.title}' vs 目标标题: '{event_title}'")

            # 🛠️ 修复：方法1 - 完全相等匹配
            if event_title == event.title:
                exact_matches.append(event)
                print(f"[DEBUG] 完全匹配: '{event.title}'")
                continue

            # 🛠️ 修复：方法2 - 严格包含匹配（双向）
            if event_title in event.title or event.title in event_title:
                partial_matches.append(event)
                print(f"[DEBUG] 包含匹配: '{event.title}'")
                continue

            # 🛠️ 修复：方法3 - 时间精确匹配
            # 从用户输入中提取原事件时间
            original_time, _ = self._extract_original_time_for_matching(original_text)
            if original_time:
                time_diff = abs((event.start_time - original_time).total_seconds())
                if time_diff < 1800:  # 30分钟内的时间匹配
                    time_matches.append(event)
                    print(f"[DEBUG] 时间匹配: '{event.title}' at {event.start_time} (时间差: {time_diff}秒)")
                    continue

        # 🛠️ 修复：优先级匹配：完全匹配 > 包含匹配 > 时间匹配
        if exact_matches:
            matching_events = exact_matches
            print(f"[DEBUG] 使用完全匹配结果: {len(exact_matches)} 个事件")
        elif partial_matches:
            matching_events = partial_matches
            print(f"[DEBUG] 使用包含匹配结果: {len(partial_matches)} 个事件")
        elif time_matches:
            matching_events = time_matches
            print(f"[DEBUG] 使用时间匹配结果: {len(time_matches)} 个事件")
        else:
            print(f"[DEBUG] 所有匹配方法都失败")

        # 🛠️ 修复：如果没有完全匹配，但只有一个事件，直接使用
        if not matching_events and len(all_events) == 1:
            print(f"[DEBUG] 只有一个事件，直接使用: '{all_events[0].title}'")
            matching_events = all_events

        # 🛠️ 修复：如果根据标题没有找到匹配，但用户指定了时间，尝试时间匹配
        if not matching_events:
            # 从原始文本中提取原事件时间
            original_time, _ = self._extract_original_time_from_text(original_text)
            if original_time:
                print(f"[DEBUG] 尝试时间匹配，原时间: {original_time}")
                for event in all_events:
                    time_diff = abs((event.start_time - original_time).total_seconds())
                    if time_diff < 3600:  # 1小时内
                        matching_events.append(event)
                        print(f"[DEBUG] 时间匹配事件: '{event.title}' at {event.start_time}")

        if not matching_events:
            # 显示可用事件让用户选择
            if all_events:
                event_list = "请选择要修改的事件：\n"
                for i, event in enumerate(all_events, 1):
                    event_list += f"{i}. {event.title} - {event.start_time.strftime('%m-%d %H:%M')}\n"
                event_list += "请输入事件编号："

                # 存储上下文以便后续处理
                self.conversation_context['available_events'] = all_events
                self.conversation_context['modify_new_time'] = (new_start_time, new_end_time)
                self.conversation_context['pending_modify_action'] = True

                return event_list
            else:
                return "在近期没有找到可修改的事件。"

        # 如果找到多个匹配事件，询问用户要修改哪个
        if len(matching_events) > 1:
            event_list = "找到多个可能的事件：\n"
            for i, event in enumerate(matching_events, 1):
                event_list += f"{i}. {event.title} - {event.start_time.strftime('%m-%d %H:%M')}\n"
            event_list += "请指定要修改的事件编号："

            # 存储上下文
            self.conversation_context['available_events'] = matching_events
            self.conversation_context['modify_new_time'] = (new_start_time, new_end_time)
            self.conversation_context['pending_modify_action'] = True

            return event_list

        # 找到唯一匹配的事件，准备修改
        target_event = matching_events[0]

        # 存储到上下文，等待用户确认
        self.conversation_context['event_to_modify'] = target_event
        self.conversation_context['new_start_time'] = new_start_time
        self.conversation_context['new_end_time'] = new_end_time or (new_start_time + timedelta(hours=1))

        confirm_msg = f"确认修改事件吗？\n"
        confirm_msg += f"原事件: {target_event.title} - {target_event.start_time.strftime('%m-%d %H:%M')}\n"
        confirm_msg += f"新时间: {new_start_time.strftime('%m-%d %H:%M')}"
        if self.conversation_context['new_end_time']:
            confirm_msg += f" 到 {self.conversation_context['new_end_time'].strftime('%H:%M')}\n"

        return confirm_msg + "请输入'确认'修改或'取消'。"

    def _extract_original_time_for_matching(self, text: str):
        """专门用于事件匹配的原时间提取"""
        import re
        from datetime import datetime, timedelta

        text_lower = text.lower()

        # 🛠️ 修复：精确匹配"下午三点"这样的时间描述
        time_patterns = [
            r'下午(\d+)点', r'上午(\d+)点', r'晚上(\d+)点',
            r'(\d+)点', r'(\d+):(\d+)'
        ]

        for pattern in time_patterns:
            match = re.search(pattern, text_lower)
            if match:
                if '下午' in pattern:
                    hour = int(match.group(1))
                    if hour < 12:
                        hour += 12
                    # 假设是明天下午
                    target_date = datetime.now().date() + timedelta(days=1)
                    return datetime.combine(target_date, datetime.min.time().replace(hour=hour, minute=0)), None
                elif '上午' in pattern:
                    hour = int(match.group(1))
                    if hour == 12:
                        hour = 0
                    target_date = datetime.now().date() + timedelta(days=1)
                    return datetime.combine(target_date, datetime.min.time().replace(hour=hour, minute=0)), None
                elif '晚上' in pattern:
                    hour = int(match.group(1))
                    if hour < 12:
                        hour += 12
                    target_date = datetime.now().date() + timedelta(days=1)
                    return datetime.combine(target_date, datetime.min.time().replace(hour=hour, minute=0)), None
                elif '点' in pattern:
                    hour = int(match.group(1))
                    target_date = datetime.now().date() + timedelta(days=1)
                    return datetime.combine(target_date, datetime.min.time().replace(hour=hour, minute=0)), None

        return None, None

    def _extract_event_title_intelligently(self, text: str, llm_entities: dict) -> str:
        """智能提取事件标题 - 完全重写，精确提取"""
        print(f"[DEBUG] 智能标题提取 - 文本: '{text}', LLM实体: {llm_entities}")

        # 🛠️ 修复：优先使用LLM解析的标题，但需要严格验证
        llm_title = llm_entities.get('title', '').strip()
        if llm_title and llm_title not in ['', '未命名事件', '事件', '日程', '安排']:
            print(f"[DEBUG] 使用LLM解析的标题: '{llm_title}'")
            return llm_title

        # 🛠️ 修复：完全重写本地提取逻辑 - 专注于修改操作
        import re

        # 定义必须匹配的事件关键词
        critical_keywords = ['会议', '讨论会', '研讨会', '约会', '活动', '讲座', '培训',
                             '上课', '课程', '考试', '面试', '面谈', '检查', '诊疗', '预约']

        # 🛠️ 修复：方法1 - 强制查找关键事件词
        for keyword in critical_keywords:
            if keyword in text:
                print(f"[DEBUG] 强制匹配关键事件词: '{keyword}'")
                return keyword

        # 🛠️ 修复：方法2 - 精确的模式匹配（针对修改操作）
        if any(op in text for op in ['修改', '更改', '调整', '更新']):
            print(f"[DEBUG] 检测到修改操作，使用精确模式匹配")

            # 模式1: "修改[时间]的[事件]" - 如"修改下午三点的会议"
            pattern1 = r'(?:修改|更改|调整)(?:明天|今天|后天)?(?:上午|下午|晚上)?(?:\d+点)?(?:\d+分)?的([^时间到为改]+?)(?:时间|到|为|改为|$)'
            match1 = re.search(pattern1, text)
            if match1:
                extracted = match1.group(1).strip()
                # 验证提取的内容是有效的事件标题
                if extracted and any(keyword in extracted for keyword in critical_keywords):
                    for keyword in critical_keywords:
                        if keyword in extracted:
                            print(f"[DEBUG] 模式1提取有效标题: '{keyword}'")
                            return keyword

            # 🛠️ 修复：模式2: "修改[事件]的时间" - 如"修改会议时间"
            pattern2 = r'(?:修改|更改|调整)([^的时间到为改]+?)(?:的时间|时间)'
            match2 = re.search(pattern2, text)
            if match2:
                extracted = match2.group(1).strip()
                if extracted and any(keyword in extracted for keyword in critical_keywords):
                    for keyword in critical_keywords:
                        if keyword in extracted:
                            print(f"[DEBUG] 模式2提取有效标题: '{keyword}'")
                            return keyword

            # 🛠️ 修复：模式3: 从完整句子中提取 - 如"修改明天下午三点的会议时间为4点"
            pattern3 = r'(?:修改|更改|调整).*?(会议|讨论会|研讨会|约会|活动|讲座|培训|上课|课程|考试|面试|面谈|检查|诊疗|预约)'
            match3 = re.search(pattern3, text)
            if match3:
                extracted = match3.group(1).strip()
                if extracted:
                    print(f"[DEBUG] 模式3直接提取标题: '{extracted}'")
                    return extracted

        # 🛠️ 修复：如果以上方法都失败，使用更激进的关键词搜索
        words = re.findall(r'[\u4e00-\u9fff]{2,}', text)  # 匹配中文字符
        for word in words:
            if word in critical_keywords:
                print(f"[DEBUG] 激进搜索找到标题: '{word}'")
                return word

        # 🛠️ 修复：最后的手段 - 基于时间上下文推断
        print(f"[DEBUG] 所有提取方法失败，使用时间推断")
        return '会议'  # 保守的默认值

    def _calculate_title_similarity(self, title1: str, title2: str) -> float:
        """计算两个标题的相似度 - 改进版本"""
        if not title1 or not title2:
            return 0.0

        # 🛠️ 修复：预处理标题
        def preprocess_title(title):
            # 移除常见的修饰词
            modifiers = ['的', '了', '在', '到', '为']
            for mod in modifiers:
                title = title.replace(mod, '')
            return title.strip()

        title1_clean = preprocess_title(title1)
        title2_clean = preprocess_title(title2)

        # 🛠️ 修复：方法1 - 完全匹配
        if title1_clean == title2_clean:
            return 1.0

        # 🛠️ 修复：方法2 - 包含匹配
        if title1_clean in title2_clean or title2_clean in title1_clean:
            return 0.8

        # 🛠️ 修复：方法3 - 字符集合相似度
        set1 = set(title1_clean)
        set2 = set(title2_clean)

        if not set1 or not set2:
            return 0.0

        intersection = set1.intersection(set2)
        union = set1.union(set2)

        jaccard_similarity = len(intersection) / len(union) if union else 0.0

        # 🛠️ 修复：方法4 - 语义相似度（基于常见事件类型）
        event_categories = {
            '会议': ['讨论会', '研讨会', '会谈', '开会'],
            '课程': ['上课', '讲座', '培训', '学习'],
            '约会': ['面谈', '见面', '约见'],
            '活动': ['聚会', '庆典', '仪式']
        }

        for main_category, synonyms in event_categories.items():
            if title1_clean == main_category and title2_clean in synonyms:
                return 0.7
            if title2_clean == main_category and title1_clean in synonyms:
                return 0.7
            if title1_clean in synonyms and title2_clean in synonyms:
                return 0.6

        return jaccard_similarity

    def _extract_original_time_from_text(self, text: str):
        """从修改文本中提取原事件的时间"""
        text_lower = text.lower()

        # 匹配"修改X点Y分的Z"这样的模式
        import re

        # 匹配"下午三点"这样的时间描述
        time_patterns = [
            r'修改(.+?)(?:的|时间)',
            r'把(.+?)(?:的|时间)',
            r'调整(.+?)(?:的|时间)'
        ]

        for pattern in time_patterns:
            match = re.search(pattern, text_lower)
            if match:
                time_part = match.group(1)
                # 从提取的部分中解析时间
                return self._extract_datetime_from_text(time_part)

        return None, None

    def _format_event_list(self, events):
        """格式化事件列表用于显示"""
        if not events:
            return "当前时间范围内没有事件。"

        result = ""
        for i, event in enumerate(events, 1):
            result += f"{i}. {event.title} - {event.start_time.strftime('%m-%d %H:%M')}\n"
        return result

    async def handle_delete_event(self, parsed_intent: ParsedIntent) -> str:
        """处理删除事件"""
        print(f"[DEBUG] 处理删除事件，实体: {parsed_intent.entities}")

        original_text = parsed_intent.original_text.lower()

        # 🛠️ 修复：首先尝试匹配特定时间的事件
        print(f"[DEBUG] 删除事件文本: {original_text}")

        # 🛠️ 修复：从文本中提取要删除事件的时间信息
        delete_start_time, delete_end_time = self._extract_datetime_from_text(original_text)

        if delete_start_time:
            print(f"[DEBUG] 找到要删除的特定时间: {delete_start_time}")

            # 查找该时间附近的事件
            search_start = delete_start_time - timedelta(hours=2)
            search_end = delete_start_time + timedelta(hours=2)

            events_in_range = await self.calendar.list_events(search_start, search_end)
            print(f"[DEBUG] 在时间范围内找到 {len(events_in_range)} 个事件")

            if not events_in_range:
                return f"在 {delete_start_time.strftime('%H:%M')} 附近没有找到事件。"

            # 🛠️ 修复：智能匹配事件
            matching_events = []
            for event in events_in_range:
                # 时间匹配（1小时内）
                time_diff = abs((event.start_time - delete_start_time).total_seconds())
                if time_diff < 3600:  # 1小时内
                    matching_events.append(event)
                    print(f"[DEBUG] 时间匹配事件: {event.title} at {event.start_time}")

            if not matching_events:
                # 如果没有精确时间匹配，显示所有事件让用户选择
                event_list = f"在 {delete_start_time.strftime('%H:%M')} 附近找到以下事件：\n"
                for i, event in enumerate(events_in_range, 1):
                    event_list += f"{i}. {event.title} - {event.start_time.strftime('%H:%M')}\n"
                event_list += "请选择要删除的事件编号，或输入'取消'："

                self.conversation_context['available_events'] = events_in_range
                self.conversation_context['pending_delete_action'] = True
                return event_list

            elif len(matching_events) == 1:
                # 只有一个匹配事件，直接确认删除
                target_event = matching_events[0]
                self.conversation_context['event_to_delete'] = target_event

                confirm_msg = f"确认删除事件吗？\n"
                confirm_msg += f"事件: {target_event.title}\n"
                confirm_msg += f"时间: {target_event.start_time.strftime('%m-%d %H:%M')}\n"
                return confirm_msg + "请输入'确认'删除或'取消'。"

            else:
                # 多个匹配事件，让用户选择
                event_list = "找到多个可能的事件：\n"
                for i, event in enumerate(matching_events, 1):
                    event_list += f"{i}. {event.title} - {event.start_time.strftime('%H:%M')}\n"
                event_list += "请选择要删除的事件编号："

                self.conversation_context['available_events'] = matching_events
                self.conversation_context['pending_delete_action'] = True
                return event_list

        # 🛠️ 修复：原有的批量删除逻辑（当没有特定时间时）
        elif '明天' in original_text and '所有' in original_text:
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

            confirm_msg = f"找到 {len(events_to_delete)} 个明天的事件，确认删除所有吗？\n"
            for i, event in enumerate(events_to_delete, 1):
                confirm_msg += f"{i}. {event.title} - {event.start_time.strftime('%H:%M')}\n"

            return confirm_msg + "\n请输入'确认'删除或'取消'。"

        elif '明天' in original_text:
            # 🛠️ 修复：当只说"明天"但没有特定时间时，显示事件列表让用户选择
            start_date = datetime.combine((datetime.now() + timedelta(days=1)).date(), datetime.min.time())
            end_date = datetime.combine((datetime.now() + timedelta(days=1)).date(), datetime.max.time())

            events_to_delete = await self.calendar.list_events(start_date, end_date)

            if not events_to_delete:
                return "明天没有安排事件，无需删除。"

            event_list = "明天有以下事件：\n"
            for i, event in enumerate(events_to_delete, 1):
                event_list += f"{i}. {event.title} - {event.start_time.strftime('%H:%M')}\n"
            event_list += "请选择要删除的事件编号，或输入'所有'删除全部："

            self.conversation_context['available_events'] = events_to_delete
            self.conversation_context['pending_delete_action'] = True
            return event_list

        elif '今天' in original_text:
            # 类似地修复今天的逻辑
            start_date = datetime.combine(datetime.now().date(), datetime.min.time())
            end_date = datetime.combine(datetime.now().date(), datetime.max.time())

            events_to_delete = await self.calendar.list_events(start_date, end_date)

            if not events_to_delete:
                return "今天没有安排事件，无需删除。"

            event_list = "今天有以下事件：\n"
            for i, event in enumerate(events_to_delete, 1):
                event_list += f"{i}. {event.title} - {event.start_time.strftime('%H:%M')}\n"
            event_list += "请选择要删除的事件编号，或输入'所有'删除全部："

            self.conversation_context['available_events'] = events_to_delete
            self.conversation_context['pending_delete_action'] = True
            return event_list

        else:
            # 🛠️ 修复：提供更明确的提示
            return "请指定要删除的事件时间，例如：'删除明天下午3点的会议' 或 '删除明天的会议'。"

    async def handle_confirm_action(self, parsed_intent: ParsedIntent) -> str:
        """处理确认操作 - 完整版本，增加冲突解决处理"""
        print(f"[DEBUG] 处理确认操作")

        original_text = parsed_intent.original_text.strip()

        # 🛠️ 新增：处理冲突解决中的时间选择
        if 'conflict_info' in self.conversation_context:
            return await self._handle_conflict_resolution(original_text)

        # 🛠️ 新增：处理强制添加
        if original_text in ['强制添加', '仍然添加'] and 'conflict_info' in self.conversation_context:
            conflict_info = self.conversation_context['conflict_info']
            original_event = conflict_info['original_event']

            # 创建实际事件
            event = CalendarEvent(
                id=str(uuid4()),
                title=original_event.title,
                start_time=original_event.start_time,
                end_time=original_event.end_time,
                description=original_event.description,
                location=original_event.location
            )

            # 清理冲突上下文
            self.conversation_context.pop('conflict_info', None)

            # 直接添加事件
            success = await self.calendar.add_event(event)
            if success:
                # Google Calendar同步
                if self.google_sync_enabled and self.google_calendar:
                    sync_success = self.google_calendar.sync_event_to_google(event)
                    if sync_success:
                        print(f"✓ 事件已同步到Google Calendar")

                return f"✅ 已强制添加事件 '{event.title}'！\n⚠️ 注意：该事件与现有事件时间重叠。"
            else:
                return "❌ 添加事件失败，请重试。"

        # 🏋️ 修复：处理训练计划确认
        if 'pending_workout_plan' in self.conversation_context:
            workout_plan = self.conversation_context['pending_workout_plan']

            print(f"[DEBUG] 确认添加训练计划: {workout_plan.id}")

            # 保存训练计划
            success = await self.calendar.add_workout_plan(workout_plan)

            if success:
                # 将训练计划添加到日历
                events_added = await self._add_workout_plan_to_calendar(workout_plan)

                # 🏋️ 修复：标记对话完成
                self.conversation_context['workout_plan_stage'] = 'completed'
                self.conversation_context.pop('pending_workout_plan', None)
                self.conversation_context.pop('user_profile', None)
                self.conversation_context.pop('workout_plan_data', None)

                return (f"✅ 训练计划已成功添加到日历！\n\n"
                        f"📊 计划详情：\n"
                        f"• 持续 {workout_plan.plan_duration} 周\n"
                        f"• 每周训练 {workout_plan.sessions_per_week} 次\n"
                        f"• 每次 {workout_plan.session_duration} 分钟\n"
                        f"• 共添加了 {events_added} 个训练事件\n\n"
                        f"💪 开始您的健身之旅吧！")
            else:
                return "❌ 添加训练计划失败，请重试。"

        # 🛠️ 修复：处理事件选择确认（用户通过数字选择事件后确认）
        if 'pending_modify_action' in self.conversation_context and self.conversation_context['pending_modify_action']:
            print(f"[DEBUG] 处理事件选择确认流程")

            # 检查用户是否已经选择了事件编号
            if 'selected_event_index' in self.conversation_context:
                event_index = self.conversation_context['selected_event_index']
                available_events = self.conversation_context.get('available_events', [])
                new_start_time, new_end_time = self.conversation_context.get('modify_new_time', (None, None))

                print(f"[DEBUG] 事件索引: {event_index}, 可用事件数: {len(available_events)}")

                if (0 <= event_index < len(available_events)) and new_start_time:
                    target_event = available_events[event_index]

                    # 确保结束时间合理
                    if not new_end_time:
                        new_end_time = new_start_time + timedelta(hours=1)

                    print(
                        f"[DEBUG] 准备修改事件: {target_event.title} 从 {target_event.start_time} 到 {new_start_time}")

                    # 创建更新内容
                    updates = {
                        'start_time': new_start_time.isoformat(),
                        'end_time': new_end_time.isoformat()
                    }

                    # 执行修改
                    success = await self.calendar.modify_event(target_event.id, updates)

                    # 清理上下文
                    self.conversation_context.pop('pending_modify_action', None)
                    self.conversation_context.pop('selected_event_index', None)
                    self.conversation_context.pop('available_events', None)
                    self.conversation_context.pop('modify_new_time', None)

                    if success:
                        # 如果Google Calendar同步启用，也同步更新
                        if self.google_sync_enabled and self.google_calendar:
                            # 重新创建事件对象用于同步
                            updated_event = CalendarEvent(
                                id=target_event.id,
                                title=target_event.title,
                                start_time=new_start_time,
                                end_time=new_end_time,
                                description=target_event.description,
                                location=target_event.location,
                                attendees=target_event.attendees
                            )
                            sync_success = self.google_calendar.sync_event_to_google(updated_event)
                            if sync_success:
                                print(f"✓ 事件已同步到Google Calendar")

                        return f"事件 '{target_event.title}' 已成功修改到 {new_start_time.strftime('%Y-%m-%d %H:%M')}！"
                    else:
                        return "修改事件失败，请重试。"
                else:
                    return "事件选择无效，请重新操作。"
            else:
                return "请先选择要修改的事件编号。"

        # 🛠️ 修复：处理数字选择删除事件
        if original_text.isdigit() and 'available_events' in self.conversation_context:
            print(f"[DEBUG] 处理数字事件选择: {original_text}")

            event_index = int(original_text) - 1  # 转换为0-based索引
            available_events = self.conversation_context['available_events']

            if 0 <= event_index < len(available_events):
                # 🛠️ 修复：区分修改和删除操作
                if 'pending_modify_action' in self.conversation_context:
                    # 修改操作
                    target_event = available_events[event_index]
                    new_start_time, new_end_time = self.conversation_context['modify_new_time']

                    # 存储选择的事件索引，等待用户确认
                    self.conversation_context['selected_event_index'] = event_index

                    confirm_msg = f"确认修改事件吗？\n"
                    confirm_msg += f"原事件: {target_event.title} - {target_event.start_time.strftime('%m-%d %H:%M')}\n"
                    confirm_msg += f"新时间: {new_start_time.strftime('%m-%d %H:%M')}"
                    if new_end_time:
                        confirm_msg += f" 到 {new_end_time.strftime('%H:%M')}\n"
                    else:
                        confirm_msg += f" 到 {(new_start_time + timedelta(hours=1)).strftime('%H:%M')}\n"

                    return confirm_msg + "请输入'确认'修改或'取消'。"

                elif 'pending_delete_action' in self.conversation_context:
                    # 🛠️ 新增：删除操作
                    target_event = available_events[event_index]
                    self.conversation_context['event_to_delete'] = target_event

                    confirm_msg = f"确认删除事件吗？\n"
                    confirm_msg += f"事件: {target_event.title}\n"
                    confirm_msg += f"时间: {target_event.start_time.strftime('%m-%d %H:%M')}\n"
                    confirm_msg += "请输入'确认'删除或'取消'。"

                    return confirm_msg
            else:
                return f"无效的选择，请输入1到{len(available_events)}之间的数字。"

        # 检查是否有待修改的事件（直接匹配的情况）
        if 'event_to_modify' in self.conversation_context:
            target_event = self.conversation_context['event_to_modify']
            new_start_time = self.conversation_context['new_start_time']
            new_end_time = self.conversation_context['new_end_time']

            print(f"[DEBUG] 修改事件: {target_event.title} 从 {target_event.start_time} 到 {new_start_time}")

            # 创建更新内容
            updates = {
                'start_time': new_start_time.isoformat(),
                'end_time': new_end_time.isoformat()
            }

            # 执行修改
            success = await self.calendar.modify_event(target_event.id, updates)

            if success:
                # 清除上下文
                self.conversation_context.pop('event_to_modify', None)
                self.conversation_context.pop('new_start_time', None)
                self.conversation_context.pop('new_end_time', None)

                # 如果Google Calendar同步启用，也同步更新
                if self.google_sync_enabled and self.google_calendar:
                    # 重新创建事件对象用于同步
                    updated_event = CalendarEvent(
                        id=target_event.id,
                        title=target_event.title,
                        start_time=new_start_time,
                        end_time=new_end_time,
                        description=target_event.description,
                        location=target_event.location,
                        attendees=target_event.attendees
                    )
                    sync_success = self.google_calendar.sync_event_to_google(updated_event)
                    if sync_success:
                        print(f"✓ 事件已同步到Google Calendar")

                return f"事件 '{target_event.title}' 已成功修改到 {new_start_time.strftime('%Y-%m-%d %H:%M')}！"
            else:
                return "修改事件失败，请重试。"

        # 🛠️ 修复：处理单个事件删除
        if 'event_to_delete' in self.conversation_context:
            target_event = self.conversation_context['event_to_delete']
            success = await self.calendar.delete_event(target_event.id)

            # 清理上下文
            self.conversation_context.pop('event_to_delete', None)
            self.conversation_context.pop('available_events', None)
            self.conversation_context.pop('pending_delete_action', None)

            if success:
                # 如果Google Calendar同步启用，也同步删除
                if self.google_sync_enabled and self.google_calendar:
                    # 这里需要实现Google Calendar的删除同步
                    print(f"[DEBUG] Google Calendar删除同步待实现")

                return f"事件 '{target_event.title}' 已成功删除！"
            else:
                return "删除事件失败，请重试。"

        # 检查是否有待删除的事件（批量删除）
        elif 'events_to_delete' in self.conversation_context:
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

        # 检查是否有待添加的事件
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

                    # 清除上下文
                    self.conversation_context.pop('pending_event', None)
                    self.conversation_context.pop('pending_action', None)

                    return f"事件 '{pending_event.title}' 已成功添加！"
                else:
                    return "添加事件失败，请重试。"

        # 处理待处理的添加事件意图（当时间信息不完整时）
        elif 'pending_action' in self.conversation_context and self.conversation_context[
            'pending_action'] == 'add_event':
            pending_intent = self.conversation_context.get('pending_intent')
            if pending_intent:
                # 重新尝试处理添加事件
                self.conversation_context.pop('pending_action', None)
                self.conversation_context.pop('pending_intent', None)
                return await self.handle_add_event(pending_intent)
            else:
                return "请重新输入事件信息，我会尝试再次解析。"

        # 清理所有未完成的上下文
        else:
            # 清理可能残留的上下文
            keys_to_remove = [
                'pending_modify_action', 'selected_event_index', 'available_events',
                'modify_new_time', 'pending_event', 'pending_action', 'pending_intent',
                'event_to_modify', 'new_start_time', 'new_end_time', 'events_to_delete',
                'delete_range', 'event_to_delete', 'pending_delete_action',
                # 🏋️ 新增：训练计划相关上下文
                'workout_plan_stage', 'workout_plan_data'
            ]
            for key in keys_to_remove:
                self.conversation_context.pop(key, None)

            return "没有待确认的操作。如果您之前有未完成的操作，请重新开始。"

    async def _handle_conflict_resolution(self, user_input: str) -> str:
        """处理冲突解决流程"""
        conflict_info = self.conversation_context['conflict_info']
        alternative_times = conflict_info['alternative_times']
        original_event = conflict_info['original_event']

        # 处理用户选择推荐时间
        if user_input.isdigit():
            choice_index = int(user_input) - 1
            if 0 <= choice_index < len(alternative_times):
                selected_time = alternative_times[choice_index]

                # 创建使用推荐时间的事件
                event_duration = original_event.end_time - original_event.start_time
                new_end_time = selected_time + event_duration

                event = CalendarEvent(
                    id=str(uuid4()),
                    title=original_event.title,
                    start_time=selected_time,
                    end_time=new_end_time,
                    description=original_event.description,
                    location=original_event.location
                )

                # 清理冲突上下文
                self.conversation_context.pop('conflict_info', None)

                # 存储到待确认事件
                self.conversation_context['pending_event'] = event
                self.conversation_context['pending_action'] = 'add'

                return (f"✅ 已选择推荐时间：{selected_time.strftime('%m-%d %H:%M')}\n\n"
                        f"即将添加事件：\n"
                        f"标题：{event.title}\n"
                        f"时间：{event.start_time.strftime('%Y-%m-%d %H:%M')}\n"
                        f"地点：{event.location}\n\n"
                        f"确认添加吗？请输入'确认'或'取消'。")
            else:
                return f"❌ 无效选择，请输入1-{len(alternative_times)}之间的数字。"

        # 处理用户选择原时间
        elif user_input in ['原时间', '使用原时间']:
            # 创建使用原时间的事件
            event = CalendarEvent(
                id=str(uuid4()),
                title=original_event.title,
                start_time=original_event.start_time,
                end_time=original_event.end_time,
                description=original_event.description,
                location=original_event.location
            )

            # 清理冲突上下文
            self.conversation_context.pop('conflict_info', None)

            # 存储到待确认事件
            self.conversation_context['pending_event'] = event
            self.conversation_context['pending_action'] = 'add'

            return (f"⚠️ 您选择了原时间（可能与现有事件冲突）\n\n"
                    f"即将添加事件：\n"
                    f"标题：{event.title}\n"
                    f"时间：{event.start_time.strftime('%Y-%m-%d %H:%M')}\n"
                    f"地点：{event.location}\n\n"
                    f"确认添加吗？请输入'确认'或'取消'。")

        # 处理取消
        elif user_input in ['取消', '不要了']:
            self.conversation_context.pop('conflict_info', None)
            return "❌ 事件添加已取消。"

        else:
            return "❌ 无效输入，请选择推荐时间编号，或输入'原时间'、'取消'。"

    async def handle_add_event(self, parsed_intent: ParsedIntent) -> str:
        """处理添加事件 - 完全使用本地时间解析，增加冲突检测"""
        print(f"[DEBUG] 处理添加事件，实体: {parsed_intent.entities}")

        entities = parsed_intent.entities

        # 🛠️ 修复：完全忽略LLM返回的时间，只使用本地解析
        title = entities.get('title', self._extract_title_from_text(parsed_intent.original_text))
        location = entities.get('location', self._extract_location_from_text(parsed_intent.original_text))
        description = entities.get('description', '')

        # 完全使用本地时间解析，不信任LLM返回的时间
        start_time, end_time = self._extract_datetime_from_text(parsed_intent.original_text)

        print(f"[DEBUG] 本地解析结果 - 开始: {start_time}, 结束: {end_time}")

        if not start_time:
            self.conversation_context['pending_intent'] = parsed_intent
            self.conversation_context['pending_action'] = 'add_event'
            return f"请告诉我事件的具体时间，例如：'明天下午3点'。当前解析的标题是：{title}"

        if not end_time:
            end_time = start_time + timedelta(hours=1)

        # 🛠️ 新增：创建临时事件对象用于冲突检测
        temp_event = CalendarEvent(
            id="temp_conflict_check",
            title=title,
            start_time=start_time,
            end_time=end_time,
            description=description,
            location=location
        )

        # 🛠️ 新增：冲突检测
        conflicting_events = await self.conflict_resolver.find_conflicting_events(temp_event)

        if conflicting_events:
            print(f"[DEBUG] 检测到 {len(conflicting_events)} 个冲突事件")

            # 生成推荐时间
            alternative_times = await self.conflict_resolver.suggest_alternative_times(temp_event, start_time)

            if alternative_times:
                # 🛠️ 修改：不再存储冲突信息到上下文，直接返回提示信息
                conflict_msg = self._format_conflict_message(conflicting_events, alternative_times, temp_event)
                return conflict_msg
            else:
                # 没有找到合适的时间
                conflict_list = "\n".join(
                    [f"• {e.title} ({e.start_time.strftime('%H:%M')}-{e.end_time.strftime('%H:%M')})"
                     for e in conflicting_events])

                return (f"⚠️ 时间冲突警告！\n\n"
                        f"您要添加的事件与以下事件冲突：\n{conflict_list}\n\n"
                        f"在当前时间段附近没有找到合适的替代时间。\n"
                        f"请重新指定一个不同的时间。")

        # 没有冲突，正常创建事件
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

    def _format_conflict_message(self, conflicting_events, alternative_times, original_event) -> str:
        """格式化冲突提示消息 - 修改：移除选择提示"""
        conflict_list = "\n".join([f"• {e.title} ({e.start_time.strftime('%H:%M')}-{e.end_time.strftime('%H:%M')})"
                                   for e in conflicting_events])

        time_suggestions = "\n".join([f"{i + 1}. {time.strftime('%m-%d %H:%M')}"
                                      for i, time in enumerate(alternative_times[:5])])  # 最多显示5个建议

        # 🛠️ 修改：移除选择提示，只提供信息性提示
        return (f"⚠️ 时间冲突检测！\n\n"
                f"您要添加的事件与以下事件冲突：\n{conflict_list}\n\n"
                f"💡 智能推荐以下可用时间：\n{time_suggestions}\n\n"
                f"请参考以上推荐时间重新安排您的事件。")


    async def handle_query_events(self, parsed_intent: ParsedIntent) -> str:
        """处理查询事件"""
        print(f"[DEBUG] 处理查询事件")

        # 根据用户输入确定查询时间范围
        original_text = parsed_intent.original_text.lower()

        # 🛠️ 修复：提取时间段信息
        time_period = self._extract_time_period(original_text)
        print(f"[DEBUG] 提取到时间段: {time_period}")

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

        # 🛠️ 修复：根据时间段过滤事件
        filtered_events = self._filter_events_by_time_period(events, time_period)

        if not filtered_events:
            time_period_desc = self._get_time_period_description(time_period)
            return f"在{start_date.strftime('%m-%d')}{time_period_desc}没有找到事件。"

        # 🛠️ 修复：根据是否有时间段来显示不同的描述
        time_period_desc = self._get_time_period_description(time_period)
        result = f"在{start_date.strftime('%m-%d')}{time_period_desc}找到以下事件：\n"
        for i, event in enumerate(filtered_events, 1):
            result += f"{i}. {event.title} - {event.start_time.strftime('%H:%M')}\n"

        return result

    async def handle_list_events(self, parsed_intent: ParsedIntent) -> str:
        """处理列出事件"""
        print(f"[DEBUG] 处理列出事件")

        # 根据用户输入确定时间范围
        original_text = parsed_intent.original_text.lower()

        # 🛠️ 修复：提取时间段信息
        time_period = self._extract_time_period(original_text)
        print(f"[DEBUG] 提取到时间段: {time_period}")

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
            time_period_desc = self._get_time_period_description(time_period)
            return f"在指定时间范围内没有安排事件（{start_date.strftime('%m-%d')}{time_period_desc}）。"

        # 🛠️ 修复：根据时间段过滤事件
        filtered_events = self._filter_events_by_time_period(events, time_period)

        if not filtered_events:
            time_period_desc = self._get_time_period_description(time_period)
            return f"在{start_date.strftime('%m-%d')}{time_period_desc}没有安排事件。"

        # 🛠️ 修复：根据是否有时间段来显示不同的描述
        time_period_desc = self._get_time_period_description(time_period)
        result = f"{start_date.strftime('%m-%d')}{time_period_desc}的日程安排：\n"
        for i, event in enumerate(filtered_events, 1):
            result += f"{i}. {event.title} - {event.start_time.strftime('%H:%M')}\n"

        return result

    def _extract_time_period(self, text: str) -> str:
        """从文本中提取时间段信息"""
        text_lower = text.lower()

        if '上午' in text_lower or '早上' in text_lower or '早晨' in text_lower:
            return 'morning'
        elif '下午' in text_lower:
            return 'afternoon'
        elif '晚上' in text_lower or '傍晚' in text_lower or '夜间' in text_lower:
            return 'evening'
        elif '中午' in text_lower or '午间' in text_lower:
            return 'noon'
        else:
            return 'all'  # 没有指定时间段

    def _filter_events_by_time_period(self, events, time_period: str):
        """根据时间段过滤事件"""
        if time_period == 'all':
            return events

        filtered_events = []
        for event in events:
            hour = event.start_time.hour

            if time_period == 'morning' and 5 <= hour < 12:  # 早上5点到12点
                filtered_events.append(event)
            elif time_period == 'noon' and 11 <= hour < 14:  # 中午11点到14点
                filtered_events.append(event)
            elif time_period == 'afternoon' and 12 <= hour < 18:  # 下午12点到18点
                filtered_events.append(event)
            elif time_period == 'evening' and (18 <= hour or hour < 5):  # 晚上18点到次日5点
                filtered_events.append(event)

        return filtered_events

    def _get_time_period_description(self, time_period: str) -> str:
        """获取时间段的描述文本"""
        descriptions = {
            'morning': '上午',
            'afternoon': '下午',
            'evening': '晚上',
            'noon': '中午',
            'all': ''
        }
        return descriptions.get(time_period, '')

    def _extract_title_from_text(self, text: str) -> str:
        """从文本中提取标题 - 完全重写，优先使用LLM结果"""
        print(f"[DEBUG] 提取标题的原始文本: {text}")

        # 🛠️ 修复：首先检查文本中明确的事件类型关键词
        event_keywords = ['会议', '讨论会', '研讨会', '约会', '活动', '讲座', '培训',
                          '开会', '面谈', '面试', '预约', '检查', '诊疗', '考试']

        # 直接查找文本中的事件关键词
        for keyword in event_keywords:
            if keyword in text:
                print(f"[DEBUG] 直接找到事件关键词: '{keyword}'")
                return keyword

        # 🛠️ 修复：处理修改操作的智能提取
        if any(keyword in text for keyword in ['修改', '更改', '调整', '更新']):
            print(f"[DEBUG] 检测到修改操作，使用智能提取")

            # 移除操作动词和时间词汇，保留核心内容
            remove_patterns = [
                r'修改', r'更改', r'调整', r'更新', r'改变',
                r'的时间', r'为', r'到', r'改为', r'调整到',
                r'明天', r'今天', r'后天', r'上午', r'下午', r'晚上',
                r'\d+点', r'\d+点钟', r'\d+:\d+'
            ]

            cleaned_text = text
            for pattern in remove_patterns:
                cleaned_text = re.sub(pattern, ' ', cleaned_text)

            # 提取剩余的有意义词汇
            words = [word for word in cleaned_text.split() if len(word) >= 2]
            if words:
                # 取第一个有意义的词作为标题
                title = words[0]
                print(f"[DEBUG] 清理后提取标题: '{title}'")
                return title

        # 🛠️ 修复：最后使用默认标题
        print(f"[DEBUG] 使用默认标题: '会议'")
        return '会议'

    def _extract_event_title_intelligently(self, text: str, llm_entities: dict) -> str:
        """智能提取事件标题 - 优先使用LLM结果，后备本地逻辑"""
        print(f"[DEBUG] 智能标题提取 - 文本: '{text}', LLM实体: {llm_entities}")

        # 🛠️ 修复：优先使用LLM解析的标题
        llm_title = llm_entities.get('title', '').strip()
        if llm_title and llm_title not in ['', '未命名事件']:
            print(f"[DEBUG] 使用LLM解析的标题: '{llm_title}'")
            return llm_title

        # 🛠️ 修复：如果LLM没有提供标题，使用改进的本地提取
        return self._extract_title_from_text(text)

    def _clean_title(self, title: str) -> str:
        """清理标题，移除不必要的字符"""
        if not title:
            return ""

        # 移除常见的无关字符和词汇
        cleanup_patterns = [
            r'^把', r'^的$', r'^这个', r'^那个', r'^我的', r'^我们的',
            r'^一个', r'^这次', r'^下次', r'^明天', r'^今天', r'^后天'
        ]

        cleaned = title.strip()

        # 移除尾部的"的"字
        if cleaned.endswith('的'):
            cleaned = cleaned[:-1]

        # 移除特定模式
        for pattern in cleanup_patterns:
            cleaned = re.sub(pattern, '', cleaned)

        # 移除多余空格
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()

        # 如果清理后为空或过短，返回原标题
        if len(cleaned) < 1:
            return title.strip()

        return cleaned

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
        """从文本中提取日期时间 - 添加调试信息"""
        import re
        from datetime import datetime, timedelta, time, date

        text_lower = text.lower()
        print(f"[DEBUG] 从文本提取时间: {text}")

        # 获取当前时间作为基准
        now = datetime.now()
        print(f"[DEBUG] 当前时间: {now}")

        # 🛠️ 修复：添加中文数字到阿拉伯数字的映射
        chinese_number_map = {
            '一': 1, '二': 2, '三': 3, '四': 4, '五': 5,
            '六': 6, '七': 7, '八': 8, '九': 9, '十': 10,
            '十一': 11, '十二': 12, '十三': 13, '十四': 14, '十五': 15,
            '十六': 16, '十七': 17, '十八': 18, '十九': 19, '二十': 20,
            '二十一': 21, '二十二': 22, '二十三': 23
        }

        def parse_hour_from_text(time_str: str):
            """从时间字符串中解析小时数"""
            time_match = re.search(r'(上午|下午|晚上)?\s*([一二三四五六七八九十\d]{1,3})\s*[点时]半?', time_str)
            if time_match:
                period, hour_str = time_match.groups()
                if hour_str in chinese_number_map:
                    hour = chinese_number_map[hour_str]
                else:
                    try:
                        hour = int(hour_str)
                    except:
                        return None, None

                minute = 0
                if '半' in time_str:
                    minute = 30

                print(f"[DEBUG] 时间解析结果: 时段={period}, 小时={hour}, 分钟={minute}")

                if period == '下午' and hour < 12:
                    hour += 12
                elif period == '晚上' and hour < 12:
                    hour += 12
                elif period == '上午' and hour == 12:
                    hour = 0
                elif not period and hour < 8:
                    hour += 12

                return hour, minute
            return None, None

        # 新增：识别明确的"X月Y日"或"Y号/日"
        md_match = re.search(r'(\d{1,2})\s*月\s*(\d{1,2})\s*[日号]', text_lower)
        day_match = re.search(r'(?<!\d)(\d{1,2})\s*[日号](?!\d)', text_lower)

        if md_match:
            month = int(md_match.group(1))
            day = int(md_match.group(2))
            year = now.year
            # 若指定月份已过，推到下一年
            if month < now.month or (month == now.month and day < now.day):
                year += 1
            try:
                base_date = date(year, month, day)
            except:
                base_date = (now + timedelta(days=1)).date()
            # 解析时段或小时
            hour, minute = parse_hour_from_text(text_lower)
            if hour is not None:
                start_time = datetime.combine(base_date, time(hour=hour, minute=minute))
                return start_time, start_time + timedelta(hours=1)
            # 若没有给出具体小时，但给出了时段关键词，使用默认小时
            if '下午' in text_lower:
                start_time = datetime.combine(base_date, time(hour=15, minute=0))
                return start_time, start_time + timedelta(hours=1)
            if '上午' in text_lower:
                start_time = datetime.combine(base_date, time(hour=9, minute=0))
                return start_time, start_time + timedelta(hours=1)
            if '晚上' in text_lower:
                start_time = datetime.combine(base_date, time(hour=19, minute=0))
                return start_time, start_time + timedelta(hours=1)
            # 无时段和小时则默认上午9点
            start_time = datetime.combine(base_date, time(hour=9, minute=0))
            return start_time, start_time + timedelta(hours=1)

        if day_match:
            day = int(day_match.group(1))
            month = now.month
            year = now.year
            # 若日已过，假定是下个月（考虑年末）
            if day < now.day:
                month += 1
                if month > 12:
                    month = 1
                    year += 1
            try:
                base_date = date(year, month, day)
            except:
                base_date = (now + timedelta(days=1)).date()

            hour, minute = parse_hour_from_text(text_lower)
            if hour is not None:
                start_time = datetime.combine(base_date, time(hour=hour, minute=minute))
                return start_time, start_time + timedelta(hours=1)
            if '下午' in text_lower:
                start_time = datetime.combine(base_date, time(hour=15, minute=0))
                return start_time, start_time + timedelta(hours=1)
            if '上午' in text_lower:
                start_time = datetime.combine(base_date, time(hour=9, minute=0))
                return start_time, start_time + timedelta(hours=1)
            if '晚上' in text_lower:
                start_time = datetime.combine(base_date, time(hour=19, minute=0))
                return start_time, start_time + timedelta(hours=1)

        # 🛠️ 修复：处理"明天"的情况
        if '明天' in text_lower:
            base_date = (now + timedelta(days=1)).date()
            print(f"[DEBUG] 识别为明天，基准日期: {base_date}")

            hour, minute = parse_hour_from_text(text_lower)
            if hour is not None:
                start_time = datetime.combine(base_date, time(hour=hour, minute=minute))
                print(f"[DEBUG] 生成开始时间: {start_time}")
                return start_time, start_time + timedelta(hours=1)

        # 🛠️ 修复：处理"今天"的情况
        elif '今天' in text_lower:
            base_date = now.date()
            hour, minute = parse_hour_from_text(text_lower)
            if hour is not None:
                start_time = datetime.combine(base_date, time(hour=hour, minute=minute))
                return start_time, start_time + timedelta(hours=1)

        # 🛠️ 修复：处理没有日期的情况（默认今天）
        else:
            hour, minute = parse_hour_from_text(text_lower)
            if hour is not None:
                base_date = now.date()
                start_time = datetime.combine(base_date, time(hour=hour, minute=minute))
                return start_time, start_time + timedelta(hours=1)

        return None, None

    def _parse_datetime(self, datetime_str: str) -> datetime:
        """解析日期时间字符串 - 增强版本，处理LLM返回的时间"""
        print(f"[DEBUG] 解析时间字符串: {datetime_str}")

        try:
            # 首先尝试标准ISO格式
            if hasattr(datetime, 'fromisoformat'):
                # 处理带时区的格式
                if 'T' in datetime_str and '+' in datetime_str:
                    # 移除时区信息，只保留本地时间
                    datetime_str = datetime_str.split('+')[0]
                return datetime.fromisoformat(datetime_str)
        except:
            pass

        try:
            # 尝试常见的日期时间格式
            formats = [
                '%Y-%m-%dT%H:%M:%S',  # 2025-04-06T15:00:00
                '%Y-%m-%d %H:%M:%S',  # 2025-04-06 15:00:00
                '%Y-%m-%dT%H:%M',  # 2025-04-06T15:00
                '%Y-%m-%d %H:%M',  # 2025-04-06 15:00
                '%Y-%m-%d',  # 2025-04-06
            ]

            for fmt in formats:
                try:
                    return datetime.strptime(datetime_str, fmt)
                except:
                    continue
        except:
            pass

        try:
            # 使用dateutil.parser作为备选（需要安装：pip install python-dateutil）
            import dateutil.parser
            return dateutil.parser.parse(datetime_str)
        except:
            # 最后尝试：如果是相对时间（如"明天"），使用文本提取
            start_time, _ = self._extract_datetime_from_text(datetime_str)
            if start_time:
                return start_time

        raise ValueError(f"无法解析时间字符串: {datetime_str}")

    async def handle_cancel_action(self, parsed_intent: ParsedIntent) -> str:
        """处理取消操作"""
        print(f"[DEBUG] 处理取消操作")

        # 🏋️ 修复：如果有待确认的训练计划，取消它
        if 'pending_workout_plan' in self.conversation_context:
            print(f"[DEBUG] 取消训练计划创建")
            # 清理训练计划相关上下文
            self.conversation_context.pop('pending_workout_plan', None)
            self.conversation_context.pop('workout_plan_stage', None)
            self.conversation_context.pop('user_profile', None)
            self.conversation_context.pop('workout_plan_data', None)
            return "❌ 训练计划创建已取消。"

        # 清除所有其他上下文
        self.conversation_context.clear()
        return "操作已取消。"

    def handle_help(self, parsed_intent: ParsedIntent) -> str:
        """处理帮助请求"""
        return """
我可以帮您管理日程，支持以下操作：
📅 日历管理：
- 添加事件：如"明天下午3点开会"
- 查询日程：如"今天有什么安排"、"明天的日程"、"本周日程"
- 列出日程：如"显示本周日程"、"列出明天的日程"
- 删除事件：如"删除明天的日程"、"删除今天的会议"
- 修改事件：如"修改明天的会议时间"、"修改研讨会到下午5点"

🏋️ 训练计划：
- 创建训练计划：如"帮我制定训练计划"、"创建健身计划"
- 删除训练计划：如"删除所有训练计划"

请输入您的需求，我会帮您处理。
        """

    # 🏋️ 新增：训练计划处理方法
    async def handle_create_workout_plan(self, parsed_intent: ParsedIntent) -> str:
        """处理创建训练计划"""
        print(f"[DEBUG] 处理创建训练计划，实体: {parsed_intent.entities}")

        # 检查是否已经在收集用户信息
        if self._is_in_workout_plan_conversation():
            return await self._continue_workout_plan_conversation(parsed_intent)

        # 开始新的训练计划对话
        self.conversation_context['workout_plan_stage'] = 'height_weight'
        self.conversation_context['user_profile'] = {}
        self.conversation_context['workout_plan_data'] = {}

        return ("🏋️‍♂️ 我来为您制定个性化的训练计划！\n\n"
                "请按顺序告诉我以下信息：\n"
                "1. 📏 您的身高（厘米）和体重（公斤）\n"
                "   👉 例如：身高175，体重70\n\n"
                "请先告诉我您的身高和体重：")

    async def _continue_workout_plan_conversation(self, parsed_intent: ParsedIntent) -> str:
        """继续训练计划的多轮对话"""
        stage = self.conversation_context['workout_plan_stage']
        user_profile = self.conversation_context['user_profile']
        text = parsed_intent.original_text.strip()

        print(f"[DEBUG] 训练计划对话阶段: {stage}, 输入: {text}")

        if stage == 'height_weight':
            # 解析身高体重
            height, weight = self._extract_height_weight(text)
            if height and weight:
                user_profile['height'] = height
                user_profile['weight'] = weight
                self.conversation_context['workout_plan_stage'] = 'age_gender'
                return ("✅ 已记录：身高{}cm，体重{}kg\n\n"
                        "2. 🎂 您的年龄和性别\n"
                        "   👉 例如：25岁，男\n\n"
                        "请告诉我您的年龄和性别：").format(height, weight)
            else:
                return "❌ 请正确输入身高和体重，例如：身高175，体重70"

        elif stage == 'age_gender':
            # 解析年龄和性别
            age, gender = self._extract_age_gender(text)
            if age and gender:
                user_profile['age'] = age
                user_profile['gender'] = gender
                self.conversation_context['workout_plan_stage'] = 'goal'
                return ("✅ 已记录：{}岁，{}\n\n"
                        "3. 🎯 您的健身目标\n"
                        "   📌 增肌 - 增加肌肉质量和体积\n"
                        "   📌 减脂 - 减少体脂肪\n"
                        "   📌 塑形 - 改善身体线条\n"
                        "   📌 力量提升 - 增加力量水平\n\n"
                        "请选择您的健身目标：").format(age, '男' if gender == 'male' else '女')
            else:
                return "❌ 请正确输入年龄和性别，例如：25岁，男"

        elif stage == 'goal':
            # 解析健身目标
            goal = self._extract_fitness_goal(text)
            if goal:
                user_profile['fitness_goal'] = goal
                self.conversation_context['workout_plan_stage'] = 'body_part'
                goal_desc = self._get_goal_description(goal)
                return ("✅ 已记录：{}\n\n"
                        "4. 💪 是否有特定部位需要加强训练？\n"
                        "   👉 例如：胸肌、腹肌、手臂、背部、腿部\n"
                        "   👉 如果没有，请说'无'或'全身'\n\n"
                        "请告诉我：").format(goal_desc)
            else:
                return "❌ 请选择健身目标：增肌、减脂、塑形或力量提升"

        elif stage == 'body_part':
            # 解析目标部位
            body_part = self._extract_body_part(text)
            user_profile['target_body_part'] = body_part
            self.conversation_context['workout_plan_stage'] = 'frequency'

            body_part_desc = body_part if body_part else '全身'
            return ("✅ 已记录：加强{}训练\n\n"
                    "5. 📅 训练安排\n"
                    "   请按顺序告诉我：\n"
                    "   • 每周训练几次？（数字）\n"
                    "   • 每次训练多长时间？（分钟）\n"
                    "   • 计划持续几周？（数字）\n\n"
                    "👉 例如：3, 60, 8 （表示每周3次，每次60分钟，持续8周）\n\n"
                    "请告诉我您的训练安排：").format(body_part_desc)

        elif stage == 'frequency':
            # 解析训练频率
            sessions, duration, weeks = self._extract_training_frequency(text)
            if sessions and duration and weeks:
                # 验证输入合理性
                if sessions < 1 or sessions > 7:
                    return "❌ 每周训练次数应在1-7次之间，请重新输入："
                if duration < 15 or duration > 180:
                    return "❌ 单次训练时间应在15-180分钟之间，请重新输入："
                if weeks < 1 or weeks > 52:
                    return "❌ 训练周期应在1-52周之间，请重新输入："

                user_profile['sessions_per_week'] = sessions
                user_profile['session_duration'] = duration
                user_profile['plan_duration'] = weeks

                # 生成训练计划
                return await self._generate_and_confirm_workout_plan()
            else:
                return "❌ 请正确输入训练安排，例如：3, 60, 8（表示每周3次，每次60分钟，持续8周）"

        return "❌ 训练计划创建流程出现错误，请重新开始。"

    async def _generate_and_confirm_workout_plan(self) -> str:
        """生成训练计划并请求确认"""
        user_profile_data = self.conversation_context['user_profile']

        # 创建用户档案对象
        user_profile = UserProfile(
            height=user_profile_data['height'],
            weight=user_profile_data['weight'],
            age=user_profile_data['age'],
            gender=user_profile_data['gender'],
            fitness_goal=user_profile_data['fitness_goal'],
            target_body_part=user_profile_data.get('target_body_part', ''),
            experience_level=user_profile_data.get('experience_level', 'beginner')
        )

        # 生成训练计划
        workout_plan = self.workout_generator.generate_workout_plan(
            user_profile=user_profile,
            sessions_per_week=user_profile_data['sessions_per_week'],
            session_duration=user_profile_data['session_duration'],
            plan_duration=user_profile_data['plan_duration']
        )

        # 🏋️ 修复：保存到上下文并标记为待确认状态
        self.conversation_context['pending_workout_plan'] = workout_plan
        self.conversation_context['workout_plan_stage'] = 'confirmation'  # 新增确认阶段

        # 显示计划摘要
        plan_summary = self._format_workout_plan_summary(workout_plan)

        return (f"✅ 已为您生成个性化训练计划！\n\n"
                f"{plan_summary}\n\n"
                f"是否确认将此训练计划添加到日历中？请输入'确认'或'取消'")

    def _format_workout_plan_summary(self, workout_plan: WorkoutPlan) -> str:
        """格式化训练计划摘要"""
        bmi = workout_plan.user_profile.weight / ((workout_plan.user_profile.height / 100) ** 2)

        summary = f"""📊 用户档案：
- 身高：{workout_plan.user_profile.height}cm
- 体重：{workout_plan.user_profile.weight}kg
- BMI：{bmi:.1f}
- 年龄：{workout_plan.user_profile.age}岁
- 性别：{'男' if workout_plan.user_profile.gender == 'male' else '女'}
- 目标：{self._get_goal_description(workout_plan.user_profile.fitness_goal)}
- 训练周期：{workout_plan.plan_duration}周
- 每周训练：{workout_plan.sessions_per_week}次
- 单次时长：{workout_plan.session_duration}分钟

🏋️ 训练安排："""

        for i, workout in enumerate(workout_plan.workouts, 1):
            summary += f"\n\n第{i}次训练：{workout['focus']}"
            for exercise in workout['exercises']:
                summary += f"\n  • {exercise['name']}：{exercise['sets']}组 × {exercise['reps']}次"

        return summary

    def _get_goal_description(self, goal: str) -> str:
        """获取目标描述"""
        goals = {
            'muscle_gain': '增肌',
            'fat_loss': '减脂',
            'body_shaping': '塑形',
            'strength': '力量提升'
        }
        return goals.get(goal, goal)

    # 🏋️ 新增：信息提取方法
    def _extract_height_weight(self, text: str) -> tuple:
        """提取身高体重 - 改进版本"""
        # 多种格式匹配
        patterns = [
            r'身高\s*(\d+(?:\.\d+)?)\s*[,，]?\s*体重\s*(\d+(?:\.\d+)?)',
            r'身高\s*(\d+(?:\.\d+)?)\s*体重\s*(\d+(?:\.\d+)?)',
            r'(\d+(?:\.\d+)?)\s*[,，]?\s*(\d+(?:\.\d+)?)',
            r'高\s*(\d+)\s*重\s*(\d+)'
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                try:
                    height = float(match.group(1))
                    weight = float(match.group(2))
                    # 验证合理性
                    if 100 <= height <= 250 and 30 <= weight <= 200:
                        return height, weight
                except ValueError:
                    continue

        # 如果没有匹配到模式，尝试提取数字
        numbers = re.findall(r'\d+(?:\.\d+)?', text)
        if len(numbers) >= 2:
            try:
                height = float(numbers[0])
                weight = float(numbers[1])
                if 100 <= height <= 250 and 30 <= weight <= 200:
                    return height, weight
            except ValueError:
                pass

        return None, None

    def _extract_age_gender(self, text: str) -> tuple:
        """提取年龄和性别 - 改进版本"""
        # 年龄提取
        age_match = re.search(r'(\d+)\s*岁', text)
        if not age_match:
            # 尝试直接提取数字
            numbers = re.findall(r'\d+', text)
            if numbers:
                age = int(numbers[0])
            else:
                return None, None
        else:
            age = int(age_match.group(1))

        # 性别提取
        if any(word in text for word in ['男', '男性', '男生', '男人', 'male', 'boy']):
            gender = 'male'
        elif any(word in text for word in ['女', '女性', '女生', '女人', 'female', 'girl']):
            gender = 'female'
        else:
            return None, None

        # 验证年龄合理性
        if 10 <= age <= 80:
            return age, gender

        return None, None

    def _extract_fitness_goal(self, text: str) -> str:
        """提取健身目标 - 改进版本"""
        text_lower = text.lower()

        goal_mapping = {
            'muscle_gain': ['增肌', '增重', '长肌肉', '肌肉', '1', '一'],
            'fat_loss': ['减脂', '减肥', '瘦身', '减重', '2', '二'],
            'body_shaping': ['塑形', '塑身', '线条', '体型', '3', '三'],
            'strength': ['力量', '力气', '力量提升', '4', '四']
        }

        for goal, keywords in goal_mapping.items():
            if any(keyword in text_lower for keyword in keywords):
                return goal

        return None

    def _extract_body_part(self, text: str) -> str:
        """提取目标训练部位 - 改进版本"""
        text_lower = text.lower()

        # 如果用户说无或全身，返回空字符串
        if any(word in text_lower for word in ['无', '没有', '全身', '都练', '整体']):
            return ''

        body_part_mapping = {
            '胸': ['胸', '胸部', '胸肌'],
            '背': ['背', '背部', '背肌'],
            '腿': ['腿', '腿部', '下肢'],
            '腹': ['腹', '腹部', '腹肌', '核心'],
            '手臂': ['手臂', '胳膊', '二头', '三头'],
            '肩': ['肩', '肩膀', '肩部']
        }

        for part, keywords in body_part_mapping.items():
            if any(keyword in text_lower for keyword in keywords):
                return part

        return '全身'  # 默认全身训练

    def _extract_training_frequency(self, text: str) -> tuple:
        """提取训练频率 - 改进版本"""
        # 多种格式匹配
        numbers = re.findall(r'\d+', text)

        if len(numbers) >= 3:
            try:
                sessions = int(numbers[0])
                duration = int(numbers[1])
                weeks = int(numbers[2])
                return sessions, duration, weeks
            except ValueError:
                pass

        # 尝试匹配中文描述
        session_match = re.search(r'每周\s*(\d+)\s*次', text)
        duration_match = re.search(r'每次\s*(\d+)\s*分钟', text)
        week_match = re.search(r'持续\s*(\d+)\s*周', text)

        if session_match and duration_match and week_match:
            try:
                sessions = int(session_match.group(1))
                duration = int(duration_match.group(1))
                weeks = int(week_match.group(1))
                return sessions, duration, weeks
            except ValueError:
                pass

        return None, None, None

    async def handle_delete_workout_plans(self, parsed_intent: ParsedIntent) -> str:
        """处理删除所有训练计划"""
        print(f"[DEBUG] 处理删除训练计划")

        # 删除训练计划数据
        success = await self.calendar.delete_workout_plans()

        # 删除训练事件
        events_deleted = await self.calendar.delete_workout_events()

        if success:
            return f"✅ 已成功删除所有训练计划！共删除了 {events_deleted} 个训练事件。"
        else:
            return "❌ 删除训练计划时出现错误，请重试。"

    async def _add_workout_plan_to_calendar(self, workout_plan: WorkoutPlan) -> int:
        """将训练计划添加到日历"""
        events_added = 0
        start_date = workout_plan.start_date

        for week in range(workout_plan.plan_duration):
            for session in range(workout_plan.sessions_per_week):
                # 计算训练日期（例如：周一、周三、周五）
                day_offset = session * (7 // workout_plan.sessions_per_week)
                training_date = start_date + timedelta(days=week * 7 + day_offset)

                # 创建训练事件
                workout = workout_plan.workouts[session % len(workout_plan.workouts)]
                event_title = f"训练：{workout['focus']}"

                event = CalendarEvent(
                    id=str(uuid4()),
                    title=event_title,
                    start_time=training_date.replace(hour=19, minute=0, second=0),  # 晚上7点
                    end_time=training_date.replace(hour=19, minute=0, second=0) +
                             timedelta(minutes=workout_plan.session_duration),
                    description=self._format_workout_description(workout),
                    location="健身房"
                )

                # 添加到日历
                success = await self.calendar.add_event(event)
                if success:
                    events_added += 1

        return events_added

    def _format_workout_description(self, workout: dict) -> str:
        """格式化训练描述"""
        description = f"训练重点：{workout['focus']}\n\n训练内容：\n"
        for exercise in workout['exercises']:
            description += f"• {exercise['name']}: {exercise['sets']}组 × {exercise['reps']}次\n"
        return description


# 🏋️ 新增：训练计划生成器
class WorkoutPlanGenerator:
    """训练计划生成器"""

    def generate_workout_plan(self, user_profile: UserProfile, sessions_per_week: int,
                              session_duration: int, plan_duration: int) -> WorkoutPlan:
        """生成训练计划"""
        from uuid import uuid4
        from datetime import datetime

        workouts = self._generate_workouts(user_profile, sessions_per_week, session_duration)

        return WorkoutPlan(
            id=str(uuid4()),
            user_profile=user_profile,
            plan_duration=plan_duration,
            sessions_per_week=sessions_per_week,
            session_duration=session_duration,
            workouts=workouts,
            created_at=datetime.now(),
            start_date=datetime.now() + timedelta(days=1)  # 从明天开始
        )

    def _generate_workouts(self, user_profile: UserProfile, sessions_per_week: int, session_duration: int) -> list:
        """根据用户档案生成具体训练内容"""
        workouts = []

        # 根据目标生成不同的训练计划
        if user_profile.fitness_goal == 'muscle_gain':
            workouts = self._generate_muscle_gain_workout(user_profile, sessions_per_week)
        elif user_profile.fitness_goal == 'fat_loss':
            workouts = self._generate_fat_loss_workout(user_profile, sessions_per_week)
        elif user_profile.fitness_goal == 'body_shaping':
            workouts = self._generate_body_shaping_workout(user_profile, sessions_per_week)
        else:  # strength
            workouts = self._generate_strength_workout(user_profile, sessions_per_week)

        # 如果有特定部位加强，调整训练计划
        if user_profile.target_body_part:
            workouts = self._adjust_for_target_body_part(workouts, user_profile.target_body_part)

        return workouts

    def _generate_muscle_gain_workout(self, user_profile: UserProfile, sessions: int) -> list:
        """生成增肌训练计划"""
        base_workouts = [
            {
                'focus': '胸肌+三头肌',
                'exercises': [
                    {'name': '卧推', 'sets': 4, 'reps': '8-12'},
                    {'name': '上斜哑铃卧推', 'sets': 3, 'reps': '10-12'},
                    {'name': '哑铃飞鸟', 'sets': 3, 'reps': '12-15'},
                    {'name': '绳索下压', 'sets': 3, 'reps': '12-15'}
                ]
            },
            {
                'focus': '背肌+二头肌',
                'exercises': [
                    {'name': '引体向上', 'sets': 4, 'reps': '力竭'},
                    {'name': '杠铃划船', 'sets': 4, 'reps': '8-12'},
                    {'name': '坐姿划船', 'sets': 3, 'reps': '10-12'},
                    {'name': '哑铃弯举', 'sets': 3, 'reps': '12-15'}
                ]
            },
            {
                'focus': '腿部+肩部',
                'exercises': [
                    {'name': '深蹲', 'sets': 4, 'reps': '8-12'},
                    {'name': '腿举', 'sets': 3, 'reps': '10-12'},
                    {'name': '肩推', 'sets': 4, 'reps': '8-12'},
                    {'name': '侧平举', 'sets': 3, 'reps': '12-15'}
                ]
            }
        ]

        return base_workouts[:sessions]

    def _generate_fat_loss_workout(self, user_profile: UserProfile, sessions: int) -> list:
        """生成减脂训练计划"""
        workouts = [
            {
                'focus': '全身循环训练',
                'exercises': [
                    {'name': '波比跳', 'sets': 4, 'reps': '15-20'},
                    {'name': '登山跑', 'sets': 3, 'reps': '30秒'},
                    {'name': '壶铃摇摆', 'sets': 4, 'reps': '20-25'},
                    {'name': '战绳', 'sets': 3, 'reps': '30秒'}
                ]
            },
            {
                'focus': 'HIIT有氧',
                'exercises': [
                    {'name': '跑步机间歇', 'sets': 1, 'reps': '30分钟'},
                    {'name': '动感单车', 'sets': 1, 'reps': '25分钟'},
                    {'name': '跳绳', 'sets': 5, 'reps': '1分钟'}
                ]
            }
        ]

        # 根据训练次数调整
        if sessions >= 3:
            workouts.append({
                'focus': '力量训练',
                'exercises': [
                    {'name': '深蹲', 'sets': 4, 'reps': '12-15'},
                    {'name': '推举', 'sets': 3, 'reps': '12-15'},
                    {'name': '划船', 'sets': 3, 'reps': '12-15'}
                ]
            })

        return workouts[:sessions]

    def _generate_body_shaping_workout(self, user_profile: UserProfile, sessions: int) -> list:
        """生成塑形训练计划"""
        workouts = [
            {
                'focus': '上半身塑形',
                'exercises': [
                    {'name': '俯卧撑', 'sets': 4, 'reps': '15-20'},
                    {'name': '哑铃肩推', 'sets': 3, 'reps': '12-15'},
                    {'name': '划船', 'sets': 3, 'reps': '12-15'},
                    {'name': '侧平举', 'sets': 3, 'reps': '15-20'}
                ]
            },
            {
                'focus': '下半身塑形',
                'exercises': [
                    {'name': '深蹲', 'sets': 4, 'reps': '15-20'},
                    {'name': '弓步蹲', 'sets': 3, 'reps': '12-15每边'},
                    {'name': '臀推', 'sets': 4, 'reps': '15-20'},
                    {'name': '腿弯举', 'sets': 3, 'reps': '15-20'}
                ]
            },
            {
                'focus': '核心训练',
                'exercises': [
                    {'name': '平板支撑', 'sets': 3, 'reps': '45-60秒'},
                    {'name': '俄罗斯转体', 'sets': 3, 'reps': '20每边'},
                    {'name': '仰卧举腿', 'sets': 3, 'reps': '15-20'},
                    {'name': '鸟狗式', 'sets': 3, 'reps': '12每边'}
                ]
            }
        ]

        return workouts[:sessions]

    def _generate_strength_workout(self, user_profile: UserProfile, sessions: int) -> list:
        """生成力量训练计划"""
        workouts = [
            {
                'focus': '力量训练日1',
                'exercises': [
                    {'name': '深蹲', 'sets': 5, 'reps': '5'},
                    {'name': '卧推', 'sets': 5, 'reps': '5'},
                    {'name': '硬拉', 'sets': 1, 'reps': '5'},
                    {'name': '推举', 'sets': 3, 'reps': '5'}
                ]
            },
            {
                'focus': '力量训练日2',
                'exercises': [
                    {'name': '前蹲', 'sets': 3, 'reps': '5'},
                    {'name': '上斜卧推', 'sets': 5, 'reps': '5'},
                    {'name': '引体向上', 'sets': 5, 'reps': '5'},
                    {'name': '划船', 'sets': 3, 'reps': '5'}
                ]
            }
        ]

        return workouts[:sessions]

    def _adjust_for_target_body_part(self, workouts: list, target_part: str) -> list:
        """根据目标部位调整训练计划"""
        part_exercises = {
            '胸': ['上斜卧推', '哑铃飞鸟', '绳索夹胸'],
            '背': ['引体向上', '杠铃划船', '坐姿划船'],
            '腿': ['深蹲', '腿举', '腿弯举', '弓步蹲'],
            '腹': ['卷腹', '俄罗斯转体', '仰卧举腿', '平板支撑'],
            '手臂': ['哑铃弯举', '绳索下压', '锤式弯举'],
            '肩': ['肩推', '侧平举', '前平举']
        }

        if target_part in part_exercises:
            for workout in workouts:
                # 在每次训练中添加目标部位练习
                workout['exercises'].extend([
                    {'name': exercise, 'sets': 3, 'reps': '12-15'}
                    for exercise in part_exercises[target_part][:2]
                ])

        return workouts