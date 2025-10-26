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
        with open(temp_file, 'w', encoding='utf-8') as f:
            f.write(code)

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
        try:
            for root, _, files in os.walk(temp_dir):
                for fname in files:
                    if fname.endswith('.py'):
                        continue
                    src = os.path.join(root, fname)
                    # avoid name collisions by prefixing with uuid if needed
                    dest_name = fname
                    dest = os.path.join(output_dir, dest_name)
                    try:
                        if os.path.exists(dest):
                            # append short uuid to avoid overwrite
                            base, ext = os.path.splitext(dest_name)
                            dest_name = f"{base}_{shortuuid.uuid()}{ext}"
                            dest = os.path.join(output_dir, dest_name)
                        shutil.move(src, dest)
                        moved_files.append(dest)
                    except Exception:
                        # ignore individual file move errors
                        pass
        except Exception:
            pass

        if moved_files:
            stdout_str += "\n<saved_files>" + ",".join(moved_files) + "</saved_files>"

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
