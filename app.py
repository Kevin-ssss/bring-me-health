# app.py
from quart import Quart
from config import Config

app = Quart(__name__)
app.config.from_object(Config)

# 注册蓝图
from router.chat import chat_bp
app.register_blueprint(chat_bp, url_prefix='/')

if __name__ == '__main__':
    # 当直接运行（或打包成 exe 并运行）时，自动在默认浏览器打开应用首页。
    # 实现思路：在单独线程中启动 Quart 服务，然后在主线程轮询直到服务可用，再使用系统默认浏览器打开页面。
    import threading
    import time
    import webbrowser
    import urllib.request
    import sys

    host = '127.0.0.1'
    port = 5000

    def run_app():
        # 关闭 reloader，避免在打包后的 exe 出现双进程
        app.run(host=host, port=port, use_reloader=False)

    t = threading.Thread(target=run_app, daemon=True)
    t.start()

    url = f'http://{host}:{port}/'

    # 等待服务启动（最多 10 秒），一旦可用就打开浏览器
    timeout = 10.0
    waited = 0.0
    interval = 0.1
    while waited < timeout:
        try:
            with urllib.request.urlopen(url, timeout=1) as resp:
                # 服务已响应，打开浏览器并退出等待循环
                webbrowser.open(url)
                break
        except Exception:
            time.sleep(interval)
            waited += interval

    # 如果循环结束时线程仍在运行，则等待（阻塞主线程直到服务线程结束）
    try:
        # 如果用户以控制台方式运行，希望保持主进程活着以便服务继续运行
        t.join()
    except KeyboardInterrupt:
        # 支持 Ctrl+C 退出
        sys.exit(0)