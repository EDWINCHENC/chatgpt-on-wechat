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

class ChatStatistics(Plugin):
    def __init__(self):
        super().__init__()
        
        # 数据库初始化
        curdir = os.path.dirname(__file__)
        db_path = os.path.join(curdir, "chat.db")
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        c = self.conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS chat_records
                    (sessionid TEXT, msgid INTEGER, user TEXT, content TEXT, type TEXT, timestamp INTEGER,
                    PRIMARY KEY (sessionid, msgid))''')
        self.conn.commit()

    def _insert_record(self, session_id, msg_id, user, content, msg_type, timestamp):
        c = self.conn.cursor()
        c.execute("INSERT OR REPLACE INTO chat_records VALUES (?,?,?,?,?,?,?)", 
                  (session_id, msg_id, user, content, msg_type, timestamp))
        logger.debug("[Summary] insert record: {} {} {} {} {} {} {}" .format(session_id, msg_id, user, content, msg_type, timestamp))
        self.conn.commit()

    def on_receive_message(self, e_context: EventContext):
        context = e_context['context']
        cmsg: ChatMessage = context['msg']
        session_id = cmsg.from_user_id

        # 处理群聊和私聊的用户名
        if context.get("isgroup", False):
            username = cmsg.actual_user_nickname or cmsg.actual_user_id
        else:
            username = cmsg.from_user_nickname or cmsg.from_user_id

        # 插入记录
        self._insert_record(session_id, cmsg.msg_id, username, context.content, str(context.type), cmsg.create_time)

    def get_chat_statistics(self, session_id):
        c = self.conn.cursor()
        c.execute("SELECT user, COUNT(*) FROM chat_records WHERE sessionid=? GROUP BY user", (session_id,))
        stats = c.fetchall()
        return stats
    
    def _get_todays_records(self, session_id):
    # 获取当前日期的开始时间戳
        today_start = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        start_timestamp = int(today_start.timestamp())

        # 查询当天的聊天记录
        c = self.conn.cursor()
        c.execute("SELECT * FROM chat_records WHERE sessionid=? and timestamp>=? ORDER BY timestamp", 
                    (session_id, start_timestamp))
        return c.fetchall()

    def on_handle_context(self, e_context: EventContext):
        if e_context['context'].type != ContextType.TEXT:
            return

        content = e_context['context'].content
        logger.debug("[ChatStatistics] on_handle_context. content: %s" % content)
        trigger_prefix = conf().get('plugin_trigger_prefix', "$")
        clist = content.split()

        if clist[0].startswith(trigger_prefix) and "统计" in clist[0]:
            msg: ChatMessage = e_context['context']['msg']
            session_id = msg.from_user_id
            if conf().get('channel_type', 'wx') == 'wx' and msg.from_user_nickname is not None:
                session_id = msg.from_user_nickname

            records = self._get_todays_records(session_id)
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
