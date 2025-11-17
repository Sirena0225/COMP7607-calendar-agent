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
            'recurrence': self.recurrence
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

@dataclass
class ParsedIntent:
    intent_type: IntentType
    entities: dict
    confidence: float
    original_text: str
    structured_response: str = ""