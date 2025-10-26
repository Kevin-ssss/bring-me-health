import sqlite3
from datetime import datetime
import os
import sys
import pandas as pd
from agentscope.message import TextBlock
from agentscope.tool import ToolResponse
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))
from config import Config

def read_heart_rate_db() -> ToolResponse:
    """
    这是读取用户步数和心率数据的工具函数，当你需要查询用户的运动和心率数据时，可以调用此函数。
    本工具将读取 SQLite 数据库中的 XIAOMI_DAILY_SUMMARY_SAMPLE 表，返回 ToolResponse 对象。
    """
    
    db_path = Config['DB_PATH']
    if not os.path.exists(db_path):
        return ToolResponse(TextBlock(text=f"数据库文件不存在: {db_path}"))

    col_desc = {
        'TIMESTAMP': 'INTEGER - 时间戳（格式化为日期时间）',
        'DEVICE_ID': 'INTEGER - 设备ID',
        'USER_ID': 'INTEGER - 用户ID',
        'TIMEZONE': 'INTEGER - 时区',
        'STEPS': 'INTEGER - 步数',
        'HR_RESTING': 'INTEGER - 静息心率',
        'HR_MAX': 'INTEGER - 最大心率',
        'HR_MAX_TS': 'INTEGER - 最大心率发生的时间戳（格式化为日期时间）',
        'HR_MIN': 'INTEGER - 最小心率',
        'HR_MIN_TS': 'INTEGER - 最小心率发生的时间戳（格式化为日期时间）',
        'HR_AVG': 'INTEGER - 平均心率'
    }

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 检查表是否存在
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='XIAOMI_DAILY_SUMMARY_SAMPLE'")
    if not cursor.fetchall():
        return ToolResponse(TextBlock(text="XIAOMI_DAILY_SUMMARY_SAMPLE 表不存在。"))

    # 获取列信息
    cursor.execute("PRAGMA table_info(XIAOMI_DAILY_SUMMARY_SAMPLE)")
    cols_info = cursor.fetchall()
    columns = [c[1] for c in cols_info][0:10]

    # 获取所有数据
    cursor.execute("SELECT * FROM XIAOMI_DAILY_SUMMARY_SAMPLE")
    rows = cursor.fetchall()

    df = pd.DataFrame(rows, columns=columns)[columns]

    # 内嵌一个更稳健的毫秒 -> 日期字符串转换器，能处理 None/NaN/空字符串/异常值
    def _safe_ms_to_datetime_str(ts_ms, fmt: str = "%Y-%m-%d %H:%M:%S"):
        try:
            if ts_ms is None:
                return None
            # pandas NA/NaN
            if pd.isna(ts_ms):
                return None
            s = str(ts_ms).strip()
            if s == '':
                return None
            val = int(float(s))
            return datetime.fromtimestamp(val / 1000.0).strftime(fmt)
        except Exception:
            # 如果转换失败，返回 None，这样不会打断整个流程
            return None

    if 'TIMESTAMP' in df.columns:
        df['TIMESTAMP'] = df['TIMESTAMP'].apply(_safe_ms_to_datetime_str)
    if 'HR_MAX_TS' in df.columns:
        df['HR_MAX_TS'] = df['HR_MAX_TS'].apply(_safe_ms_to_datetime_str)
    if 'HR_MIN_TS' in df.columns:
        df['HR_MIN_TS'] = df['HR_MIN_TS'].apply(_safe_ms_to_datetime_str)

    # 不要将列映射（长度为列数）直接赋值给 DataFrame 的列（长度为行数），会导致长度不匹配错误。
    # 我们把列说明保存在一个字典里，并在返回内容中一并提供。
    column_descriptions = {col: col_desc.get(col, '') for col in df.columns}
    conn.close()

    # 返回 DataFrame 的文本表示和列说明字典
    return ToolResponse(
        content=[
            TextBlock(
                type="text",
                text=f"已完成搜索，找到 {len(df)} 条步数和心率记录。",
            ),
            TextBlock(
                type="text",
                text=df.to_string(),
            ),
            TextBlock(
                type="text",
                text=f"列说明: {column_descriptions}",
            ),
        ]
    )
        


