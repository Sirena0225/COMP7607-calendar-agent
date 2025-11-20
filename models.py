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