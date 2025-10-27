# app.py
from quart import Quart
from config import Config

app = Quart(__name__)
app.config.from_object(Config)

# 注册蓝图
from router.chat import chat_bp
app.register_blueprint(chat_bp, url_prefix='/')