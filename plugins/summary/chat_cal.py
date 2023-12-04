import os
import sqlite3
from bot import bot_factory
from bridge.bridge import Bridge
from bridge.context import ContextType
from channel.chat_message import ChatMessage
from config import conf
from plugins import *
from bridge.context import ContextType
from bridge.reply import Reply, ReplyType
import datetime
from common.log import logger
import plugins
import openai
import time


@plugins.register(
    name="c_summary",
    desc="A plugin that summarize",
    version="0.1.0",
    author="cc",
    desire_priority=60
)
class ChatStatistics(Plugin):
    def __init__(self):
        super().__init__()
        
        curdir = os.path.dirname(__file__)
        db_path = os.path.join(curdir, "chat.db")
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        c = self.conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS chat_records
                    (sessionid TEXT, msgid INTEGER, user TEXT, content TEXT, type TEXT, timestamp INTEGER, is_triggered INTEGER,
                    PRIMARY KEY (sessionid, msgid))''')
        
        # 后期增加了is_triggered字段，这里做个过渡，这段代码某天会删除
        c = c.execute("PRAGMA table_info(chat_records);")
        column_exists = False
        for column in c.fetchall():
            logger.debug("[Summary] column: {}" .format(column))
            if column[1] == 'is_triggered':
                column_exists = True
                break
        if not column_exists:
            self.conn.execute("ALTER TABLE chat_records ADD COLUMN is_triggered INTEGER DEFAULT 0;")
            self.conn.execute("UPDATE chat_records SET is_triggered = 0;")
        self.openai_api_key = conf().get("open_ai_api_key")
        logger.info(f"[csummary] openai_api_key: {self.openai_api_key}")
        self.openai_api_base = conf().get("open_ai_api_base", "https://api.openai.com/v1")
        self.conn.commit()
        self.handlers[Event.ON_HANDLE_CONTEXT] = self.on_handle_context
        self.handlers[Event.ON_RECEIVE_MESSAGE] = self.on_receive_message
        logger.info("[Summary] inited")

    def _insert_record(self, session_id, msg_id, user, content, msg_type, timestamp, is_triggered = 0):
        c = self.conn.cursor()
        logger.debug("[Summary] insert record: {} {} {} {} {} {} {}" .format(session_id, msg_id, user, content, msg_type, timestamp, is_triggered))
        c.execute("INSERT OR REPLACE INTO chat_records VALUES (?,?,?,?,?,?,?)", (session_id, msg_id, user, content, msg_type, timestamp, is_triggered))
        self.conn.commit()
    
    def _get_records(self, session_id):
        # 获取当天的起始时间戳
        start_of_day = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        start_timestamp = int(start_of_day.timestamp())
        # 获取当天的聊天记录
        c = self.conn.cursor()
        c.execute("SELECT * FROM chat_records WHERE sessionid=? and timestamp>=? ORDER BY timestamp DESC", (session_id, start_timestamp))
        return c.fetchall()


    def on_receive_message(self, e_context: EventContext):
        context = e_context['context']
        cmsg : ChatMessage = e_context['context']['msg']
        username = None
        session_id = cmsg.from_user_id
        if conf().get('channel_type', 'wx') == 'wx' and cmsg.from_user_nickname is not None:
            session_id = cmsg.from_user_nickname # itchat channel id会变动，只好用群名作为session id
        logger.debug(f"session_id: {session_id}")
        if context.get("isgroup", False):
            username = cmsg.actual_user_nickname
            if username is None:
                username = cmsg.actual_user_id
        else:
            username = cmsg.from_user_nickname
            if username is None:
                username = cmsg.from_user_id

        self._insert_record(session_id, cmsg.msg_id, username, context.content, str(context.type), cmsg.create_time)
        # logger.debug("[Summary] {}:{} ({})" .format(username, context.content, session_id))

# 在类中添加一个新的辅助方法
    def _get_session_id(self, chat_message: ChatMessage):
        session_id = chat_message.from_user_id
        if conf().get('channel_type', 'wx') == 'wx' and chat_message.from_user_nickname:
            session_id = chat_message.from_user_nickname
        return session_id

    def on_handle_context(self, e_context: EventContext):
        if e_context['context'].type != ContextType.TEXT:
            return

        content = e_context['context'].content
        chat_message: ChatMessage = e_context['context']['msg']
        username = chat_message.actual_user_nickname or chat_message.from_user_id
        session_id = self._get_session_id(chat_message)

        # 解析用户请求
        if "总结群聊" in content:
            logger.debug("开始总结群聊...")
            result = self.summarize_group_chat(session_id, 100)  # 总结最近100条群聊消息
            logger.debug("总结群聊结果: {}".format(result))
            _set_reply_text(result, e_context, level=ReplyType.TEXT)
        elif "我的聊天" in content:
            self.summarize_user_chat(username, session_id)  # 总结用户当天的聊天
        else:
            _set_reply_text("我不知道你在说什么，请问你想问什么？", e_context, level=ReplyType.TEXT)



    def summarize_group_chat(self, session_id, count):
        # 从 _get_records 方法获取当天的所有聊天记录
        all_records = self._get_records(session_id)
        # 从所有记录中提取最新的 count 条记录，并只获取 user, content, timestamp 字段
        recent_records = [{"user": record[2], "content": record[3], "timestamp": record[5]} for record in all_records[:count]]
        logger.debug("recent_records: {}".format(recent_records))
        # 构建 ChatGPT 需要的消息格式
        messages = [
            {"role": "system", "content": "你是一个聊天记录分析总结专家，要根据获取到聊天记录，将时间段内的聊天内容的主要信息提炼出来。适当使用emoji让生成的总结更生动。文本要连贯、排版要结构清晰。"}
        ]
        messages.extend([
            {"role": "user", "content": f"[{datetime.datetime.fromtimestamp(record['timestamp']).strftime('%Y-%m-%d %H:%M:%S')}] {record['user']} said: {record['content']}"} 
            for record in recent_records
        ])

        # 设置 OpenAI API 密钥和基础 URL
        openai.api_key = self.openai_api_key
        openai.api_base = self.openai_api_base

        logger.debug(f"Summarizing messages: {messages}")

        # 调用 OpenAI ChatGPT
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo-0613",
            messages=messages
        )

        logger.debug(f"Summary response: {response}")
        message = response["choices"][0]["message"]['content']  # 获取模型返回的消息
        message_json = json.dumps(message)
        # 返回 ChatGPT 生成的总结
        return message_json

    # def summarize_user_chat(self, username, session_id):
    #     # 从数据库中获取用户username今天的聊天记录并进行总结
    #     start_of_day = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    #     start_timestamp = int(start_of_day.timestamp())
    #     records = self._get_records(session_id, start_timestamp=start_timestamp)
    #     user_records = [record for record in records if record[2] == username]
    #     # ... 总结逻辑 ...

    def get_help_text(self, verbose=False, **kwargs):
        help_text = "聊天记录统计插件。\n"
        if verbose:
            help_text += "使用方法: 输入特定命令以获取聊天统计信息，例如每个用户的发言数量。"
        return help_text

def _set_reply_text(content: str, e_context: EventContext, level: ReplyType = ReplyType.ERROR):
    reply = Reply(level, content)
    e_context["reply"] = reply
    e_context.action = EventAction.BREAK_PASS
# 其他必要的插件逻辑
