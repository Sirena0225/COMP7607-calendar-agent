# utils/conflict_resolver.py
from datetime import datetime, timedelta
from typing import List, Optional
from models import CalendarEvent

class ConflictResolver:
    def __init__(self, calendar_interface):
        self.calendar = calendar_interface
    
    async def find_conflicting_events(self, new_event: CalendarEvent) -> List[CalendarEvent]:
        """查找与新事件时间冲突的现有事件"""
        # 查询新事件时间前后1天内的事件
        start_search = new_event.start_time - timedelta(days=1)
        end_search = new_event.end_time + timedelta(days=1)
        all_events = await self.calendar.list_events(start_search, end_search)
        
        conflicts = []
        for event in all_events:
            if event.id != getattr(new_event, 'id', '') and self._events_overlap(event, new_event):
                conflicts.append(event)
        return conflicts

    def _events_overlap(self, e1: CalendarEvent, e2: CalendarEvent) -> bool:
        """判断两个事件是否时间重叠"""
        return e1.start_time < e2.end_time and e2.start_time < e1.end_time

    async def suggest_alternative_times(self, new_event: CalendarEvent, base_time: datetime = None) -> List[datetime]:
        """
        按优先级推荐时间：
        1. 同天前后30分钟
        2. 前后1天同一时间
        3. 前后1天前后1小时
        """
        if base_time is None:
            base_time = new_event.start_time
        
        suggestions = []

        # 1. 同天前/后30分钟
        for delta in [-30, +30]:
            cand = base_time + timedelta(minutes=delta)
            if self._is_available(cand, new_event):
                suggestions.append(cand)

        # 2. 前后1天同一时间
        for day in [-1, +1]:
            cand = base_time + timedelta(days=day)
            if self._is_available(cand, new_event):
                suggestions.append(cand)

        # 3. 前后1天 ±1小时
        for day in [-1, +1]:
            for hour in [-1, +1]:
                cand = base_time + timedelta(days=day, hours=hour)
                if self._is_available(cand, new_event):
                    suggestions.append(cand)

        # 按与原时间距离排序（越近越靠前）
        suggestions.sort(key=lambda t: abs((t - base_time).total_seconds()))
        return suggestions[:5]  # 最多5个建议

    async def _is_available(self, start_time: datetime, event: CalendarEvent) -> bool:
        """检查 start_time 开始的时段是否可用（不与现有事件冲突）"""
        end_time = start_time + (event.end_time - event.start_time)
        candidate = CalendarEvent(
            id="temp", title="temp", start_time=start_time, end_time=end_time
        )
        conflicts = await self.find_conflicting_events(candidate)
        return len(conflicts) == 0