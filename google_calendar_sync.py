# google_calendar_sync.py - Google Calendar同步功能
# google_calendar_sync.py
import os
import json
from datetime import datetime
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from models import CalendarEvent


class GoogleCalendarSync:
    def __init__(self, credentials_file=None):
        print("[DEBUG] 初始化 GoogleCalendarSync...")

        # 🛠️ 修复：使用基于项目根目录的绝对路径
        if credentials_file is None:
            # 获取项目根目录
            project_root = os.path.dirname(os.path.abspath(__file__))
            self.credentials_file = os.path.join(project_root, 'google-calendar-api.json')
        else:
            self.credentials_file = credentials_file

        print(f"[DEBUG] 凭据文件路径: {self.credentials_file}")

        self.service = None
        self._initialize_service()

    def _initialize_service(self):
        """初始化Google Calendar服务"""
        print("[DEBUG] 开始初始化Google Calendar服务...")

        try:
            # 检查环境变量
            env_cred = os.getenv('GOOGLE_CALENDAR_CREDENTIALS_JSON')
            print(f"[DEBUG] 环境变量检查: {'已设置' if env_cred else '未设置'}")

            if env_cred:
                print("[DEBUG] 尝试从环境变量加载凭据...")
                try:
                    credentials_info = json.loads(env_cred)
                    credentials = Credentials.from_service_account_info(
                        credentials_info,
                        scopes=['https://www.googleapis.com/auth/calendar']
                    )
                    print("✓ 从环境变量加载Google Calendar凭据成功")

                except Exception as e:
                    print(f"❌ 从环境变量加载凭据失败: {e}")
                    # 继续尝试文件方式
                    env_cred = None

            # 如果没有环境变量或环境变量失败，尝试文件
            if not env_cred:
                print(f"[DEBUG] 检查配置文件: {self.credentials_file}")
                print(f"[DEBUG] 文件是否存在: {os.path.exists(self.credentials_file)}")

                if os.path.exists(self.credentials_file):
                    print("[DEBUG] 尝试从文件加载凭据...")
                    try:
                        credentials = Credentials.from_service_account_file(
                            self.credentials_file,
                            scopes=['https://www.googleapis.com/auth/calendar']
                        )
                        print(f"✓ 从文件加载Google Calendar凭据成功: {self.credentials_file}")

                    except Exception as e:
                        print(f"❌ 从文件加载凭据失败: {e}")
                        print("⚠ Google Calendar凭据未配置")
                        return None
                else:
                    print("⚠ Google Calendar凭据未配置")
                    print(f"   环境变量 GOOGLE_CALENDAR_CREDENTIALS_JSON: {'已设置' if env_cred else '未设置'}")
                    print(f"   配置文件 {self.credentials_file}: 不存在")
                    return None

            # 构建服务
            print("[DEBUG] 构建Google Calendar服务...")
            self.service = build('calendar', 'v3', credentials=credentials)
            print("✓ Google Calendar服务构建成功")

            # 测试连接
            print("[DEBUG] 测试Google Calendar连接...")
            if self._test_connection():
                print("🎉 Google Calendar同步已启用")
            else:
                print("❌ Google Calendar连接测试失败")
                self.service = None

        except Exception as e:
            print(f"❌ Google Calendar服务初始化失败: {e}")
            import traceback
            traceback.print_exc()
            self.service = None

    def _test_connection(self):
        """测试Google Calendar连接"""
        try:
            calendar_list = self.service.calendarList().list().execute()
            calendar_count = len(calendar_list.get('items', []))
            print(f"✓ Google Calendar连接测试成功，找到 {calendar_count} 个日历")
            return True
        except Exception as e:
            print(f"❌ Google Calendar连接测试失败: {e}")
            return False

    def is_available(self):
        """检查Google Calendar服务是否可用"""
        return self.service is not None

    # 其余方法保持不变...

    def sync_event_to_google(self, event: CalendarEvent) -> bool:
        """将事件同步到Google Calendar"""
        if not self.is_available():
            print("⚠ Google Calendar服务不可用，跳过同步")
            return False

        try:
            event_body = {
                'summary': event.title,
                'location': event.location,
                'description': event.description,
                'start': {
                    'dateTime': event.start_time.isoformat(),
                    'timeZone': 'Asia/Shanghai',
                },
                'end': {
                    'dateTime': event.end_time.isoformat(),
                    'timeZone': 'Asia/Shanghai',
                },
            }

            # 如果有参与者，添加到事件
            if event.attendees:
                event_body['attendees'] = [{'email': email} for email in event.attendees]

            # 插入事件到主日历
            created_event = self.service.events().insert(
                calendarId='primary',
                body=event_body
            ).execute()

            print(f"✓ 事件已同步到Google Calendar: {created_event.get('htmlLink')}")
            return True

        except HttpError as e:
            print(f"❌ 同步到Google Calendar失败 (HTTP错误): {e}")
            return False
        except Exception as e:
            print(f"❌ 同步到Google Calendar失败: {e}")
            return False

    def get_events_from_google(self, time_min=None, time_max=None):
        """从Google Calendar获取事件"""
        if not self.is_available():
            print("⚠ Google Calendar服务不可用，无法获取事件")
            return []

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
            print(f"✓ 从Google Calendar获取到 {len(events)} 个事件")
            return events

        except Exception as e:
            print(f"❌ 从Google Calendar获取事件失败: {e}")
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