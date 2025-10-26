import asyncio
import os
import sys
import tempfile
import shutil
from typing import Any

import shortuuid

from agentscope.message import TextBlock
from agentscope.tool._response import ToolResponse

# Make sure project root is importable
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))
from config import Config


async def execute_python_code_local(code: str, timeout: float = 300, **kwargs: Any) -> ToolResponse:
    """在临时脚本中执行用户提供的 Python 代码并将生成的非 .py 文件移动到持久化输出目录。

    精简版本：不打印调试信息（避免无关输出），保留 matplotlib 后端和中文字体处理、子进程执行、
    输出文件搬迁与清理逻辑。
    """

    output_dir = kwargs.get('output_dir') or Config.get('OUTPUT_DIR')
    try:
        os.makedirs(output_dir, exist_ok=True)
    except Exception:
        output_dir = os.path.abspath('.')

    temp_dir = tempfile.mkdtemp()
    temp_file = os.path.join(temp_dir, f"tmp_{shortuuid.uuid()}.py")

    # 设置 matplotlib 无头后端并尝试注册常见中文字体（尽量静默失败）
    prefix = r"""import matplotlib
matplotlib.use('Agg')
import os
import matplotlib
import matplotlib.pyplot as plt
plt.ioff()
try:
    from config import Config as _Config
    font_candidates = []
    if _Config.get('CHINESE_FONT_PATH'):
        font_candidates.append(_Config.get('CHINESE_FONT_PATH'))
except Exception:
    font_candidates = []
font_candidates += [
    r"C:\Windows\Fonts\msyh.ttc",
    r"C:\Windows\Fonts\msyh.ttf",
    r"C:\Windows\Fonts\simhei.ttf",
    r"C:\Windows\Fonts\simsun.ttc",
]
import matplotlib.font_manager as fm
for _p in font_candidates:
    try:
        if os.path.exists(_p):
            fm.fontManager.addfont(_p)
            fp = fm.FontProperties(fname=_p)
            plt.rcParams['font.sans-serif'] = [fp.get_name()]
            plt.rcParams['axes.unicode_minus'] = False
            break
    except Exception:
        pass
"""

    # 写入临时执行脚本（仅前缀 + 用户代码），不再添加任何自动打印或额外保存操作
    with open(temp_file, 'w', encoding='utf-8') as f:
        f.write(prefix + '\n' + code)

    # Ensure 'output' exists in temp so user code can write to it
    try:
        os.makedirs(os.path.join(temp_dir, 'output'), exist_ok=True)
    except Exception:
        pass

    proc = await asyncio.create_subprocess_exec(
        sys.executable,
        '-u',
        temp_file,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=temp_dir,
    )

    stdout_str = ''
    stderr_str = ''
    returncode = None

    try:
        # 等待并获取输出，超时会抛出 asyncio.TimeoutError
        stdout_bytes, stderr_bytes = await asyncio.wait_for(proc.communicate(), timeout=timeout)

        def safe_decode(bs: bytes) -> str:
            if not bs:
                return ''
            for enc in ('gbk', 'utf-8'):
                try:
                    return bs.decode(enc)
                except Exception:
                    continue
            return bs.decode('utf-8', errors='replace')

        stdout_str = safe_decode(stdout_bytes)
        stderr_str = safe_decode(stderr_bytes)
        returncode = proc.returncode

        # 简单持久化日志，便于打包后排查（不打印到控制台）
        try:
            log_file = os.path.join(output_dir, 'exec_subproc_output.log')
            with open(log_file, 'a', encoding='utf-8') as _lf:
                from datetime import datetime

                _lf.write('--- EXEC SUBPROC OUTPUT %s ---\n' % datetime.now().isoformat())
                _lf.write(f'returncode={returncode}\n')
                _lf.write('[STDOUT]\n')
                _lf.write(stdout_str + '\n')
                _lf.write('[STDERR]\n')
                _lf.write(stderr_str + '\n')
        except Exception:
            pass

    except asyncio.TimeoutError:
        returncode = -1
        stderr_str = f"TimeoutError: code execution exceeded {timeout} seconds."
        try:
            proc.terminate()
        except Exception:
            pass

    # 将 temp_dir 中的非 .py 文件移动到 output_dir
    moved_files = []
    move_errors = []
    try:
        for root, _, files in os.walk(temp_dir):
            for fname in files:
                if fname.endswith('.py'):
                    continue
                src = os.path.join(root, fname)
                dest_name = fname
                dest = os.path.join(output_dir, dest_name)
                if os.path.exists(dest):
                    base, ext = os.path.splitext(dest_name)
                    dest_name = f"{base}_{shortuuid.uuid()}{ext}"
                    dest = os.path.join(output_dir, dest_name)

                moved = False
                last_exc = None
                for _ in range(6):
                    try:
                        shutil.move(src, dest)
                        moved_files.append(dest)
                        moved = True
                        break
                    except Exception as e:
                        last_exc = e
                        try:
                            await asyncio.sleep(0.05)
                        except Exception:
                            pass

                if not moved:
                    try:
                        shutil.copy2(src, dest)
                        try:
                            os.remove(src)
                        except Exception:
                            pass
                        moved_files.append(dest)
                    except Exception as e2:
                        move_errors.append((src, dest, str(last_exc or e2)))
    except Exception as e:
        move_errors.append((temp_dir, '', str(e)))

    # 清理临时目录（尽量重试几次）
    for _ in range(6):
        try:
            shutil.rmtree(temp_dir)
            break
        except Exception:
            try:
                await asyncio.sleep(0.05)
            except Exception:
                pass

    if moved_files:
        stdout_str = (stdout_str or '') + "\n<saved_files>" + ",".join(moved_files) + "</saved_files>"
    if move_errors:
        err_lines = [f"MOVE_ERROR src={s} dest={d} err={m}" for (s, d, m) in move_errors]
        stderr_str = (stderr_str or '') + '\n' + '\n'.join(err_lines)

    if not moved_files:
        # 如果没有任何输出文件，返回非零并给出简短提示（不打印额外调试）
        returncode = returncode if returncode is not None and returncode != 0 else 1
        msg = "[ERROR] 未检测到任何输出文件。请确认脚本将文件保存到相对路径 'output/...'。"
        stderr_str = (stderr_str or '') + ('\n' + msg if stderr_str else msg)

    return ToolResponse(
        content=[
            TextBlock(
                type='text',
                text=(f"<returncode>{returncode}</returncode>"
                      f"<stdout>{stdout_str}</stdout>"
                      f"<stderr>{stderr_str}</stderr>"),
            ),
        ],
    )
