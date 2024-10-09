import os
import sqlite3
# from bot import bot_factory
# from bridge.bridge import Bridge
from bridge.context import ContextType
from channel.chat_message import ChatMessage
# from config import conf
from plugins import *
from bridge.context import ContextType
from bridge.reply import Reply, ReplyType
import datetime
from common.log import logger
import plugins
# import openai
from collections import Counter
# from .lib import wxmsg as wx
from .lib.model_factory import ModelGenerator
import re



@plugins.register(
    name="c_summary",
    desc="A plugin that summarize",
    version="0.1.0",
    author="cc",
    desire_priority=70
)


class ChatStatistics(Plugin):
    def __init__(self):
        super().__init__()

        # 设置数据库路径和API配置
        curdir = os.path.dirname(__file__)
        self.db_path = os.path.join(curdir, "chat.db")

        config_path = os.path.join(curdir, "config.json")
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
            logger.info(f"[c_summary] config content: {config}")
        self.c_model = ModelGenerator()

        # 初始化数据库
        self.initialize_database()

        # 设置事件处理器
        self.handlers[Event.ON_HANDLE_CONTEXT] = self.on_handle_context
        self.handlers[Event.ON_RECEIVE_MESSAGE] = self.on_receive_message

        # 记录初始化信息
        logger.info("[c_summary] Initialized")

    def initialize_database(self):
        """初始化数据库，创建所需表格和列"""
        try:
            with sqlite3.connect(self.db_path, check_same_thread=False) as conn:
                c = conn.cursor()
                # 创建表
                c.execute('''CREATE TABLE IF NOT EXISTS chat_records
                            (sessionid TEXT, msgid INTEGER, user TEXT, content TEXT, type TEXT, timestamp INTEGER, is_triggered INTEGER,
                            PRIMARY KEY (sessionid, msgid))''')
                
                # 检查并添加新列
                c.execute("PRAGMA table_info(chat_records);")
                if not any(column[1] == 'is_triggered' for column in c.fetchall()):
                    c.execute("ALTER TABLE chat_records ADD COLUMN is_triggered INTEGER DEFAULT 0;")
        except Exception as e:
            logger.error(f"Database initialization error: {e}")

    def _insert_record(self, session_id, msg_id, user, content, msg_type, timestamp, is_triggered=0):
        """向数据库中插入一条新记录"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                c = conn.cursor()
                c.execute("INSERT OR REPLACE INTO chat_records VALUES (?,?,?,?,?,?,?)", 
                          (session_id, msg_id, user, content, msg_type, timestamp, is_triggered))
            logger.debug("insert chat record to db: %s", (session_id, msg_id, user, content, msg_type, timestamp, is_triggered))
        except Exception as e:
            logger.error(f"Error inserting record: {e}")

    def _get_records(self, session_id, excluded_users=None, specific_day=None):
        """获取指定会话的聊天记录，排除特定用户列表中的用户，可选特定日期"""
        if excluded_users is None:
            excluded_users = ["Oʀ ."]  # 默认排除的用户列表

        if specific_day is None:
            specific_day = datetime.datetime.now()

        start_of_day = specific_day.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = specific_day.replace(hour=23, minute=59, second=59, microsecond=999999)
        start_timestamp = int(start_of_day.timestamp())
        end_timestamp = int(end_of_day.timestamp())

        try:
            with sqlite3.connect(self.db_path) as conn:
                c = conn.cursor()

                # 构建排除用户的 SQL 条件
                excluded_users_placeholder = ','.join('?' for _ in excluded_users)
                query = f"SELECT * FROM chat_records WHERE sessionid=? AND timestamp BETWEEN ? AND ? AND user NOT IN ({excluded_users_placeholder}) ORDER BY timestamp DESC"

                # 准备查询参数
                query_params = [session_id, start_timestamp, end_timestamp] + excluded_users

                # 执行查询
                c.execute(query, query_params)
                return c.fetchall()

        except Exception as e:
            logger.error(f"Error fetching records: {e}")
            return []


    def on_receive_message(self, e_context: EventContext):
        context = e_context['context']
        cmsg : ChatMessage = e_context['context']['msg']
        username = None
        session_id = cmsg.from_user_id
        if conf().get('channel_type', 'wx') == 'wx' and cmsg.from_user_nickname is not None:
            session_id = cmsg.from_user_nickname # itchat channel id会变动，只好用群名作为session id
        # logger.debug(f"session_id: {session_id}")
        if context.get("isgroup", False):
            username = cmsg.actual_user_nickname
            if username is None:
                username = cmsg.actual_user_id
        else:
            username = cmsg.from_user_nickname
            if username is None:
                username = cmsg.from_user_id

        self._insert_record(session_id, cmsg.msg_id, username, context.content, str(context.type), cmsg.create_time)
        logger.debug("[Summary] {}:{} ({})" .format(username, context.content, session_id))

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
        # username = chat_message.actual_user_nickname or chat_message.from_user_id
        session_id = self._get_session_id(chat_message)
        prefix = "查群聊关键词"

        # 解析用户请求
        if "总结群聊" in content:
            logger.debug("开始总结群聊...")
            result = remove_markdown(self.summarize_group_chat(session_id, 100) ) # 总结最近100条群聊消息
            logger.debug("总结群聊结果: {}".format(result))
            _set_reply_text(result, e_context, level=ReplyType.TEXT)
            
        elif "群聊统计" in content:
            logger.debug("开始进行群聊统计...")
            ranking_results = self.get_chat_activity_ranking(session_id)
            logger.debug("群聊统计结果: {}".format(ranking_results))
            _set_reply_text(ranking_results, e_context, level=ReplyType.TEXT)
            
        elif content.startswith(prefix):
            # 直接提取关键词
            logger.debug("开始分析群聊关键词...")
            keyword = content[len(prefix):].strip()           
            if keyword:
                keyword_summary = remove_markdown(self.analyze_keyword_usage(keyword))
                _set_reply_text(keyword_summary, e_context, level=ReplyType.TEXT)
            else:
                _set_reply_text("请提供一个有效的关键词。", e_context, level=ReplyType.TEXT)

        else:
            # 使用正则表达式检查是否符合 "@xxx的聊天" 格式
            match = re.match(r"@([\w\s]+)的聊天$", content)
            if match:
                nickname = match.group(1).strip()
                logger.debug(f"开始分析群员{nickname}的聊天记录...")
                user_summary = remove_markdown(self.analyze_specific_user_usage(nickname))
                logger.debug(f"群员{nickname}的聊天记录分析结果: {user_summary}")
                _set_reply_text(user_summary, e_context, level=ReplyType.TEXT)
            else:
                e_context.action = EventAction.CONTINUE

    def summarize_group_chat(self, session_id, count):
        # 从 _get_records 方法获取当天的所有聊天记录
        all_records = self._get_records(session_id)
        # 从所有记录中提取最新的 count 条记录，并只获取 user, content, timestamp 字段
        recent_records = [{"user": record[2], "content": record[3], "timestamp": record[5]} for record in all_records[:count]]
        logger.debug("recent_records: {}".format(recent_records))
        
        # 将所有聊天记录合并成一个字符串
        combined_content = "\n".join(
            f"[{datetime.datetime.fromtimestamp(record['timestamp']).strftime('%Y-%m-%d %H:%M:%S')}] {record['user']} said: {record['content']}"
            for record in recent_records
        )
        prompt = "你是一个群聊聊天记录分析总结助手，要根据获取到的聊天记录，将时间段内的聊天内容的主要信息提炼出来，适当使用emoji让生成的总结更生动。可以先用50字左右总结你认为最精华的聊天话题和内容。然后适当提炼总结3个左右群聊的精华主题/标题+聊天内容，标题用emoji美化。最后点点名一下表现活跃的一个群成员，并点评他的聊天记录，在总结的末尾单独一行，搭配emoji展示3-5个核心关键词（可以是活跃的群友名字、关键话题等）,并进行一句话精华点评（搭配emoji)。 总体要求：总结的文本要连贯、排版要段落结构清晰。总体字数不超过180字。"
        function_response = self.c_model._generate_model_analysis(prompt, combined_content)           
        return function_response

    def get_chat_activity_ranking(self, session_id):
        try:
            # 定义要排除的用户列表
            excluded_users = ["Oʀ ."]
            # 获取今天的聊天记录
            today_records = self._get_records(session_id)
            today_count = len(today_records)  # 计算今日聊天记录总条数

            # 获取昨天的聊天记录
            yesterday = datetime.datetime.now() - datetime.timedelta(days=1)
            yesterday_records = self._get_records(session_id, specific_day=yesterday)
            yesterday_count = len(yesterday_records)  # 计算昨日聊天记录总条数

            # 计算今日与昨日聊天量的百分比变化
            percent_change = ((today_count - yesterday_count) / yesterday_count * 100) if yesterday_count > 0 else float('inf')
            # percent_change_str = f"+{percent_change:.0f}%" if percent_change >= 0 else f"{percent_change:.0f}%"
            percent_change_str = f"{percent_change:+.2f}%"
            # 组装今日聊天榜信息和昨日数据
            today_info = f"😈 今日群员聊天榜🏆 总 {today_count} 条"
            change_emoji = "🔺" if percent_change >= 0 else "🔻"
            yesterday_info = f"😴 较昨日: {yesterday_count} 条 {percent_change_str}"

            # 获取历史单日最高聊天量和对应用户
            with sqlite3.connect(self.db_path) as conn:
                c = conn.cursor()
                excluded_users_placeholder = ','.join('?' for _ in excluded_users)
                
                # 查询历史单日用户发送消息最高记录，排除特定用户，限定特定session_id
                c.execute(f"""
                    SELECT user, COUNT(*) as count, strftime('%Y-%m-%d', timestamp, 'unixepoch') as date 
                    FROM chat_records 
                    WHERE sessionid = ? AND user NOT IN ({excluded_users_placeholder})
                    GROUP BY date, user 
                    ORDER BY count DESC 
                    LIMIT 1
                """, [session_id] + excluded_users)
                top_user_record = c.fetchone()
                top_user, top_user_count, top_date = top_user_record if top_user_record else ("无记录", 0, "无日期")

                # 查询特定session_id下历史单日聊天量最高的记录
                c.execute(f"""
                    SELECT COUNT(*) as count, strftime('%Y-%m-%d', timestamp, 'unixepoch') as date 
                    FROM chat_records 
                    WHERE sessionid = ? AND user NOT IN ({excluded_users_placeholder})
                    GROUP BY date 
                    ORDER BY count DESC 
                    LIMIT 1
                """, [session_id] + excluded_users)
                top_day_record = c.fetchone()
                top_day_count, top_day_date = top_day_record if top_day_record else (0, "无日期")

 
            # 获取今日活跃用户信息
            user_message_count = Counter(record[2] for record in today_records)
            sorted_users = user_message_count.most_common(6)

            # 提取今日最活跃用户的聊天内容
            top_user_today = sorted_users[0][0] if sorted_users else None
            top_user_today_messages = [record[3] for record in today_records if record[2] == top_user_today]
            #打印获取到的top_user_today_messages的数量
            logger.debug(f"今日top_user共发送了{len(top_user_today_messages)}条消息")
            model_analysis = ""
            if top_user_today_messages:
                # 构建消息格式
                formatted_top_user_messages = f"以下是 {top_user_today} 今天的聊天内容，请点评：\n" + "\n".join(top_user_today_messages[:5])

                prompt = f"你是一个群聊小助手，对获取到的群内最活跃的群员 {top_user_today} 的聊天记录进行适当的总结，并进行精华点评（搭配emoji)。可以点评和适当总结他/她主要的聊天话题、核心话题分析、和谁互动最多等等方面，点评要尽量生动，语言表达精炼，如果可以，可以在最后用一两句诗来总结，总字数60字以内"
                messages_to_model = formatted_top_user_messages
                # 调用 Model 进行分析
                model_analysis = self.c_model._generate_model_analysis(prompt, messages_to_model)
                logger.debug(f"Model analysis for {top_user_today}: {json.dumps(model_analysis, ensure_ascii=False)}")

            # 组装最终的结果
            result_lines = [
                today_info,
                yesterday_info,
                "---------------------"
            ]
            for idx, (user, count) in enumerate(sorted_users, start=1):
                emoji_number = self.get_fancy_emoji_for_number(idx)
                special_emoji = self.get_special_emoji_for_top_three(idx)
                result_lines.append(f"{emoji_number} {user}: {count}条 {special_emoji}")
            # 添加点评时刻部分
            if model_analysis:
                result_lines.append("\n🔍点评时刻:\n" + model_analysis)
                
            # 添加历史数据部分
            # result_lines.append("---------------------")
            result_lines.append(f"\n🔖 最高历史记录: {top_day_count} 条")
            # result_lines.append(f"🏆 眠眠羊₊⁺: {top_user_count} 条 ({top_date})")
            # result_lines.append(f"🌟 群聊: {top_day_count} 条 ({top_day_date})")
                    
            return "\n".join(result_lines) 
        except Exception as e:
            logger.error(f"Error getting chat activity ranking: {e}")
            return "Unable to retrieve chat activity ranking."

    def get_fancy_emoji_for_number(self, number):
        """为排名序号提供更漂亮的emoji"""
        fancy_emojis = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣"]
        return fancy_emojis[number - 1] if number <= len(fancy_emojis) else "🔹"

    def get_special_emoji_for_top_three(self, rank):
        """为前三名提供特别的emoji"""
        special_emojis = ["✨", "🌟", "💫", "", "", ""]
        return special_emojis[rank - 1] if rank <= len(special_emojis) else ""

    # def analyze_keyword_usage(self, keyword):
    #     # 调用 wxmsg 模块中的函数
    #     keyword_analysis = wx.analyze_keyword_in_messages(keyword)
    #     logger.debug(f"分析关键词 {keyword} 的使用情况成功: {keyword_analysis}")
    #     # 判断是否有有效的分析结果
    #     if keyword_analysis:
    #         # 准备 OpenAI 的输入
    #         messages_to_openai = [
    #             {"role": "system", "content": f"你是群里的聊天记录统计助手，你主要的功能是根据用户查询的关键词'{keyword}'，对和该关键词有关的聊天记录进行分析，形成一份简明、好看、完整的聊天记录报告，该报告要准确的结合聊天报告的文案风格，语言连贯，段落清晰，搭配数据加以展示。将获取到的聊天记录数据进行呈现，适当添加emoji，报告的角度包括但不限于该关键词讨论的热度、总提及次数、讨论最多的日期（频率、时间段）和该日提及次数、最多聊到该关键词的人是谁、聊了多少次....等等，以及根据提取出的特定聊天者针对该话题的聊天记录进行精彩点评。"},
    #             {"role": "user", "content": json.dumps(keyword_analysis, ensure_ascii=False)}
    #         ]
    #         # 调用 OpenAI 生成总结
    #         openai_analysis = self.c_model._generate_summary_with_openai(messages_to_openai)
    #         return openai_analysis
    #     else:
    #         return "没有找到关于此关键词的信息。"
    
    # def analyze_specific_user_usage(self, nickname):
    #     # 调用 analyze_user_messages 函数进行分析
    #     user_analysis = wx.analyze_user_messages(nickname)
    #     logger.debug(f"分析用户{nickname}的使用情况: {user_analysis}")
    #     if user_analysis:
    #         # 准备 OpenAI 的输入
    #         messages_to_openai = [
    #             {"role": "system", "content": f"你是群里的聊天记录统计助手，主要的功能是分析群聊昵称名为【{nickname}】的聊天记录,精确整理出【{nickname}】的重要聊天信息。根据【{nickname}】的聊天记录各项数据生成一份专属于【{nickname}】的聊天记录报告，要求内容连贯、客观并体现数据，适当添加emoji使报告更美观，包括但不限于：各种类型的消息的发送数量、用户的消息最爱说哪些词汇、哪个时间段最爱聊天、该统计周期内总的聊天次数、聊天字数、话最多的一天是哪天（当天的发言条数和聊天字数）、用户的消息发送内容的情感倾向等等。报告要生动，对【{nickname}】和群员的互动进行精彩点评。"},
    #             {"role": "user", "content": user_analysis}
    #         ]

    #         # 调用 OpenAI 生成总结
    #         openai_analysis = self.c_model._generate_summary_with_openai(messages_to_openai)
    #         return openai_analysis
    #     else:
    #         return "没有找到关于此用户的信息。"


    def get_help_text(self, verbose=False, **kwargs):
        help_text = "一个清新易用的聊天记录统计插件。\n"
        if verbose:
            help_text += "使用方法: 总结群聊、聊天统计、聊天关键词等"
        return help_text
    

def _set_reply_text(content: str, e_context: EventContext, level: ReplyType = ReplyType.ERROR):
    reply = Reply(level, content)
    e_context["reply"] = reply
    e_context.action = EventAction.BREAK_PASS
# 其他必要的插件逻辑

def remove_markdown(text):
    # 替换Markdown的粗体标记
    text = text.replace("**", "")
    # 替换Markdown的标题标记
    text = text.replace("### ", "").replace("## ", "").replace("# ", "")
    return text