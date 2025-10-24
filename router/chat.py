from quart import Blueprint, render_template, request, Response
from agents.router_agent import router_agent
import time

chat_bp = Blueprint('chat', __name__)

@chat_bp.route('/')
async def index():
    return await render_template('index.html')

@chat_bp.route('/stream', methods=['POST'])
async def stream_chat():
    user_input = (await request.form).get('message')

    return Response(
        router_agent(user_input),          # 直接传异步生成器
        mimetype='text/plain; charset=utf-8',
        headers={'Cache-Control': 'no-cache'},
    )