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

        self.conn.commit()
        self.handlers[Event.ON_HANDLE_CONTEXT] = self.on_handle_context
        self.handlers[Event.ON_RECEIVE_MESSAGE] = self.on_receive_message
        logger.info("[Summary] inited")

    def _insert_record(self, session_id, msg_id, user, content, msg_type, timestamp, is_triggered = 0):
        c = self.conn.cursor()
        logger.debug("[Summary] insert record: {} {} {} {} {} {} {}" .format(session_id, msg_id, user, content, msg_type, timestamp, is_triggered))
        c.execute("INSERT OR REPLACE INTO chat_records VALUES (?,?,?,?,?,?,?)", (session_id, msg_id, user, content, msg_type, timestamp, is_triggered))
        self.conn.commit()
    
    def _get_records(self, session_id, start_timestamp=0, limit=9999):
        c = self.conn.cursor()
        c.execute("SELECT * FROM chat_records WHERE sessionid=? and timestamp>? ORDER BY timestamp DESC LIMIT ?", (session_id, start_timestamp, limit))
        return c.fetchall()

    def on_receive_message(self, e_context: EventContext):
        context = e_context['context']
        cmsg : ChatMessage = e_context['context']['msg']
        username = None
        session_id = cmsg.from_user_id
        if conf().get('channel_type', 'wx') == 'wx' and cmsg.from_user_nickname is not None:
            session_id = cmsg.from_user_nickname # itchat channel id会变动，只好用群名作为session id

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

    def on_handle_context(self, e_context: EventContext):
        if e_context['context'].type != ContextType.TEXT:
            return

        content = e_context['context'].content
        logger.debug("[ChatStatistics] on_handle_context. content: %s" % content)

        cmsg: ChatMessage = e_context['context']['msg']
        session_id = cmsg.from_user_id
        if conf().get('channel_type', 'wx') == 'wx' and cmsg.from_user_nickname is not None:
            session_id = cmsg.from_user_nickname

        # 获取当天的起始时间戳
        start_of_day = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        start_timestamp = int(start_of_day.timestamp())

        records = self._get_records(session_id, start_timestamp=start_timestamp, limit=9999)
        if len(records) == 0:
            reply = Reply(ReplyType.INFO, "今天还没有聊天记录")
        else:
            record_strings = [f"{record[2]} ({datetime.datetime.fromtimestamp(record[5]).strftime('%Y-%m-%d %H:%M:%S')}): {record[3]}" for record in records]
            reply_text = "\n".join(record_strings)
            reply = Reply(ReplyType.TEXT, f"今天的聊天记录如下：\n{reply_text}")

        e_context['reply'] = reply
        e_context.action = EventAction.BREAK_PASS

    def get_help_text(self, verbose=False, **kwargs):
        help_text = "聊天记录统计插件。\n"
        if verbose:
            help_text += "使用方法: 输入特定命令以获取聊天统计信息，例如每个用户的发言数量。"
        return help_text

# 其他必要的插件逻辑
