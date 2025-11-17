import sqlite3
from datetime import datetime, timedelta
import json

def check_database_events():
    """检查数据库中的所有事件"""
    conn = sqlite3.connect('calendar.db')
    cursor = conn.cursor()
    
    print("=== 数据库事件检查 ===")
    
    # 查询所有事件
    cursor.execute("SELECT * FROM events ORDER BY start_time")
    rows = cursor.fetchall()
    
    if not rows:
        print("数据库中没有事件")
    else:
        print(f"数据库中找到 {len(rows)} 个事件:")
        for i, row in enumerate(rows, 1):
            print(f"{i}. ID: {row[0]}")
            print(f"   标题: {row[1]}")
            print(f"   开始时间: {row[2]}")
            print(f"   结束时间: {row[3]}")
            print(f"   描述: {row[4]}")
            print(f"   地点: {row[5]}")
            print(f"   参与者: {row[6]}")
            print(f"   提醒时间: {row[7]}")
            print(f"   重复: {row[8]}")
            print(f"   创建时间: {row[9]}")
            print("-" * 50)
    
    conn.close()

def check_specific_time_range():
    """检查特定时间范围内的事件"""
    conn = sqlite3.connect('calendar.db')
    cursor = conn.cursor()
    
    print("\n=== 特定时间范围检查 ===")
    
    # 检查明天的事件
    tomorrow_start = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d 00:00:00')
    tomorrow_end = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d 23:59:59')
    
    print(f"查询时间范围: {tomorrow_start} 到 {tomorrow_end}")
    
    cursor.execute('''
        SELECT * FROM events 
        WHERE start_time >= ? AND start_time <= ?
        ORDER BY start_time
    ''', (tomorrow_start, tomorrow_end))
    
    rows = cursor.fetchall()
    
    if not rows:
        print("在明天时间范围内没有找到事件")
    else:
        print(f"找到 {len(rows)} 个明天的事件:")
        for row in rows:
            print(f"  - {row[1]} at {row[2]}")
    
    conn.close()

if __name__ == "__main__":
    check_database_events()
    check_specific_time_range()