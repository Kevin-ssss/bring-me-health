# launcher.py
# 极简启动器：后台起 Quart，服务就绪后直接打开系统默认浏览器

import multiprocessing
import time
import urllib.request
import webbrowser
import sys

from app import app

HOST = '127.0.0.1'
PORT = 5000
URL = f'http://{HOST}:{PORT}/'


def start_server():
    # 禁用 reloader，适合打包成 exe
    app.run(host=HOST, port=PORT, use_reloader=False)


def wait_for_service(timeout=15.0, interval=0.1):
    """轮询直到服务返回 200"""
    waited = 0.0
    while waited < timeout:
        try:
            with urllib.request.urlopen(URL, timeout=1):
                return True
        except Exception:
            time.sleep(interval)
            waited += interval
    return False


if __name__ == '__main__':
    multiprocessing.freeze_support()

    # 后台启动 Quart
    srv = multiprocessing.Process(target=start_server, daemon=True)
    srv.start()

    # 等待服务就绪
    if wait_for_service():
        webbrowser.open(URL)          # 直接拉起默认浏览器
    else:
        print('服务启动超时，请手动打开', URL, file=sys.stderr)

    # 主进程保持运行，直到服务器子进程结束或 Ctrl+C
    try:
        srv.join()
    except KeyboardInterrupt:
        srv.terminate()
        sys.exit(0)