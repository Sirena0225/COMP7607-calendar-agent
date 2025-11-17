import re
from datetime import datetime
from typing import Tuple, Optional, Dict, Any
from models import ParsedIntent, IntentType
from qwen_client import QwenClient

class LLMParser:
    def __init__(self):
        self.qwen_client = QwenClient()
    
    def parse(self, text: str) -> ParsedIntent:
        """使用Qwen LLM解析用户输入"""
        result = self.qwen_client.parse_intent_with_llm(text)
        
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
                'delete_workout_plans': IntentType.DELETE_WORKOUT_PLANS
            }
            
            intent_type_str = data.get('intent_type', 'query_events')
            intent_type = intent_map.get(intent_type_str, IntentType.QUERY_EVENTS)
            
            entities = data.get('entities', {})
            confidence = data.get('confidence', 0.5)
            
            parsed_intent = ParsedIntent(
                intent_type=intent_type,
                entities=entities,
                confidence=confidence,
                original_text=text,
                structured_response=result['raw_response']
            )
            
            print(f"[DEBUG] 解析意图: {intent_type.value}, 置信度: {confidence}")
            return parsed_intent
        else:
            print(f"[DEBUG] LLM解析失败: {result.get('error', 'Unknown error')}")
            # LLM解析失败时的备用方案
            return self._fallback_parse(text)
    
    def _fallback_parse(self, text: str) -> ParsedIntent:
        """备用解析方法 - 修复确认操作识别"""
        print(f"[DEBUG] 使用备用解析方法: {text}")
        
        text_lower = text.lower()

        # 🏋️ 新增：训练计划相关意图识别
        if any(keyword in text_lower for keyword in ['训练计划', '健身计划', '锻炼计划', '健身', '训练']):
            intent_type = IntentType.CREATE_WORKOUT_PLAN
            confidence = 0.8
            entities = {'action': 'create_workout', 'raw_text': text}
        elif any(keyword in text_lower for keyword in ['删除训练计划', '清除训练计划', '删除所有训练']):
            intent_type = IntentType.DELETE_WORKOUT_PLANS
            confidence = 0.9
            entities = {'action': 'delete_workout_plans', 'raw_text': text}
        
        # 检查确认相关的关键词
        elif any(keyword in text_lower for keyword in ['确认', '确定', '是的', '好的', '对', '同意', '是']):
            intent_type = IntentType.CONFIRM_ACTION
            confidence = 0.9
            entities = {'action': 'confirm', 'raw_text': text}
        elif any(keyword in text_lower for keyword in ['取消', '不要', '不是', '否', '拒绝', '不']):
            intent_type = IntentType.CANCEL_ACTION
            confidence = 0.9
            entities = {'action': 'cancel', 'raw_text': text}
        elif any(keyword in text_lower for keyword in ['添加', '新建', '安排', '创建', '参加']):
            intent_type = IntentType.ADD_EVENT
            confidence = 0.8
            entities = {
                'title': self._extract_title(text),
                'location': self._extract_location(text),
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