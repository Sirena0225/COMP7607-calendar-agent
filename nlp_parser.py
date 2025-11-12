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
            print(f"[DEBUG] LLM解析结果: {data}")  # 调试输出
            
            # 将字符串意图类型转换为枚举
            intent_map = {
                'add_event': IntentType.ADD_EVENT,
                'modify_event': IntentType.MODIFY_EVENT,
                'delete_event': IntentType.DELETE_EVENT,
                'query_events': IntentType.QUERY_EVENTS,
                'list_events': IntentType.LIST_EVENTS,
                'confirm_action': IntentType.CONFIRM_ACTION,
                'cancel_action': IntentType.CANCEL_ACTION,
                'help': IntentType.HELP
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
            
            print(f"[DEBUG] 解析意图: {intent_type.value}, 置信度: {confidence}")  # 调试输出
            return parsed_intent
        else:
            print(f"[DEBUG] LLM解析失败: {result.get('error', 'Unknown error')}")  # 调试输出
            # LLM解析失败时的备用方案
            return self._fallback_parse(text)
    
    def _fallback_parse(self, text: str) -> ParsedIntent:
        """备用解析方法"""
        print(f"[DEBUG] 使用备用解析方法: {text}")  # 调试输出
        
        # 简单的关键词匹配
        if any(keyword in text for keyword in ['添加', '新建', '安排', '创建', '会议', '讨论会', '约会']):
            intent_type = IntentType.ADD_EVENT
            confidence = 0.8
            
            # 从文本中提取基本信息
            entities = {
                'title': self._extract_title(text),
                'location': self._extract_location(text),
                'raw_text': text
            }
        elif any(keyword in text for keyword in ['修改', '更新', '更改']):
            intent_type = IntentType.MODIFY_EVENT
            confidence = 0.7
        elif any(keyword in text for keyword in ['删除', '取消']):
            intent_type = IntentType.DELETE_EVENT
            confidence = 0.7
        elif any(keyword in text for keyword in ['帮助', '怎么用']):
            intent_type = IntentType.HELP
            confidence = 0.8
        else:
            intent_type = IntentType.QUERY_EVENTS
            confidence = 0.6
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
        # 查找关键词后的文本
        keywords = ['参加', '会议', '讨论会', '约会', '活动']
        for keyword in keywords:
            if keyword in text:
                start_idx = text.find(keyword) + len(keyword)
                title = text[start_idx:].strip()
                if title:
                    return title
        return '未命名事件'
    
    def _extract_location(self, text: str) -> str:
        """从文本中提取地点"""
        # 匹配 "在...教室" 或 "在...会议室" 等模式
        location_patterns = [
            r'在(.+?)[教室|会议室|办公室|地点]',
            r'于(.+?)[教室|会议室|办公室|地点]',
            r'地点(.+?)[，。]',
        ]
        
        for pattern in location_patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1).strip()
        
        # 简单匹配 "在..." 模式
        match = re.search(r'在(.+?)[，。]', text)
        if match:
            return match.group(1).strip()
        
        return ''