# llm/qwen_client.py
import requests
import json
import re
from typing import Dict, Any
from config import APIConfig

class QwenClient:
    def __init__(self):
        self.api_key = APIConfig.QWEN_API_KEY
        self.model = APIConfig.QWEN_MODEL
        self.base_url = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
    
    def call_qwen(self, prompt: str, system_prompt: str = "") -> Dict[str, Any]:
        """调用Qwen API"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        payload = {
            "model": self.model,
            "input": {
                "messages": messages
            },
            "parameters": {
                "temperature": 0.7,
                "top_p": 0.8,
                "max_tokens": 1000
            }
        }
        
        try:
            response = requests.post(
                self.base_url,
                headers=headers,
                json=payload,
                timeout=APIConfig.TIMEOUT
            )
            
            if response.status_code == 200:
                result = response.json()
                return {
                    'success': True,
                    'response': result['output']['text'],
                    'usage': result.get('usage', {})
                }
            else:
                return {
                    'success': False,
                    'error': f"API Error: {response.status_code} - {response.text}"
                }
        except Exception as e:
            return {
                'success': False,
                'error': f"Request Error: {str(e)}"
            }
    
    def parse_intent_with_llm(self, user_input: str) -> Dict[str, Any]:
        """使用LLM解析用户意图"""
        system_prompt = """
        你是一个专业的日历助手，专门解析用户的日历相关意图。
        请分析用户的输入，识别其意图类型和提取相关信息。
        
        意图类型包括：
        - add_event: 添加事件
        - modify_event: 修改事件  
        - delete_event: 删除事件
        - query_events: 查询事件
        - list_events: 列出事件
        - confirm_action: 确认操作
        - cancel_action: 取消操作
        - help: 帮助
        
        请严格按照以下JSON格式返回结果，不要添加其他内容：
        {
            "intent_type": "intent_type",
            "entities": {
                "title": "事件标题",
                "start_time": "开始时间(ISO格式，如果知道的话)",
                "end_time": "结束时间(ISO格式，如果知道的话)", 
                "location": "地点",
                "description": "描述"
            },
            "confidence": 0.0-1.0,
            "explanation": "分析说明"
        }
        """
        
        prompt = f"""
        用户输入: "{user_input}"
        
        请严格按照JSON格式返回分析结果。如果时间信息不完整，start_time和end_time字段可以为空字符串。
        
        JSON格式：
        {{
            "intent_type": "add_event",
            "entities": {{
                "title": "事件标题",
                "start_time": "开始时间",
                "end_time": "结束时间", 
                "location": "地点",
                "description": "描述"
            }},
            "confidence": 0.8,
            "explanation": "分析说明"
        }}
        """
        
        result = self.call_qwen(prompt, system_prompt)
        
        if result['success']:
            try:
                response_text = result['response']
                print(f"[DEBUG] Qwen原始响应: {response_text}")  # 调试输出
                
                # 提取JSON部分
                json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                if json_match:
                    json_str = json_match.group()
                    print(f"[DEBUG] 提取的JSON: {json_str}")  # 调试输出
                    
                    parsed_data = json.loads(json_str)
                    return {
                        'success': True,
                        'data': parsed_data,
                        'raw_response': response_text
                    }
                else:
                    print(f"[DEBUG] 未找到JSON格式")  # 调试输出
                    return {
                        'success': False,
                        'error': '无法解析LLM返回的JSON格式'
                    }
            except json.JSONDecodeError as e:
                print(f"[DEBUG] JSON解析错误: {e}")  # 调试输出
                return {
                    'success': False,
                    'error': f'JSON解析错误: {str(e)}'
                }
        else:
            print(f"[DEBUG] Qwen API调用失败: {result['error']}")  # 调试输出
            return result