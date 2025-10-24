# launcher.py
# 使用 pywebview 创建本地窗口的启动器：后台启动 Quart 服务并在原生窗口中显示 Web 界面

import multiprocessing
import time
import urllib.request
import sys
import webbrowser

try:
    import webview
except Exception:
    webview = None

from app import app

HOST = '127.0.0.1'
PORT = 5000
URL = f'http://{HOST}:{PORT}/'


def start_server():
    # 以非 reloader 模式启动，适合打包后的 exe
    app.run(host=HOST, port=PORT, use_reloader=False)


def wait_for_service(timeout=10.0, interval=0.1):
    waited = 0.0
    while waited < timeout:
        try:
            with urllib.request.urlopen(URL, timeout=1):
                return True
        except Exception:
            time.sleep(interval)
            waited += interval
    return False


def open_in_browser():
    webbrowser.open(URL)


def open_in_webview():
    # 创建并启动 pywebview 窗口（阻塞调用）
    def create():
        webview.create_window('智能健康系统', URL)

    # webview.start 会阻塞直到窗口关闭
    webview.start(create)


if __name__ == '__main__':
    # 在 Windows 上，当程序被 PyInstaller 等工具打包为 frozen 可执行文件时，
    # 需要调用 multiprocessing.freeze_support() 来正确初始化子进程。
    multiprocessing.freeze_support()
    # 在单独进程中启动服务，避免 Quart 在非主线程尝试注册 signal 处理器（在 exe 中会抛出异常）
    srv_process = multiprocessing.Process(target=start_server, daemon=True)
    srv_process.start()

    # 等待服务就绪
    ready = wait_for_service(timeout=15.0)

    if ready and webview is not None:
        try:
            open_in_webview()
        except Exception:
            # 如果 pywebview 在某些环境（打包或缺少依赖）失败，则回退到系统浏览器
            open_in_browser()
    else:
        # pywebview 未安装或服务未就绪：回退到默认浏览器并保持进程
        open_in_browser()

    # 保持主进程，等待子进程结束或用户退出
    try:
        srv_process.join()
    except KeyboardInterrupt:
        # 在 Windows 上优雅终止子进程
        try:
            srv_process.terminate()
        except Exception:
            pass
        sys.exit(0)
