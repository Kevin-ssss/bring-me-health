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

    output_dir = kwargs.get('output_dir') or Config.get('OUTPUT_DIR') or os.path.abspath('./output')
    try:
        os.makedirs(output_dir, exist_ok=True)
    except Exception:
        # If we cannot create output dir, fallback to current working dir
        output_dir = os.path.abspath('.')

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_file = os.path.join(temp_dir, f"tmp_{shortuuid.uuid()}.py")

        # 自动为 matplotlib 配置支持中文的字体（优先使用常见的 Windows 字体），
        # 以避免绘图中的中文显示为方块。若需要自定义字体，可在 Config 中添加路径并传入。
        font_prefix = r"""
import os
try:
    import matplotlib
    import matplotlib.font_manager as fm
    # 优先使用用户配置（若存在）
    try:
        from config import Config as _Config
        font_path_candidates = []
        if _Config.get('CHINESE_FONT_PATH'):
            font_path_candidates.append(_Config.get('CHINESE_FONT_PATH'))
    except Exception:
        font_path_candidates = []

    # 常见 Windows 字体路径
    font_path_candidates += [
        r"C:\\Windows\\Fonts\\msyh.ttc",
        r"C:\\Windows\\Fonts\\msyh.ttf",
        r"C:\\Windows\\Fonts\\simhei.ttf",
        r"C:\\Windows\\Fonts\\simsun.ttc",
    ]

    for _p in font_path_candidates:
        try:
            if os.path.exists(_p):
                fm.fontManager.addfont(_p)
                fp = fm.FontProperties(fname=_p)
                matplotlib.rcParams['font.sans-serif'] = [fp.get_name()]
                matplotlib.rcParams['axes.unicode_minus'] = False
                break
        except Exception:
            continue
except Exception:
    pass
"""

        # 把前缀和用户代码写入临时文件，使得子进程运行时先应用字体设置
        with open(temp_file, 'w', encoding='utf-8') as f:
            f.write(font_prefix + '\n' + code)

        # Ensure common relative output folders exist in temp_dir so user code
        # that writes to e.g. 'output/...' won't fail with FileNotFoundError.
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

        try:
            await asyncio.wait_for(proc.wait(), timeout=timeout)
            stdout, stderr = await proc.communicate()
            stdout_str = stdout.decode('utf-8')
            stderr_str = stderr.decode('utf-8')
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
                    for attempt in range(5):
                        try:
                            shutil.move(src, dest)
                            moved_files.append(dest)
                            moved = True
                            break
                        except Exception as e:
                            last_exc = e
                            # small backoff
                            try:
                                asyncio.sleep(0.05)
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

        if moved_files:
            stdout_str += "\n<saved_files>" + ",".join(moved_files) + "</saved_files>"
        if move_errors:
            # Append move errors to stderr so caller can see what happened
            err_lines = [f"MOVE_ERROR src={s} dest={d} err={m}" for (s, d, m) in move_errors]
            if stderr_str:
                stderr_str += "\n" + "\n".join(err_lines)
            else:
                stderr_str = "\n".join(err_lines)

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
