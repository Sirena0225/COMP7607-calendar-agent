# google_calendar_config.py
import os
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

class GoogleCalendarConfig:
    # 从JSON文件读取凭据
    CREDENTIALS_FILE = "google-calendar-api.json"
    
    # 或从环境变量读取（推荐用于生产环境）
    CREDENTIALS_JSON = os.getenv('GOOGLE_CALENDAR_CREDENTIALS_JSON')
    
    SCOPES = [
        'https://www.googleapis.com/auth/calendar',
        'https://www.googleapis.com/auth/calendar.events'
    ]
    
    def get_credentials(self):
        """获取Google Calendar API凭据"""
        if self.CREDENTIALS_JSON:
            import json
            info = json.loads(self.CREDENTIALS_JSON)
            credentials = Credentials.from_service_account_info(info, scopes=self.SCOPES)
        else:
            credentials = Credentials.from_service_account_file(
                self.CREDENTIALS_FILE, 
                scopes=self.SCOPES
            )
        return credentials
    
    def get_service(self):
        """获取Calendar服务对象"""
        credentials = self.get_credentials()
        service = build('calendar', 'v3', credentials=credentials)
        return service

# example of setting the environment variable:
"""
export GOOGLE_CALENDAR_CREDENTIALS_JSON='{
  "type": "service_account",
  "project_id": "your-project-id",
  "private_key_id": "key-id",
  "private_key": "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n",
  "client_email": "your-service-account@your-project.iam.gserviceaccount.com",
  "client_id": "client-id",
  "auth_uri": "https://accounts.google.com/o/oauth2/auth",
  "token_uri": "https://oauth2.googleapis.com/token"
}'
"""