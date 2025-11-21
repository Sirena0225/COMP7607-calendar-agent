import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from abc import ABC, abstractmethod
from enum import Enum

@dataclass
class CalendarEvent:
    id: str
    title: str
    start_time: datetime
    end_time: datetime
    description: str = ""
    location: str = ""
    attendees: List[str] = None
    reminder_minutes: int = 15
    recurrence: str = None
    has_conflict: bool = False  # 🛠️ 新增：冲突标记

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'start_time': self.start_time.isoformat(),
            'end_time': self.end_time.isoformat(),
            'description': self.description,
            'location': self.location,
            'attendees': self.attendees or [],
            'reminder_minutes': self.reminder_minutes,
            'recurrence': self.recurrence,
            'has_conflict': self.has_conflict  # 🛠️ 新增
        }

class IntentType(Enum):
    ADD_EVENT = "add_event"
    MODIFY_EVENT = "modify_event"
    DELETE_EVENT = "delete_event"
    QUERY_EVENTS = "query_events"
    LIST_EVENTS = "list_events"
    CONFIRM_ACTION = "confirm_action"
    CANCEL_ACTION = "cancel_action"
    HELP = "help"
    # 🏋️ 新增训练计划相关意图
    CREATE_WORKOUT_PLAN = "create_workout_plan"
    DELETE_WORKOUT_PLANS = "delete_workout_plans"
    # 🎯 新增：任务分解意图
    BREAKDOWN_TASK = "breakdown_task"
    # 🗑️ 新增：删除任务分解意图
    DELETE_TASK_BREAKDOWNS = "delete_task_breakdowns"

@dataclass
class ParsedIntent:
    intent_type: IntentType
    entities: dict
    confidence: float
    original_text: str
    structured_response: str = ""

# 🏋️ 新增：训练计划相关模型
@dataclass
class UserProfile:
    height: float  # 厘米
    weight: float  # 公斤
    age: int
    gender: str  # 'male' or 'female'
    fitness_goal: str  # 'muscle_gain', 'fat_loss', 'body_shaping', 'strength'
    target_body_part: str = ""  # 特定训练部位
    experience_level: str = "beginner"  # beginner, intermediate, advanced

@dataclass
class WorkoutPlan:
    id: str
    user_profile: UserProfile
    plan_duration: int  # 持续周数
    sessions_per_week: int  # 每周训练次数
    session_duration: int  # 单次训练分钟数
    workouts: List[Dict]  # 训练内容列表
    created_at: datetime
    start_date: datetime

    def to_dict(self):
        return {
            'id': self.id,
            'user_profile': {
                'height': self.user_profile.height,
                'weight': self.user_profile.weight,
                'age': self.user_profile.age,
                'gender': self.user_profile.gender,
                'fitness_goal': self.user_profile.fitness_goal,
                'target_body_part': self.user_profile.target_body_part,
                'experience_level': self.user_profile.experience_level
            },
            'plan_duration': self.plan_duration,
            'sessions_per_week': self.sessions_per_week,
            'session_duration': self.session_duration,
            'workouts': self.workouts,
            'created_at': self.created_at.isoformat(),
            'start_date': self.start_date.isoformat()
        }

# 添加任务分解相关数据模型
# 修复 TaskBreakdown 类的 __post_init__ 方法
@dataclass
class TaskBreakdown:
    id: str
    title: str
    total_hours: float
    deadline: datetime
    chunks: List[Dict]  # 分解后的任务块
    created_at: datetime

    def __post_init__(self):
        """确保字段类型正确 - 修复版本"""
        # 🛠️ 修复：改进 datetime 解析
        def parse_datetime(dt_str):
            if isinstance(dt_str, datetime):
                return dt_str
            try:
                if hasattr(datetime, 'fromisoformat'):
                    return datetime.fromisoformat(dt_str)
                else:
                    # 备用解析方法
                    for fmt in ['%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d']:
                        try:
                            return datetime.strptime(dt_str, fmt)
                        except:
                            continue
                    return datetime.now()
            except:
                return datetime.now()

        # 如果 deadline 是字符串，转换为 datetime
        if isinstance(self.deadline, str):
            self.deadline = parse_datetime(self.deadline)

        # 如果 created_at 是字符串，转换为 datetime
        if isinstance(self.created_at, str):
            self.created_at = parse_datetime(self.created_at)

        # 🛠️ 修复：确保 chunks 中的时间字符串被正确解析
        if self.chunks:
            for chunk in self.chunks:
                if 'start_time' in chunk and isinstance(chunk['start_time'], str):
                    chunk['start_time'] = parse_datetime(chunk['start_time'])

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'total_hours': self.total_hours,
            'deadline': self.deadline.isoformat(),
            'chunks': self.chunks,
            'created_at': self.created_at.isoformat()
        }