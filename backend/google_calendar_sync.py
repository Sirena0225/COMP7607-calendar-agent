# google_calendar_sync.py - Google Calendar同步功能
import os
import json
from datetime import datetime
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from models import CalendarEvent

class GoogleCalendarSync:
    def __init__(self, credentials_file=None):
        self.credentials_file = credentials_file or os.getenv('GOOGLE_CALENDAR_CREDENTIALS_FILE')
        self.service = self._get_service()
    
    def _get_service(self):
        """获取Google Calendar服务"""
        if os.getenv('GOOGLE_CALENDAR_CREDENTIALS_JSON'):
            # 从环境变量读取JSON
            credentials_json = json.loads(os.getenv('GOOGLE_CALENDAR_CREDENTIALS_JSON'))
            credentials = Credentials.from_service_account_info(
                credentials_json,
                scopes=['https://www.googleapis.com/auth/calendar']
            )
        elif self.credentials_file:
            # 从文件读取
            credentials = Credentials.from_service_account_file(
                self.credentials_file,
                scopes=['https://www.googleapis.com/auth/calendar']
            )
        else:
            raise ValueError("需要提供Google Calendar凭据")
        
        return build('calendar', 'v3', credentials=credentials)
    
    def sync_event_to_google(self, event: CalendarEvent) -> bool:
        """将事件同步到Google Calendar"""
        try:
            event_body = {
                'summary': event.title,
                'location': event.location,
                'description': event.description,
                'start': {
                    'dateTime': event.start_time.isoformat(),
                    'timeZone': 'Asia/Shanghai',  # 根据需要调整时区
                },
                'end': {
                    'dateTime': event.end_time.isoformat(),
                    'timeZone': 'Asia/Shanghai',
                },
            }
            
            # 插入事件到主日历
            created_event = self.service.events().insert(
                calendarId='primary',
                body=event_body
            ).execute()
            
            print(f"事件已同步到Google Calendar: {created_event.get('htmlLink')}")
            return True
            
        except Exception as e:
            print(f"同步到Google Calendar失败: {e}")
            return False
    
    def get_events_from_google(self, time_min=None, time_max=None):
        """从Google Calendar获取事件"""
        try:
            # 设置时间范围
            if time_min is None:
                time_min = datetime.now().isoformat() + 'Z'
            if time_max is None:
                from datetime import timedelta
                time_max = (datetime.now() + timedelta(days=7)).isoformat() + 'Z'
            
            events_result = self.service.events().list(
                calendarId='primary',
                timeMin=time_min,
                timeMax=time_max,
                maxResults=10,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            events = events_result.get('items', [])
            return events
            
        except Exception as e:
            print(f"从Google Calendar获取事件失败: {e}")
            return []
    
    def list_recent_events(self):
        """列出最近的事件"""
        events = self.get_events_from_google()
        
        if not events:
            print('没有找到事件。')
            return
        
        print('最近的事件:')
        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            print(f'{start} - {event["summary"]}')