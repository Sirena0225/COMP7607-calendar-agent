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
        print(f"[DEBUG] 数据库已初始化: {self.db_path}")
    
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
            
            print(f"[DEBUG] 事件已添加到数据库: {event.title} at {event.start_time}")
            return True
        except Exception as e:
            print(f"[ERROR] 添加事件失败: {e}")
            return False
    
    async def modify_event(self, event_id: str, updates: dict) -> bool:
        """修改事件"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 构建更新语句
            set_clause = ", ".join([f"{key} = ?" for key in updates.keys()])
            values = list(updates.values()) + [event_id]
            
            cursor.execute(f'''
                UPDATE events SET {set_clause} WHERE id = ?
            ''', values)
            
            conn.commit()
            conn.close()
            
            rows_affected = cursor.rowcount
            print(f"[DEBUG] 修改事件影响行数: {rows_affected}")
            
            if rows_affected > 0:
                print(f"[DEBUG] 事件 {event_id} 已成功修改")
                return True
            else:
                print(f"[DEBUG] 未找到事件 {event_id}")
                return False
        except Exception as e:
            print(f"[ERROR] 修改事件失败: {e}")
            return False
    
    async def delete_event(self, event_id: str) -> bool:
        """删除事件"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('DELETE FROM events WHERE id = ?', (event_id,))
            conn.commit()
            conn.close()
            
            rows_affected = cursor.rowcount
            print(f"[DEBUG] 删除事件影响行数: {rows_affected}")
            
            return rows_affected > 0
        except Exception as e:
            print(f"[ERROR] 删除事件失败: {e}")
            return False
    
    async def list_events(self, start_date: datetime, end_date: datetime) -> List[CalendarEvent]:
        """列出事件"""
        print(f"[DEBUG] 查询事件时间范围: {start_date} 到 {end_date}")
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM events 
            WHERE start_time >= ? AND start_time <= ?
            ORDER BY start_time
        ''', (start_date.isoformat(), end_date.isoformat()))
        
        rows = cursor.fetchall()
        conn.close()
        
        print(f"[DEBUG] 查询到 {len(rows)} 个事件")
        
        events = []
        for row in rows:
            try:
                # 修复时间解析 - 兼容旧版本Python
                start_time = self._parse_datetime(row[2])
                end_time = self._parse_datetime(row[3])
                
                event = CalendarEvent(
                    id=row[0], title=row[1], 
                    start_time=start_time,
                    end_time=end_time,
                    description=row[4], location=row[5],
                    attendees=json.loads(row[6]) if row[6] else [],
                    reminder_minutes=row[7], recurrence=row[8]
                )
                events.append(event)
                print(f"[DEBUG] 解析事件: {event.title} at {event.start_time}")
            except Exception as e:
                print(f"[ERROR] 解析事件失败 {row[0]}: {e}")
        
        return events
    
    def _parse_datetime(self, datetime_str: str) -> datetime:
        """解析日期时间字符串 - 兼容旧版本Python"""
        try:
            # 尝试使用 fromisoformat (Python 3.7+)
            if hasattr(datetime, 'fromisoformat'):
                return datetime.fromisoformat(datetime_str)
            else:
                # 对于旧版本Python，使用其他方法解析
                import dateutil.parser
                return dateutil.parser.parse(datetime_str)
        except:
            # 如果都失败，尝试手动解析
            try:
                # 常见的ISO格式: 2024-01-15 14:30:00
                return datetime.strptime(datetime_str, '%Y-%m-%d %H:%M:%S.%f')
            except:
                try:
                    return datetime.strptime(datetime_str, '%Y-%m-%d %H:%M:%S')
                except:
                    # 最后尝试解析日期部分
                    return datetime.strptime(datetime_str.split(' ')[0], '%Y-%m-%d')
    
    async def get_all_events(self) -> List[CalendarEvent]:
        """获取所有事件（用于调试）"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM events ORDER BY start_time')
        rows = cursor.fetchall()
        conn.close()
        
        events = []
        for row in rows:
            try:
                start_time = self._parse_datetime(row[2])
                end_time = self._parse_datetime(row[3])
                
                event = CalendarEvent(
                    id=row[0], title=row[1], 
                    start_time=start_time,
                    end_time=end_time,
                    description=row[4], location=row[5],
                    attendees=json.loads(row[6]) if row[6] else [],
                    reminder_minutes=row[7], recurrence=row[8]
                )
                events.append(event)
            except Exception as e:
                print(f"解析事件失败 {row[0]}: {e}")
        
        return events