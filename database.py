import sqlite3
import os
import json
import datetime
from typing import List, Optional, Dict
from abc import ABC, abstractmethod
from models import CalendarEvent

class SQLiteCalendar:
    def __init__(self, db_path: str = "calendar.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """初始化数据库"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS events (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                start_time TEXT NOT NULL,
                end_time TEXT NOT NULL,
                description TEXT,
                location TEXT,
                attendees TEXT,
                reminder_minutes INTEGER DEFAULT 15,
                recurrence TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
    
    async def add_event(self, event: CalendarEvent) -> bool:
        """添加事件"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO events 
                (id, title, start_time, end_time, description, location, attendees, reminder_minutes, recurrence)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                event.id, event.title, event.start_time.isoformat(), 
                event.end_time.isoformat(), event.description, event.location,
                json.dumps(event.attendees or []), event.reminder_minutes, event.recurrence
            ))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"添加事件失败: {e}")
            return False
    
    async def modify_event(self, event_id: str, updates: Dict) -> bool:
        """修改事件"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            set_clause = ", ".join([f"{key} = ?" for key in updates.keys()])
            values = list(updates.values()) + [event_id]
            
            cursor.execute(f'''
                UPDATE events SET {set_clause} WHERE id = ?
            ''', values)
            
            conn.commit()
            conn.close()
            return cursor.rowcount > 0
        except Exception as e:
            print(f"修改事件失败: {e}")
            return False
    
    async def delete_event(self, event_id: str) -> bool:
        """删除事件"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('DELETE FROM events WHERE id = ?', (event_id,))
            conn.commit()
            conn.close()
            return cursor.rowcount > 0
        except Exception as e:
            print(f"删除事件失败: {e}")
            return False
    
    async def list_events(self, start_date: datetime, end_date: datetime) -> List[CalendarEvent]:
        """列出事件"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM events 
            WHERE start_time >= ? AND start_time <= ?
            ORDER BY start_time
        ''', (start_date.isoformat(), end_date.isoformat()))
        
        rows = cursor.fetchall()
        conn.close()
        
        events = []
        for row in rows:
            events.append(CalendarEvent(
                id=row[0], title=row[1], 
                start_time=datetime.fromisoformat(row[2]),
                end_time=datetime.fromisoformat(row[3]),
                description=row[4], location=row[5],
                attendees=json.loads(row[6]) if row[6] else [],
                reminder_minutes=row[7], recurrence=row[8]
            ))
        
        return events