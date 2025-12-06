# qwen_client.py
import os
import json
import re
from typing import Dict, Any
from openai import OpenAI
from config import APIConfig


class QwenClient:
    def __init__(self):
        self.api_key = os.getenv("DASHSCOPE_API_KEY", APIConfig.QWEN_API_KEY)
        self.model = APIConfig.QWEN_MODEL
        self.client = OpenAI(
            api_key=self.api_key,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        )

    def call_qwen(self, prompt: str, system_prompt: str = "") -> Dict[str, Any]:
        """调用Qwen API使用OpenAI兼容接口"""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        try:
            completion = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.7,
                top_p=0.8,
                max_tokens=1000
            )

            response_content = completion.choices[0].message.content

            return {
                'success': True,
                'response': response_content,
                'usage': {
                    'prompt_tokens': completion.usage.prompt_tokens if completion.usage else 0,
                    'completion_tokens': completion.usage.completion_tokens if completion.usage else 0,
                    'total_tokens': completion.usage.total_tokens if completion.usage else 0
                }
            }

        except Exception as e:
            return {
                'success': False,
                'error': f"API调用错误: {str(e)}"
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
        - create_workout_plan: 创建训练计划（当用户提到训练、健身、锻炼、增肌、减脂等）
        - delete_workout_plans: 删除训练计划（当用户提到删除训练、清除健身计划等）
        - breakdown_task: 任务分解（当用户提到任务分解、分配空余时间、截止日期前完成等）

        请严格按照以下JSON格式返回结果，不要添加其他内容：
        {
            "intent_type": "intent_type",
            "entities": {
                "title": "事件标题",
                "start_time": "开始时间(ISO格式，如果知道的话)",
                "end_time": "结束时间(ISO格式，如果知道的话)", 
                "location": "地点",
                "description": "描述"
                "total_hours": "所需小时数",
                "deadline": "截止日期"
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
                print(f"[DEBUG] Qwen原始响应: {response_text}")

                # 提取JSON部分
                json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                if json_match:
                    json_str = json_match.group()
                    print(f"[DEBUG] 提取的JSON: {json_str}")

                    parsed_data = json.loads(json_str)
                    return {
                        'success': True,
                        'data': parsed_data,
                        'raw_response': response_text
                    }
                else:
                    print(f"[DEBUG] 未找到JSON格式")
                    return {
                        'success': False,
                        'error': '无法解析LLM返回的JSON格式'
                    }
            except json.JSONDecodeError as e:
                print(f"[DEBUG] JSON解析错误: {e}")
                return {
                    'success': False,
                    'error': f'JSON解析错误: {str(e)}'
                }
            except Exception as e:
                print(f"[DEBUG] 其他解析错误: {e}")
                return {
                    'success': False,
                    'error': f'解析错误: {str(e)}'
                }
        else:
            print(f"[DEBUG] Qwen API调用失败: {result['error']}")
            return result

    # 添加一个简单的测试方法
    def test_connection(self) -> bool:
        """测试API连接"""
        try:
            result = self.call_qwen("你好，请回复'连接成功'", "你是一个测试助手")
            return result['success']
        except:
            return False