# utils/conflict_resolver.py
from datetime import datetime, timedelta
from typing import List, Optional
from models import CalendarEvent


class ConflictResolver:
    def __init__(self, calendar_interface):
        self.calendar = calendar_interface

    async def find_conflicting_events(self, new_event: CalendarEvent) -> List[CalendarEvent]:
        """查找与新事件时间冲突的现有事件"""
        # 查询新事件时间前后2小时内的事件
        start_search = new_event.start_time - timedelta(hours=2)
        end_search = new_event.end_time + timedelta(hours=2)

        try:
            all_events = await self.calendar.list_events(start_search, end_search)
        except Exception as e:
            print(f"[ERROR] 查询事件失败: {e}")
            return []

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
        2. 同天前后1小时
        3. 前后1天同一时间
        4. 前后1天前后1小时
        """
        if base_time is None:
            base_time = new_event.start_time

        suggestions = []
        event_duration = new_event.end_time - new_event.start_time

        # 1. 同天前/后30分钟
        for delta in [-30, +30, -60, +60]:
            cand = base_time + timedelta(minutes=delta)
            if await self._is_available(cand, event_duration):
                suggestions.append(cand)

        # 2. 前后1天同一时间
        for day in [-1, +1]:
            cand = base_time + timedelta(days=day)
            if await self._is_available(cand, event_duration):
                suggestions.append(cand)

        # 3. 前后1天 ±1小时
        for day in [-1, +1]:
            for hour in [-1, +1]:
                cand = base_time + timedelta(days=day, hours=hour)
                if await self._is_available(cand, event_duration):
                    suggestions.append(cand)

        # 4. 同周相邻日期同一时间
        for day in [-2, +2, -3, +3]:
            cand = base_time + timedelta(days=day)
            if await self._is_available(cand, event_duration):
                suggestions.append(cand)

        # 按与原时间距离排序（越近越靠前）
        suggestions.sort(key=lambda t: abs((t - base_time).total_seconds()))

        # 过滤掉过去的时间
        now = datetime.now()
        suggestions = [t for t in suggestions if t > now]

        return suggestions[:8]  # 最多8个建议

    async def _is_available(self, start_time: datetime, duration: timedelta) -> bool:
        """检查 start_time 开始的时段是否可用（不与现有事件冲突）"""
        end_time = start_time + duration

        # 检查是否在合理的时间范围内（早上6点到晚上11点）
        if start_time.hour < 6 or end_time.hour > 23:
            return False

        candidate = CalendarEvent(
            id="temp_check",
            title="临时检查",
            start_time=start_time,
            end_time=end_time
        )

        try:
            conflicts = await self.find_conflicting_events(candidate)
            return len(conflicts) == 0
        except Exception as e:
            print(f"[ERROR] 检查时间可用性失败: {e}")
            return False

    async def get_available_slots(self, date: datetime, duration: timedelta) -> List[datetime]:
        """获取指定日期可用的时间段"""
        available_slots = []

        # 检查当天的每个小时段
        start_of_day = datetime(date.year, date.month, date.day, 6, 0)  # 从早上6点开始
        for hour in range(6, 22):  # 到晚上10点结束
            check_time = start_of_day + timedelta(hours=hour)
            if await self._is_available(check_time, duration):
                available_slots.append(check_time)

        return available_slots