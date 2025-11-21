import re
from datetime import datetime, date, timedelta
from typing import Tuple, Optional, Dict, Any
from models import ParsedIntent, IntentType
from qwen_client import QwenClient


class LLMParser:
    def __init__(self):
        self.qwen_client = QwenClient()

    def parse(self, text: str) -> ParsedIntent:
        """使用Qwen LLM解析用户输入，增加对 '22号/22日' 等日期的识别并返回结构化实体"""
        result = self.qwen_client.parse_intent_with_llm(text)

        # 常用短输入分类词表（供启发式覆盖）
        confirm_short = {'确认', '确定', '是的', '好的', '对', '同意', '是', '接受', 'ok', 'yes', '添加'}
        cancel_short = {'取消', '不要', '不是', '否', '拒绝', '不', 'no'}
        next_short = {'换一个', '重新推荐', '下一个', '再来一个'}

        # 先对LLM输出做常规处理
        if result['success']:
            data = result['data']
            print(f"[DEBUG] LLM解析结果: {data}")

            # 将字符串意图类型转换为枚举
            intent_map = {
                'add_event': IntentType.ADD_EVENT,
                'modify_event': IntentType.MODIFY_EVENT,
                'delete_event': IntentType.DELETE_EVENT,
                'query_events': IntentType.QUERY_EVENTS,
                'list_events': IntentType.LIST_EVENTS,
                'confirm_action': IntentType.CONFIRM_ACTION,
                'cancel_action': IntentType.CANCEL_ACTION,
                'help': IntentType.HELP,
                # 🏋️ 新增训练计划意图
                'create_workout_plan': IntentType.CREATE_WORKOUT_PLAN,
                'delete_workout_plans': IntentType.DELETE_WORKOUT_PLANS,
                # 🎯 新增：任务分解意图
                'breakdown_task': IntentType.BREAKDOWN_TASK
            }

            intent_type_str = data.get('intent_type', 'query_events')
            intent_type = intent_map.get(intent_type_str, IntentType.QUERY_EVENTS)

            entities = data.get('entities', {}) or {}
            confidence = data.get('confidence', 0.5)

            # 启发式覆盖：短输入（数字/确认/取消/换一个/所有）优先使用规则映射，避免LLM误判
            text_strip = text.strip()
            text_lower = text_strip.lower()

            # 优先：数字序号 -> 视为删除选择
            if text_strip.isdigit():
                return ParsedIntent(
                    intent_type=IntentType.DELETE_EVENT,
                    entities={'selection_index': int(text_strip), 'raw_text': text},
                    confidence=0.99,
                    original_text=text,
                    structured_response="启发式覆盖：数字选择"
                )
            # 优先：明确的"所有/全部"
            if text_lower in ['所有', '全部', 'all']:
                return ParsedIntent(
                    intent_type=IntentType.DELETE_EVENT,
                    entities={'delete_all': True, 'raw_text': text},
                    confidence=0.95,
                    original_text=text,
                    structured_response="启发式覆盖：删除全部"
                )
            # 短确认/取消/换一个等，一般为单词或极短句，优先覆盖为确认/取消/下一推荐
            if len(text_strip) <= 6:
                if any(k == text_strip or k.lower() == text_lower for k in confirm_short):
                    return ParsedIntent(
                        intent_type=IntentType.CONFIRM_ACTION,
                        entities={'action': 'confirm', 'raw_text': text},
                        confidence=0.95,
                        original_text=text,
                        structured_response="启发式覆盖：确认操作"
                    )
                if any(k == text_strip or k.lower() == text_lower for k in cancel_short):
                    return ParsedIntent(
                        intent_type=IntentType.CANCEL_ACTION,
                        entities={'action': 'cancel', 'raw_text': text},
                        confidence=0.95,
                        original_text=text,
                        structured_response="启发式覆盖：取消操作"
                    )
                if any(k in text_strip for k in next_short):
                    return ParsedIntent(
                        intent_type=IntentType.CONFIRM_ACTION,
                        entities={'action': 'next_suggestion', 'raw_text': text},
                        confidence=0.90,
                        original_text=text,
                        structured_response="启发式覆盖：下一推荐"
                    )

            # 将 LLM 返回或文本中可能包含的"22号/22日 + 时间段/时刻"抽取为实体，供 agent 使用
            day_time = self._extract_day_time_from_text(text)
            if day_time:
                # 合并实体，不覆盖已有重要实体
                entities = dict(entities)
                entities.update(day_time)

            # 🎯 新增：如果是任务分解意图，尝试提取任务信息
            if intent_type == IntentType.BREAKDOWN_TASK:
                task_info = self._extract_task_info(text)
                if task_info:
                    entities.update(task_info)

            # 无需覆盖，使用LLM解析结果（带上可能新提取的 date/time 实体）
            parsed_intent = ParsedIntent(
                intent_type=intent_type,
                entities=entities,
                confidence=confidence,
                original_text=text,
                structured_response=result.get('raw_response')
            )

            print(f"[DEBUG] 解析意图: {intent_type.value}, 置信度: {confidence}, 额外实体: {day_time}")
            return parsed_intent
        else:
            print(f"[DEBUG] LLM解析失败: {result.get('error', 'Unknown error')}")
            # LLM解析失败时的备用方案
            return self._fallback_parse(text)

    def _fallback_parse(self, text: str) -> ParsedIntent:
        """备用解析方法 - 增强对 'N号/日 + 时间段' 的识别"""
        print(f"[DEBUG] 使用备用解析方法: {text}")

        text_lower = text.lower()
        text_stripped = text.strip()

        # 优先识别用户直接输入的序号或"所有/全部"
        if text_stripped.isdigit():
            intent_type = IntentType.DELETE_EVENT
            confidence = 0.95
            entities = {'selection_index': int(text_stripped), 'raw_text': text}
            return ParsedIntent(
                intent_type=intent_type,
                entities=entities,
                confidence=confidence,
                original_text=text,
                structured_response="数字选择（备用解析）"
            )
        if text_lower in ['所有', '全部', 'all']:
            intent_type = IntentType.DELETE_EVENT
            confidence = 0.9
            entities = {'delete_all': True, 'raw_text': text}
            return ParsedIntent(
                intent_type=intent_type,
                entities=entities,
                confidence=confidence,
                original_text=text,
                structured_response="删除全部（备用解析）"
            )

        # 识别是否包含具体"几号/几日"并据此推断为 添加/删除/查询 等操作
        day_time = self._extract_day_time_from_text(text)
        if day_time:
            # 基于上下文关键词判断意图优先级（删除/添加/查询）
            if any(k in text_lower for k in ['删除', '移除', '删掉']):
                intent_type = IntentType.DELETE_EVENT
            elif any(k in text_lower for k in ['参加', '安排', '添加', '创建', '新建']):
                intent_type = IntentType.ADD_EVENT
            elif any(k in text_lower for k in ['修改', '更改', '更新', '编辑', '调整']):
                intent_type = IntentType.MODIFY_EVENT
            elif any(k in text_lower for k in ['查询', '查看', '显示', '有']):
                intent_type = IntentType.QUERY_EVENTS
            else:
                # 默认将带具体日期的短句当作添加事件（例如"22号下午参加会议"）
                intent_type = IntentType.ADD_EVENT

            confidence = 0.8
            entities = {'raw_text': text}
            entities.update(day_time)
            return ParsedIntent(
                intent_type=intent_type,
                entities=entities,
                confidence=confidence,
                original_text=text,
                structured_response="备用解析：包含具体日期"
            )

        # 🏋️ 新增：训练计划相关意图识别（保持原有判断）
        if any(keyword in text_lower for keyword in ['训练计划', '健身计划', '锻炼计划', '健身', '训练']):
            intent_type = IntentType.CREATE_WORKOUT_PLAN
            confidence = 0.8
            entities = {'action': 'create_workout', 'raw_text': text}
        elif any(keyword in text_lower for keyword in ['删除训练计划', '清除训练计划', '删除所有训练']):
            intent_type = IntentType.DELETE_WORKOUT_PLANS
            confidence = 0.9
            entities = {'action': 'delete_workout_plans', 'raw_text': text}

        # 🎯 新增：任务分解意图识别
        elif any(keyword in text_lower for keyword in
                 ['任务', '分解', '分配', '空余时间', '截止', '之前完成', '需要小时']):
            # 尝试提取任务信息
            task_info = self._extract_task_info(text)
            if task_info:
                intent_type = IntentType.BREAKDOWN_TASK
                confidence = 0.8
                entities = task_info
            else:
                intent_type = IntentType.BREAKDOWN_TASK
                confidence = 0.6
                entities = {'raw_text': text}

        elif any(keyword in text_lower for keyword in
            ['删除任务分解', '清除任务分解', '删除所有任务分解', '清除所有任务分解']):

            intent_type = IntentType.DELETE_TASK_BREAKDOWNS
            confidence = 0.9
            entities = {'action': 'delete_all_task_breakdowns', 'raw_text': text}
            return ParsedIntent(
                intent_type=intent_type,
                entities=entities,
                confidence=confidence,
                original_text=text,
                structured_response="删除所有任务分解（备用解析）"
            )

        # 检查确认相关的关键词
        elif any(keyword in text_lower for keyword in ['确认', '确定', '是的', '好的', '对', '同意', '是']):
            intent_type = IntentType.CONFIRM_ACTION
            confidence = 0.9
            entities = {'action': 'confirm', 'raw_text': text}
        elif any(keyword in text_lower for keyword in ['取消', '不要', '不是', '否', '拒绝', '不']):
            intent_type = IntentType.CANCEL_ACTION
            confidence = 0.9
            entities = {'action': 'cancel', 'raw_text': text}
        # 🚀 新增：识别用户请求"换一个/重新推荐/下一个"为下一推荐动作
        elif any(keyword in text_lower for keyword in ['换一个', '重新推荐', '下一个', '再来一个']):
            intent_type = IntentType.CONFIRM_ACTION
            confidence = 0.85
            entities = {'action': 'next_suggestion', 'raw_text': text}
        elif any(keyword in text_lower for keyword in ['添加', '新建', '安排', '创建', '参加']):
            intent_type = IntentType.ADD_EVENT
            confidence = 0.8
            entities = {
                'title': self._extract_title(text) if hasattr(self, '_extract_title') else None,
                'location': self._extract_location(text) if hasattr(self, '_extract_location') else None,
                'raw_text': text
            }
        elif any(keyword in text_lower for keyword in ['修改', '更新', '更改', '编辑', '调整']):
            intent_type = IntentType.MODIFY_EVENT
            confidence = 0.7
            entities = {'raw_text': text}
        elif any(keyword in text_lower for keyword in ['删除', '移除']):
            intent_type = IntentType.DELETE_EVENT
            confidence = 0.7
            entities = {'raw_text': text}
        elif any(keyword in text_lower for keyword in ['帮助', '怎么用', '如何']):
            intent_type = IntentType.HELP
            confidence = 0.8
            entities = {'raw_text': text}
        elif any(keyword in text_lower for keyword in ['查询', '查看', '显示', '什么', '有']):
            intent_type = IntentType.QUERY_EVENTS
            confidence = 0.7
            entities = {'raw_text': text}
        elif any(keyword in text_lower for keyword in ['列表', '日程', '计划', '安排']):
            intent_type = IntentType.LIST_EVENTS
            confidence = 0.7
            entities = {'raw_text': text}
        else:
            intent_type = IntentType.QUERY_EVENTS
            confidence = 0.5
            entities = {'raw_text': text}

        return ParsedIntent(
            intent_type=intent_type,
            entities=entities,
            confidence=confidence,
            original_text=text,
            structured_response="使用备用解析方法"
        )

    def _extract_day_time_from_text(self, text: str) -> Optional[Dict[str, Any]]:
        """
        提取文本中的"几号/几日"与简单时间（如下午3点、15:30、晚上7点）并返回结构化实体：
        返回示例：
        {
          'day_of_month': 22,
          'date': '2025-11-22',         # YYYY-MM-DD 字符串
          'hour': 15,
          'minute': 0,
          'time_period': 'afternoon'    # morning/noon/afternoon/evening
        }
        """
        text = text.strip()
        today = datetime.now().date()
        # 匹配"22号"或"22日"
        m_day = re.search(r'(?P<day>\b[1-9]|[12][0-9]|3[01])\s*(号|日)\b', text)
        if not m_day:
            # 也支持带"\d+号"的连续数字（例如"27号晚上的日程"）
            m_day = re.search(r'(?P<day>\d{1,2})(?=号|日)', text)
        if not m_day:
            return None

        day = int(m_day.group('day'))
        # 推断月份：优先本月，若该日已过则推到下个月
        year = today.year
        month = today.month
        try:
            candidate_date = date(year, month, day)
            if candidate_date < today:
                # 转到下个月
                if month == 12:
                    candidate_date = date(year + 1, 1, day)
                else:
                    candidate_date = date(year, month + 1, day)
        except Exception:
            # 如果无效日期（例如当月没有该日），尝试下个月
            if month == 12:
                candidate_date = date(year + 1, 1, min(day, 28))
            else:
                candidate_date = date(year, month + 1, min(day, 28))

        # 解析时间（尽可能识别"下午3点/15:30/晚上7点/19点半"等）
        hour = None
        minute = 0
        time_period = None

        # 先找 24h 格式 hh:mm
        m_hm = re.search(r'(?P<h>\b[0-2]?\d):(?P<m>[0-5]\d)', text)
        if m_hm:
            hour = int(m_hm.group('h'))
            minute = int(m_hm.group('m'))
        else:
            # 匹配 "下午3点" / "上午10时" / "晚上7点半"
            m_tm = re.search(r'(?P<period>上午|早上|早晨|中午|下午|晚上|傍晚|夜间)?\s*(?P<h>\d{1,2})\s*(点|时)', text)
            if m_tm:
                period = m_tm.group('period')
                hour = int(m_tm.group('h'))
                # 处理半点
                if '半' in text:
                    minute = 30
                # 根据 period 调整小时
                if period:
                    if period in ['下午', '晚上', '傍晚', '夜间'] and hour < 12:
                        hour = hour % 12 + 12
                        time_period = 'afternoon' if period == '下午' else 'evening'
                    elif period in ['上午', '早上', '早晨'] and hour == 12:
                        hour = 0
                        time_period = 'morning'
                    elif period in ['中午']:
                        time_period = 'noon'
                else:
                    # 未指定 period，保持 hour 原样
                    pass

        entity = {
            'day_of_month': day,
            'date': candidate_date.isoformat()
        }
        if hour is not None:
            entity.update({'hour': hour, 'minute': minute})
            if not time_period:
                # 根据小时简单分类
                if 6 <= hour < 12:
                    entity['time_period'] = 'morning'
                elif 12 <= hour < 14:
                    entity['time_period'] = 'noon'
                elif 14 <= hour < 18:
                    entity['time_period'] = 'afternoon'
                else:
                    entity['time_period'] = 'evening'
        return entity

    def _extract_title(self, text: str) -> str:
        """从文本中提取标题"""
        keywords = ['参加', '会议', '讨论会', '约会', '活动', '讲座', '培训']
        for keyword in keywords:
            if keyword in text:
                start_idx = text.find(keyword) + len(keyword)
                title = text[start_idx:].strip()
                if title:
                    return title.strip('在，。！？')
        return '未命名事件'

    def _extract_location(self, text: str) -> str:
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

    # 🎯 新增：提取任务信息的方法
    # 在 LLMParser 类中改进 _extract_task_info 方法
    def _extract_task_info(self, text: str) -> Dict[str, Any]:
        """从文本中提取任务信息：任务名称、截止日期、所需小时数 - 改进版本"""
        import re
        from datetime import datetime

        task_info = {'raw_text': text}

        # 🛠️ 修复：改进小时数提取
        hour_patterns = [
            r'(\d+(?:\.\d+)?)\s*小时',
            r'需要\s*(\d+(?:\.\d+)?)\s*小时',
            r'大概\s*(\d+(?:\.\d+)?)\s*小时',
            r'约\s*(\d+(?:\.\d+)?)\s*小时',
            r'(\d+(?:\.\d+)?)\s*个小时'
        ]

        for pattern in hour_patterns:
            match = re.search(pattern, text)
            if match:
                try:
                    task_info['total_hours'] = float(match.group(1))
                    print(f"[DEBUG] 提取到小时数: {task_info['total_hours']}")
                    break
                except ValueError:
                    continue

        # 🛠️ 修复：改进截止日期提取
        deadline_patterns = [
            r'(\d+)月\s*(\d+)\s*号之前',
            r'(\d+)\s*月\s*(\d+)\s*日之前',
            r'(\d+)\/(\d+)之前',
            r'截止到\s*(\d+)\D+(\d+)',
            r'在\s*(\d+)\D+(\d+)\D+前',
            r'(\d+)\s*月\s*(\d+)\s*号前'
        ]

        current_year = datetime.now().year
        current_month = datetime.now().month

        for pattern in deadline_patterns:
            match = re.search(pattern, text)
            if match:
                try:
                    month = int(match.group(1))
                    day = int(match.group(2))

                    # 🛠️ 修复：处理月份逻辑，如果月份小于当前月份，则认为是明年
                    year = current_year
                    if month < current_month:
                        year = current_year + 1

                    # 简单的日期验证
                    if 1 <= month <= 12 and 1 <= day <= 31:
                        deadline = datetime(year, month, day, 23, 59, 59)
                        task_info['deadline'] = deadline
                        print(f"[DEBUG] 提取到截止日期: {deadline}")
                        break
                except (ValueError, IndexError):
                    continue

        # 🛠️ 修复：改进任务标题提取
        title_keywords = ['任务', '事情', '工作', '项目', '作业']
        words = re.findall(r'[^，。！？\s]+', text)

        # 尝试提取任务描述
        task_desc_match = re.search(r'有一个(.+?)要在', text)
        if task_desc_match:
            task_info['title'] = task_desc_match.group(1).strip()
        else:
            # 如果没有明确描述，使用默认标题
            for i, word in enumerate(words):
                if any(keyword in word for keyword in title_keywords) and i > 0:
                    # 组合前面的词作为标题
                    title_parts = []
                    for j in range(max(0, i - 2), i + 1):
                        if j < len(words):
                            title_parts.append(words[j])
                    task_info['title'] = ''.join(title_parts)
                    break

        # 如果没有提取到标题，使用默认标题
        if 'title' not in task_info:
            task_info['title'] = '待完成任务'

        print(f"[DEBUG] 最终任务信息: {task_info}")
        return task_info