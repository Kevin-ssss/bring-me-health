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
    """在临时脚本中执行用户提供的 Python 代码，并将生成的输出文件持久化到指定目录。

    说明：此函数行为与 agentscope 原生的 `execute_python_code` 一致（在临时目录中
    创建脚本、以子进程运行、捕获 stdout/stderr、处理超时），但额外在临时目录被
    删除前，将所有生成的非 `.py` 文件移动到持久化的 `output_dir`（默认为
    `Config['OUTPUT_DIR']`），以便在脚本执行完成后仍能访问这些文件。

    参数：
        code: 要执行的 Python 源代码（如需返回结果，请在代码中使用 print 输出）。
        timeout: 最大允许执行时间（秒），超时将终止子进程并返回超时信息。
        output_dir: 可选关键字参数，用于覆盖默认的输出目录（例如临时调试用途）。

    返回：
        一个 `ToolResponse`，其内容格式与 agentscope 原始工具一致，包含
        `<returncode>`、`<stdout>`、`<stderr>` 等字段；若有文件被保存，还会在 stdout
        中附加 `<saved_files>...</saved_files>` 标签，列出已保存文件的绝对路径。
    """

    output_dir = kwargs.get('output_dir') or Config.get('OUTPUT_DIR')
    try:
        os.makedirs(output_dir, exist_ok=True)
    except Exception:
        # If we cannot create output dir, fallback to current working dir
        output_dir = os.path.abspath('.')

    temp_dir = tempfile.mkdtemp()
    temp_file = os.path.join(temp_dir, f"tmp_{shortuuid.uuid()}.py")

    # 自动为 matplotlib 配置支持中文的字体（优先使用常见的 Windows 字体），
    # 以避免绘图中的中文显示为方块。若需要自定义字体，可在 Config 中添加路径并传入。
    # Make sure 'Agg' backend is set as the very first matplotlib action.
    # No leading newline: this should be the first line of the temp script.
    prefix = r"""import os, sys
import pathlib
import matplotlib
import matplotlib.font_manager as fm
# 1. 进程级环境变量，任何重新 import 也改不掉
os.environ['MPLBACKEND'] = 'Agg'
# 2. 立即重启 matplotlib 参数并强制 backend
matplotlib.rcParams['backend'] = 'Agg'
matplotlib.use('Agg')
# 3. 立即把 pyplot 也拉进来并关交互
import matplotlib.pyplot as plt
plt.ioff()

# 以下保持你原来的字体逻辑（优先使用 Config 中指定的字体）
try:
    from config import Config as _Config
    font_path_candidates = []
    if _Config.get('CHINESE_FONT_PATH'):
        font_path_candidates.append(_Config.get('CHINESE_FONT_PATH'))
except Exception:
    font_path_candidates = []

font_path_candidates += [
    r"C:\Windows\Fonts\msyh.ttc",
    r"C:\Windows\Fonts\msyh.ttf",
    r"C:\Windows\Fonts\simhei.ttf",
    r"C:\Windows\Fonts\simsun.ttc",
]

for _p in font_path_candidates:
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

    # 添加后缀
    suffix = r"""
