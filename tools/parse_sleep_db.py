import sqlite3
from datetime import datetime
import os
import sys
import pandas as pd
from agentscope.message import TextBlock
from agentscope.tool import ToolResponse
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))
from config import Config

def read_sleep_db() -> ToolResponse:
    """
    这是读取用户睡眠数据的工具函数，当你需要查询用户的睡眠数据时，可以调用此函数。
    本工具将读取 SQLite 数据库中的 XIAOMI_SLEEP_TIME_SAMPLE 表，返回 ToolResponse 对象。
    """
    
    db_path = Config['DB_PATH']
    if not os.path.exists(db_path):
        return ToolResponse(success=False, message=f"数据库文件不存在: {db_path}")

    col_desc = {
        'SLEEP_TIME': 'DATETIME - 时间戳（格式化为日期时间）',
        'DEVICE_ID': 'INTEGER - 设备ID',
        'USER_ID': 'INTEGER - 用户ID',
        'WAKEUP_TIME': 'DATETIME - 醒来时间（格式化为日期时间）',
        'IS_AWAKE': 'INTEGER - 是否醒着（布尔/标志）',
        'TOTAL_DURATION': 'INTEGER - 总时长（分钟）',
        'DEEP_SLEEP_DURATION': 'INTEGER - 深度睡眠时长（分钟）',
        'LIGHT_SLEEP_DURATION': 'INTEGER - 浅睡时长（分钟）',
        'REM_SLEEP_DURATION': 'INTEGER - 快速眼动睡眠时长（分钟）',
        'AWAKE_DURATION': 'INTEGER - 清醒时长（分钟）',
    }

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 检查表是否存在
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='XIAOMI_SLEEP_TIME_SAMPLE'")
    if not cursor.fetchall():
        return ToolResponse(success=False, message="XIAOMI_SLEEP_TIME_SAMPLE 表不存在。")

    # 获取列信息
    cursor.execute("PRAGMA table_info(XIAOMI_SLEEP_TIME_SAMPLE)")
    cols_info = cursor.fetchall()
    columns = [c[1] for c in cols_info]

    # 获取所有数据
    cursor.execute("SELECT * FROM XIAOMI_SLEEP_TIME_SAMPLE")
    rows = cursor.fetchall()

    df = pd.DataFrame(rows, columns=columns)
    # 如果存在 TIMESTAMP 列，重命名为 SLEEP_TIME
    if 'TIMESTAMP' in df.columns and 'SLEEP_TIME' not in df.columns:
        df.rename(columns={'TIMESTAMP': 'SLEEP_TIME'}, inplace=True)

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

    if 'SLEEP_TIME' in df.columns:
        df['SLEEP_TIME'] = df['SLEEP_TIME'].apply(_safe_ms_to_datetime_str)
    if 'WAKEUP_TIME' in df.columns:
        df['WAKEUP_TIME'] = df['WAKEUP_TIME'].apply(_safe_ms_to_datetime_str)

    # 不要将列映射（长度为列数）直接赋值给 DataFrame 的列（长度为行数），会导致长度不匹配错误。
    # 我们把列说明保存在一个字典里，并在返回内容中一并提供。
    column_descriptions = {col: col_desc.get(col, '') for col in df.columns}
    conn.close()

    # 返回 DataFrame 的文本表示和列说明字典
    return ToolResponse(
        content=[
            TextBlock(
                type="text",
                text=f"已完成搜索，找到 {len(df)} 条睡眠记录。",
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
        


