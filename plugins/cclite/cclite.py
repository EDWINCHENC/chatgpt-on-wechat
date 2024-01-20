import plugins
import requests
import json
import re
from bridge.context import ContextType
from bridge.reply import Reply, ReplyType
from channel.chat_message import ChatMessage
from plugins import *
from common.log import logger
import os
from datetime import datetime
from .lib.model_factory import ModelGenerator
from .lib.unifiedmodel import UnifiedChatbot
from .lib import fetch_affdz as affdz, horoscope as horo


@plugins.register(
    name="cclite",
    desc="A plugin that supports multi-function_call",
    version="0.1.0",
    author="cc",
    desire_priority=66
)
class CCLite(Plugin):
    def __init__(self):
        super().__init__()
        self.handlers[Event.ON_HANDLE_CONTEXT] = self.on_handle_context
        try:
                self.c_model = ModelGenerator()
                # 创建 UnifiedChatbot 实例
                self.c_modelpro = UnifiedChatbot()
                self.session_data = {}  # user_id -> (state, data)
                logger.info("[cclite] inited")
        except Exception as e:
            logger.error(f"[cclite] init error: {e}")

    
    def on_handle_context(self, e_context: EventContext):
        context = e_context['context']
        msg: ChatMessage = context['msg']
        isgroup = e_context["context"].get("isgroup")
        user_id = msg.actual_user_id if isgroup else msg.from_user_id
        # nickname = msg.actual_user_nickname  # 获取nickname

        # 过滤不需要处理的内容类型
        if context.type not in [ContextType.TEXT, ContextType.IMAGE, ContextType.IMAGE_CREATE, ContextType.FILE, ContextType.SHARING]:
            return
        if context.type == ContextType.TEXT:
            session_state, session_data = self.get_session_state(user_id)

            if session_state == "NORMAL":
                self.handle_normal_context(e_context)
            elif session_state == "ANSWER_BOOK":
                self.handle_answer_book(e_context, session_data)
            elif session_state == "ZHOU_GONG_DREAM":
                self.handle_zhou_gong_dream(e_context, session_data)
            # 未来可以添加更多elif来处理其他状态

    def handle_normal_context(self, e_context: EventContext):
        context = e_context['context']
        msg: ChatMessage = context['msg']
        isgroup = e_context["context"].get("isgroup")
        user_id = msg.actual_user_id if isgroup else msg.from_user_id
        # nickname = msg.actual_user_nickname  # 获取nickname
        
        # 模型切换
        content_lower = context.content.lower()
        if "cc openai" in content_lower:
            self.c_model.set_ai_model("OpenAI")
            self.c_modelpro.set_ai_model("OpenAI")
            _set_reply_text("已切换到OpenAI模型。", e_context, level=ReplyType.TEXT)
            return
        elif "cc gemini" in content_lower:
            self.c_model.set_ai_model("Gemini")
            self.c_modelpro.set_ai_model("Gemini")
            _set_reply_text("已切换到Gemini模型。", e_context, level=ReplyType.TEXT)
            return
        elif "cc qwen" in content_lower:
            self.c_model.set_ai_model("Qwen")
            self.c_modelpro.set_ai_model("Qwen")
            _set_reply_text("已切换到Qwen模型。", e_context, level=ReplyType.TEXT)
            return
        elif "cc zhipuai" in content_lower:
            # self.c_model.set_ai_model("Zhipuai")
            self.c_modelpro.set_ai_model("Zhipuai")
            _set_reply_text("已切换到Zhipuai模型。", e_context, level=ReplyType.TEXT)
            return
        elif "cmodel" in content_lower:
            response = self.c_model.get_current_model()
            _set_reply_text(response, e_context, level=ReplyType.TEXT)
            return
        elif "重置会话" in context.content:
            self.c_modelpro.clear_all_histories()
            _set_reply_text("记录清除，会话已重置。", e_context, level=ReplyType.TEXT)
            return
        elif "清除我的会话" in context.content:
            # 调用 clear_user_history 方法并检查操作是否成功
            if self.c_modelpro.clear_user_history(user_id):
                _set_reply_text("您的会话历史已被清除。", e_context, level=ReplyType.TEXT)
            return

        elif "找" in context.content:
            # 通过正则表达式匹配 "找电影名" 的模式
            match = re.search(r"找(.+)", context.content)
            if match:
                movie_name = match.group(1).strip()  # 获取电影名
                logger.debug(f"正在为 {nickname} 查找电影: {movie_name}")
                try:
                    # 调用fetch_movie_info函数获取电影信息
                    movie_info = affdz.fetch_movie_info(movie_name)
                    if movie_info is None:
                        # 如果movie_info为None，则返回一个错误消息
                        logger.error(f"未找到电影: {movie_info}")
                        _set_reply_text("未找到电影信息，请检查电影名称是否正确。", e_context, level=ReplyType.TEXT)
                    else:
                        logger.debug(f"获取电影信息响应：{movie_info}")
                        _set_reply_text(movie_info, e_context, level=ReplyType.TEXT)
                    return
                except Exception as e:
                    logger.error(f"查找电影信息失败: {e}")
                    _set_reply_text("查找电影信息失败，请稍后再试。", e_context, level=ReplyType.TEXT)
                    return

        # 使用正则表达式来匹配星座运势的请求
        elif "运势" in context.content:
            match = re.search(r"(今日)?\s*(白羊座|金牛座|双子座|巨蟹座|狮子座|处女座|天秤座|天蝎座|射手座|摩羯座|水瓶座|双鱼座)\s*(运势|今日运势)?", context.content)
            if match:
                sign = match.group(2)  # 获取匹配到的星座名称
                logger.debug(f"正在获取 {sign} 星座运势数据")
                _send_info(e_context, f"💰🧧 {sign}今日运势即将来临...")
                try:
                    horoscope_data = horo.fetch_horoscope(sign)
                    logger.debug(f"星座运势响应：{horoscope_data}")
                    final_response = f"{horoscope_data}\n🔮 发送‘求签’, 让诸葛神数签诗为你今日算上一卦。"
                    _set_reply_text(final_response, e_context, level=ReplyType.TEXT)
                    return
                except Exception as e:
                    logger.error(f"获取星座运势失败: {e}")
                    _set_reply_text(f"获取星座运势失败，请稍后再试", e_context, level=ReplyType.TEXT)
                    return

        # 以下为求签、解签功能
        elif "求签" in context.content:
            logger.debug("开始求签")
            # 检查用户是否已在当天抽过签
            if self.has_user_drawn_today(user_id):
                response = "--今日已得签，请明日再来。--\n"
                # 如果今日已求过签，显示今日的签文
                if 'divination' in self.user_divinations[user_id]:
                    divination = self.user_divinations[user_id]['divination']
                    response += f"📜 今日{divination['qian']}"
                _set_reply_text(response, e_context, level=ReplyType.TEXT)
                return

            divination = horo.fetch_divination()
            if divination and divination['code'] == 200:
                # 存储用户的抽签结果及日期
                self.user_divinations[user_id] = {
                    'date': datetime.now().date().isoformat(),
                    'divination': divination,
                    'already_interpreted': False  # 初始化解签标记
                }
                logger.debug(f"当前抽签结果字典：{self.user_divinations}")
                response = f"📜 你抽到了{divination['title']}\n⏰ {divination['time']}\n💬 {divination['qian']}\n🔮 发送‘解签’, 让诸葛神数为你解卦。"
                _set_reply_text(response, e_context, level=ReplyType.TEXT)
                return
            else:
                _set_reply_text("获取签文失败，请稍后再试。", e_context, level=ReplyType.TEXT)
                return

        elif "解签" in context.content:
            logger.debug("开始解签")
            # 检查用户是否已经抽过签
            if user_id in self.user_divinations and 'divination' in self.user_divinations[user_id]:
                user_divination_data = self.user_divinations[user_id]
                logger.debug(f"用户{user_id}的解签数据：{user_divination_data}")
                # 检查是否已经解过签
                if user_divination_data.get('already_interpreted', False):
                    _set_reply_text("今日已解签，请明日再来。", e_context, level=ReplyType.TEXT)
                    return
                divination = user_divination_data['divination']
                response = f"📖 {divination['jie']}"
                _set_reply_text(response, e_context, level=ReplyType.TEXT)
                # 标记为已解签
                user_divination_data['already_interpreted'] = True
                logger.debug(f"用户{user_id}已完成解签")
                return
            else:
                _set_reply_text("请先求签后再请求解签。", e_context, level=ReplyType.TEXT)
                return

        elif "答案之书" in context.content:
            logger.debug("激活答案之书会话")
            self.start_session(user_id, "ANSWER_BOOK")
            _set_reply_text(
                "🔮 当你遇事不决时......\n\n"
                "🤔 请用 5 至 10 秒的时间，集中思考你的问题。\n"
                "🌟 每次只能有一个问题。\n\n"
                "💭 在确定你的问题后，可以告诉我，例如：\n"
                "“TA喜欢我吗？” 或 “我需要换个工作吗？”\n\n"
                "✨ 或者，如果你愿意，不必告诉我你的问题，只需心中虔诚地默念。\n"
                "然后发送“答案”，你要寻找的答案就在那里等着你。\n",
                e_context,
                level=ReplyType.TEXT
            )
            return

        elif re.search("吃什么|中午吃什么|晚饭吃什么|吃啥", context.content):
            logger.debug("正替你考虑今天吃什么")
            msg = context.kwargs.get('msg')  # 这是WechatMessage实例
            nickname = msg.actual_user_nickname  # 获取nickname
            url = "https://zj.v.api.aa1.cn/api/eats/"
            try:
                response = requests.get(url)
                logger.debug(f"response响应：{response}")
                if response.status_code == 200:
                    data = response.json()
                    logger.debug(f"data数据：{data}")
                    if data['code'] == 200:
                        # 构建消息
                        prompt = "你是中国著名的美食专家，走遍全国各大城市品尝过各种当地代表性的、小众的美食，对美食有深刻且独到的见解。你会基于背景信息，给用户随机推荐2道国内地域美食，会根据用户的烦恼给出合理的饮食建议和推荐的美食点评或推荐理由。"
                        user_input = f"对于今天该吃些什么好呢？你推荐了{data.get('meal1', '')}，和{data.get('meal2', '')}。现在需要你用两段文字（每段35字以内），适当结合{context.content}中用户的实际情况（例如来自什么地方、口味等）来简要点评推荐的菜、分享一下菜谱、营养搭配建议等，搭配适当的emoji来回复。总字数不超70字。"
                        # 调用OpenAI处理函数
                        model_response = self.c_model._generate_model_analysis(prompt, user_input)
                        # 构建最终的回复消息
                        final_response = (
                            f"🌟 你好呀！{nickname}，\n"
                            f"🍽️ 今天推荐给你的美食有：\n\n"
                            f"🍴 {data.get('meal1', '精选美食')} 或者 🍴 {data.get('meal2', '精选美食')}\n\n"
                            f"😊 奉上我的推荐理由：\n"
                            f"{model_response}"
                        )
                        logger.debug(f"_最终回复：{final_response}")
                        _set_reply_text(final_response, e_context, level=ReplyType.TEXT)
                        return
            except requests.RequestException as e:
                return f"请求异常：{e}"

        # 添加对图像生成请求的检测
        elif context.content.startswith("画"):
            prompt = context.content[1:].strip()  # 从"画："后的文本开始提取
            logger.debug(f"检测到图像生成请求，提示词: {prompt}")
            image_url = self.c_modelpro._generate_image_zhipuai(prompt)
            logger.debug(f"生成的图像URL: {image_url}")
            _set_reply_text(image_url, e_context, level=ReplyType.IMAGE_URL)
            return

        # 调用模型库的模型进行处理
        else:
            user_input = context.content
            response = self.c_modelpro.get_model_reply(user_input, user_id)
            _set_reply_text(response, e_context, level=ReplyType.TEXT)     
            return

    # 以下为进入特殊会话的处理函数
    def handle_answer_book(self, e_context: EventContext, session_data):
        logger.debug("进入答案之书会话")     
        context = e_context['context']
        msg: ChatMessage = context['msg']
        # user_id = msg.from_user_id
        isgroup = e_context["context"].get("isgroup")
        user_id = msg.actual_user_id if isgroup else msg.from_user_id
        nickname = msg.actual_user_nickname  # 获取nickname              
    
        # 处理用户的问题，生成答案
        # 构建提示词
        prompt = "你是一本《答案之书》，人生的每个问题，都能从你这找到答案，你拥有丰富的生活经验和深邃的洞察力。10秒沉思，你会从你的答案之书中寻找答案，帮助他人找到人生方向，解决疑惑，找到任何问题的答案，有时候，我不会告诉你我的问题，只是想要一个答案，我会在心中虔诚地默念，无论如何，你每次都要直接从答案之书中给出1个富有启发性的、简洁的(20字以内的)、尽量确切的、具有方向性、指导性的答案，为任何问题，或不存在的问题，解惑。记住，只需要给出问题答案，不需要解释，不需要任何其他内容。"
        # 接收用户的问题
        # 根据context.content调整user_input
        if context.content == "答案":
            user_input = "刚才，我在心中虔诚地默念了我的困惑，现在，请你直接从答案之书随机开启一个答案给我吧。"
        else:
            user_input = f"现在，我的问题是 {context.content} ，请你直接从答案之书随机开启一个答案给我吧。"
        # 调用OpenAI处理函数
        model_response = self.c_model._generate_model_analysis(prompt, user_input)
        # 构建最终的回复消息
        final_response = f"🔮 你的答案：\n{model_response}"
        logger.debug(f"已获取答案: {final_response}")
        # 使用_set_reply_text发送回复
        _set_reply_text(final_response, e_context, level=ReplyType.TEXT)
        # 结束当前会话
        logger.debug(f"结束答案之书会话前，用户 {user_id} 的会话状态: {self.session_data.get(user_id)}")
        self.end_session(user_id)
        logger.debug(f"结束答案之书会话后，用户 {user_id} 的会话状态: {self.session_data.get(user_id)}")
        return

    # 以下为插件的一些辅助函数

    def has_user_drawn_today(self, user_id):
        """检查用户是否在当天已求过签"""
        if user_id in self.user_divinations:
            last_divination_date = self.user_divinations[user_id].get('date')
            return last_divination_date == datetime.now().date().isoformat()
        return False

    def start_session(self, user_id, state, data=None):
        self.session_data[user_id] = (state, data)
        logger.debug(f"用户{user_id}开始会话，状态: {state}, 数据: {data}")

    def end_session(self, user_id):
        self.session_data.pop(user_id, None)
        logger.debug(f"用户{user_id}结束会话")

    def get_session_state(self, user_id):
        logger.debug(f"获取用户{user_id}的会话状态")
        return self.session_data.get(user_id, ("NORMAL", None))

    def get_help_text(self, verbose=False, **kwargs):
        # 初始化帮助文本，插件的基础描述
        help_text = "\n🤖 基于微信的多功能聊天机器人，提供新闻、天气、火车票信息、娱乐内容等实用服务。\n"
        
        # 如果不需要详细说明，则直接返回帮助文本
        if not verbose:
            return help_text
        
        # 添加详细的使用方法到帮助文本中
        help_text += """
            国产大模型
        """    
        # 返回帮助文本
        return help_text

def _send_info(e_context: EventContext, content: str):
    reply = Reply(ReplyType.TEXT, content)
    channel = e_context["channel"]
    channel.send(reply, e_context["context"])

def _set_reply_text(content: str, e_context: EventContext, level: ReplyType = ReplyType.ERROR):
    reply = Reply(level, content)
    e_context["reply"] = reply
    e_context.action = EventAction.BREAK_PASS

def remove_markdown(text):
    # 替换Markdown的粗体标记
    text = text.replace("**", "")
    # 替换Markdown的标题标记
    text = text.replace("### ", "").replace("## ", "").replace("# ", "")
    return text