save_path = pathlib.Path('output/sleep_analysis.png').resolve()
print('[DEBUG] 准备保存到:', save_path)
print('[DEBUG] 目录存在:', save_path.parent.exists())
print('[DEBUG] 后端:', matplotlib.get_backend())
plt.savefig(save_path, dpi=150)
print('[DEBUG] 保存完成 → 文件大小:', save_path.stat().st_size, '字节')
"""

    # 把前缀后缀用户代码写入临时文件，使得子进程运行时先应用字体设置
    with open(temp_file, 'w', encoding='utf-8') as f:
        f.write(prefix + '\n' + code + '\n' + suffix)

    # Ensure common relative output folders exist in temp_dir so user code
    # that writes to e.g. 'output/...' won't fail with FileNotFoundError.
    try:
        os.makedirs(os.path.join(temp_dir, 'output'), exist_ok=True)
    except Exception:
        pass

    # Start subprocess AFTER the temp file has been closed to avoid holding
    # the script file handle open on Windows (which causes rmtree/cleanup to fail).
    proc = await asyncio.create_subprocess_exec(
        sys.executable,
        '-u',
        temp_file,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=temp_dir,
    )

    try:
        await asyncio.wait_for(proc.wait(), timeout=timeout)
        stdout_bytes, stderr_bytes = await proc.communicate()

        # 1. 先按 GBK 解，失败再用 utf-8 + 忽略/替换
        def safe_decode(bs: bytes) -> str:
            if not bs:
                return ''
            for enc in ('gbk', 'utf-8'):
                try:
                    return bs.decode(enc)
                except UnicodeDecodeError:
                    continue
            # 兜底：utf-8 忽略无法解析的字节
            return bs.decode('utf-8', errors='replace')

        stdout_str = safe_decode(stdout_bytes)
        stderr_str = safe_decode(stderr_bytes)
        returncode = proc.returncode

    except asyncio.TimeoutError:
        stderr_suffix = f"TimeoutError: The code execution exceeded the timeout of {timeout} seconds."
        returncode = -1
        try:
            proc.terminate()
            stdout, stderr = await proc.communicate()
            stdout_str = stdout.decode('utf-8')
            stderr_str = stderr.decode('utf-8')
            if stderr_str:
                stderr_str += f"\n{stderr_suffix}"
            else:
                stderr_str = stderr_suffix
        except ProcessLookupError:
            stdout_str = ''
            stderr_str = stderr_suffix

    # Move non-.py files from temp_dir to output_dir before temp_dir is removed
    moved_files = []
    move_errors = []
    try:
        for root, _, files in os.walk(temp_dir):
            for fname in files:
                if fname.endswith('.py'):
                    continue
                src = os.path.join(root, fname)
                # avoid name collisions by prefixing with uuid if needed
                dest_name = fname
                dest = os.path.join(output_dir, dest_name)
                if os.path.exists(dest):
                    base, ext = os.path.splitext(dest_name)
                    dest_name = f"{base}_{shortuuid.uuid()}{ext}"
                    dest = os.path.join(output_dir, dest_name)

                # Try several strategies because on Windows a just-closed file
                # can still be locked by the OS or antivirus. Retry a few times
                # with a short sleep, then fall back to copy+remove.
                moved = False
                last_exc = None
                for attempt in range(10):
                    try:
                        shutil.move(src, dest)
                        moved_files.append(dest)
                        moved = True
                        break
                    except Exception as e:
                        last_exc = e
                        # small backoff
                        try:
                            # proper async sleep so we actually wait between retries
                            await asyncio.sleep(0.05)
                        except Exception:
                            # if sleep isn't usable for some reason, fallback to time.sleep
                            try:
                                import time as _time

                                _time.sleep(0.05)
                            except Exception:
                                pass

                if not moved:
                    # fallback: try copy then remove
                    try:
                        shutil.copy2(src, dest)
                        try:
                            os.remove(src)
                        except Exception:
                            # If remove fails, leave it; temp dir cleanup will remove later
                            pass
                        moved_files.append(dest)
                        moved = True
                    except Exception as e2:
                        move_errors.append((src, dest, str(last_exc or e2)))
                        # give up on this file
                        continue
    except Exception as e:
        move_errors.append((temp_dir, '', str(e)))

    # Try to cleanup temp_dir explicitly. On Windows it's common that a just-closed
    # file may still be reported as "in use" for a short time by the OS or by
    # antivirus. Retry more times with short backoff. If final attempts fail,
    # record a cleanup warning (not an exception) so caller can proceed.
    cleanup_errors = []
    for _attempt in range(10):
        try:
            shutil.rmtree(temp_dir)
            break
        except Exception as e:
            cleanup_errors.append(str(e))
            try:
                await asyncio.sleep(0.1)
            except Exception:
                try:
                    import time as _time

                    _time.sleep(0.1)
                except Exception:
                    pass
    else:
        # If we failed to remove the temp dir after retries, don't raise —
        # just report it in stderr as a CLEANUP_WARNING so the caller can inspect.
        if cleanup_errors:
            err_msg = f"[CLEANUP_WARNING] temp_dir={temp_dir} errors={cleanup_errors}"
            if stderr_str:
                stderr_str += "\n" + err_msg
            else:
                stderr_str = err_msg

    if moved_files:
        stdout_str += "\n<saved_files>" + ",".join(moved_files) + "</saved_files>"
    if move_errors:
        # Append move errors to stderr so caller can see what happened
        err_lines = [f"MOVE_ERROR src={s} dest={d} err={m}" for (s, d, m) in move_errors]
        if stderr_str:
            stderr_str += "\n" + "\n".join(err_lines)
        else:
            stderr_str = "\n".join(err_lines)

    # 如果没有任何文件被搬出，视为执行失败（常见原因：子进程没有成功生成图片）
    if not moved_files:
        returncode = returncode if 'returncode' in locals() and returncode != 0 else 1
        msg = "[ERROR] 未检测到任何输出图片，请确认代码中调用 plt.savefig('output/xxx.png') 且路径为相对路径。"
        if stderr_str:
            stderr_str += "\n" + msg
        else:
            stderr_str = msg

    return ToolResponse(
        content=[
            TextBlock(
                type='text',
                text=f"<returncode>{returncode}</returncode>"
                f"<stdout>{stdout_str}</stdout>"
                f"<stderr>{stderr_str}</stderr>",
            ),
        ],
    )
