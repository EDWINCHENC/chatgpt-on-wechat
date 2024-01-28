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
import time
from datetime import datetime
from .lib.model_factory import ModelGenerator
from .lib.unifiedmodel import UnifiedChatbot
from .lib import fetch_affdz as affdz, horoscope as horo, function as fun, fetch_tv_show_id as fetch_tv_show_id, tvshowinfo as tvinfo


@plugins.register(
    name="cclite",
    desc="A plugin that supports multi-function_call",
    version="3.0",
    author="cc",
    desire_priority=66
)
class CCLite(Plugin):
    def __init__(self):
        super().__init__()
        self.handlers[Event.ON_HANDLE_CONTEXT] = self.on_handle_context
        curdir = os.path.dirname(__file__)
        config_path = os.path.join(curdir, "config.json")
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
                logger.info(f"[cclite] 加载配置文件成功: {config}")
                # 创建 UnifiedChatbot 实例
                self.c_model = ModelGenerator()
                self.c_modelpro = UnifiedChatbot()
                self.session_data = {}  # user_id -> (state, data)
                self.user_divinations = {}
                self.alapi_key = config["alapi_key"]   
                self.getwt_key = config["getwt_key"]
                self.cc_api_base = config.get("cc_api_base", "https://api.lfei.cc")
                logger.info("[cclite] inited")
        except Exception as e:
            logger.error(f"[cclite] init error: {e}")

    
    def on_handle_context(self, e_context: EventContext):
        context, _, user_id, session_id, _ = self.extract_e_context_info(e_context)
        logger.debug(f"CCLite获取到用户输入：{context.content}")
        # 过滤不需要处理的内容类型
        if context.type not in [ContextType.TEXT, ContextType.IMAGE, ContextType.IMAGE_CREATE, ContextType.FILE, ContextType.SHARING]:
            return
        if context.type == ContextType.TEXT:
            session_state, session_data = self.get_session_state(user_id, session_id)

            if context.content == "退出":
                self.c_modelpro.clear_user_history(user_id)
                self.c_modelpro.clear_user_history(session_id)
                self.end_session(user_id, session_id)
                _set_reply_text("已退出特殊会话模式，进入正常聊天。", e_context, level=ReplyType.TEXT)
                return
            elif session_state == "NORMAL":
                self.handle_normal_context(e_context)            
            elif session_state == "ANSWER_BOOK":
                self.handle_answer_book(e_context, session_data)
            elif session_state == "ZHOU_GONG_DREAM":
                self.handle_zhou_gong_dream(e_context, session_data)
            elif session_state == "KITCHEN_ASSISTANT":
                self.handle_recipe_request(e_context, session_data)
            elif session_state == "QUIZ_MODE":
                self.handle_quiz_mode(e_context, session_data)
            elif session_state == "COMFORT_MODE":
                self.handle_comfort_mode(e_context, session_data)
            # 未来可以添加更多elif来处理其他状态

    def handle_normal_context(self, e_context: EventContext):
        context, _, user_id, session_id, nickname = self.extract_e_context_info(e_context)
        start_time = time.time()  # 开始计时
        
        # 模型切换
        content_lower = context.content.lower()
        if "cc openai" in content_lower:
            self.c_modelpro.set_ai_model("OpenAI")
            _set_reply_text("已切换到OpenAI模型。", e_context, level=ReplyType.TEXT)
            return
        elif "cc gemini" in content_lower:
            self.c_modelpro.set_ai_model("Gemini")
            _set_reply_text("已切换到Gemini模型。", e_context, level=ReplyType.TEXT)
            return
        elif "cc qwen" in content_lower:
            self.c_modelpro.set_ai_model("Qwen")
            _set_reply_text("已切换到Qwen模型。", e_context, level=ReplyType.TEXT)
            return
        elif "cc zhipuai" in content_lower:
            self.c_modelpro.set_ai_model("Zhipuai")
            _set_reply_text("已切换到Zhipuai模型。", e_context, level=ReplyType.TEXT)
            return
        elif "重置所有会话" in context.content:
            self.c_modelpro.clear_all_histories()
            _set_reply_text("记录清除，会话已重置。", e_context, level=ReplyType.TEXT)
            return
        elif "清除我的会话" in context.content:
            # 调用 clear_user_history 方法并检查操作是否成功
            self.c_modelpro.clear_user_history(user_id)
            _set_reply_text("您的会话历史已被清除。", e_context, level=ReplyType.TEXT)
            return

        elif context.content.startswith("找"):
            # 通过正则表达式匹配 "找电影名" 的模式
            match = re.search(r"找(.+)", context.content)
            if match:
                movie_name = match.group(1).strip()  # 获取电影名
                logger.debug(f"正在查找影视资源: {movie_name}")
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
            self.c_modelpro.clear_user_history(user_id)  # 先清除用户历史记录
            _set_reply_text(
                "🔮 你已进入答案之书......\n"
                "💭 告诉我你的不解，你要寻找的答案就在那里等着你。",
                e_context,
                level=ReplyType.TEXT
            )
            return
        
        elif "周公解梦" in context.content:
            logger.debug("激活周公解梦会话")
            self.start_session(user_id, "ZHOU_GONG_DREAM")
            self.c_modelpro.clear_user_history(user_id)  # 先清除用户历史记录
            _set_reply_text("你已进入周公解梦模式，请描述你的梦境。", e_context, level=ReplyType.TEXT)
            return

        elif "厨房助手" in context.content:
            logger.debug("激活厨房助手会话")
            self.start_session(user_id, "KITCHEN_ASSISTANT")
            self.c_modelpro.clear_user_history(user_id)  # 先清除用户历史记录
            _set_reply_text("你已进入厨房助手模式，你可以告诉我你手上拥有的食材(例如里脊肉、青椒)，和你喜欢的口味。", e_context, level=ReplyType.TEXT)
            return

        elif "答题模式" in context.content:
            logger.debug("激活答题模式会话")
            logger.debug(f"使用session_id: {session_id} 作为会话ID")
            self.start_session(session_id, "QUIZ_MODE")
            self.c_modelpro.clear_user_history(session_id)  # 先清除用户历史记录
            _set_reply_text("你已进入答题模式，来挑战自己吧！\n您想选择什么类型的题目呢？例如，您可以选择天文、地理、生活常识、历史、法律等。", e_context, level=ReplyType.TEXT)
            return

        elif "哄哄模式" in context.content:
            logger.debug("激活哄哄模式会话")
            self.start_session(user_id, "COMFORT_MODE","1")
            self.c_modelpro.clear_user_history(user_id)  # 先清除用户历史记录
            _send_info(e_context, "💖 你已进入哄哄模式，你需要使用语言技巧和沟通能力，让对方原谅你。")
            # 等待3秒
            time.sleep(3)
            _set_reply_text("哼!!", e_context, level=ReplyType.TEXT)
            return

        elif re.search("吃什么|中午吃什么|晚饭吃什么|吃啥", context.content):
            logger.debug("激活今天吃什么会话")
            self.c_modelpro.clear_user_history(user_id)  # 先清除用户历史记录
            system_prompt = """
            你是中国著名的美食专家，走遍全国各大城市品尝过各种当地代表性的、小众的美食，对美食有深刻且独到的见解。你会基于背景信息，给用户随机推荐2道国内地域美食，会根据用户的烦恼给出合理的饮食建议和推荐的美食点评或推荐理由。现在需要你用两段文字（每段35字以内），适当结合用户的实际情况（例如来自什么地方、口味等）来简要点评推荐的菜、分享一下菜谱、营养搭配建议等，搭配适当的emoji来回复。总字数不超70字。推荐美食严格遵循以下格式（仅作为参考）：
            🍽️ 今天推荐给你的美食有：

            🍴 串串香 或者 🍴 香菇鸡肉粥

            😊 奉上我的推荐理由：
            串串香：麻辣鲜香，四川特色小吃。选材丰富，汤底醇厚。配冰粉解辣，口感层次更丰富。营养均衡，适合重口味爱好者。
            香菇鸡肉粥：清香鲜美，健康养生。鸡肉富含蛋白质，香菇提鲜。搭配青菜，营养全面。清淡口味，适合各年龄段。
            """
            self.c_modelpro.set_system_prompt(system_prompt, user_id)
            # 调用OpenAI处理函数
            model_response = self.c_modelpro.get_model_reply(context.content, user_id)
            logger.debug(f"_最终回复：{model_response}")
            self.c_modelpro.clear_user_history(user_id)  # 清除用户历史记录
            _set_reply_text(model_response, e_context, level=ReplyType.TEXT)
            return
            
            # 以下为获取实时要闻的处理函数  
        elif "实时要闻" in context.content:
            api_url = f"{self.base_url()}/latest_news/"
            try:
                # 发送GET请求到你的FastAPI服务
                response = requests.get(api_url)
                response.raise_for_status()  # 如果响应状态码不是200，将抛出异常
                function_response = response.json()  # 解析JSON响应体为字典
                logger.debug(f"Function response: {function_response}")  # 打印函数响应
                function_response = function_response["results"]  # 返回结果字段中的数据
                elapsed_time = time.time() - start_time  # 计算耗时
                # 仅在成功获取数据后发送信息
                if context.kwargs.get('isgroup'):
                    msg = context.kwargs.get('msg')  # 这是WechatMessage实例
                    nickname = msg.actual_user_nickname  # 获取nickname
                    _send_info(e_context, f"@{nickname}\n✅获取实时要闻成功,正在整理。🕒耗时{elapsed_time:.2f}秒")
                else:
                    _send_info(e_context, f"✅获取实时要闻成功,正在整理。🕒耗时{elapsed_time:.2f}秒")
                system_prompt = (
                    "你是一个高级智能助手，专门用于整理和概括实时要闻。"
                    "你的任务是将获取到的最新新闻资讯进行精确的整理和提炼。"
                    "运用适当的emoji和精炼的语言，将复杂的信息以简洁、清晰且吸引人的方式呈现给用户。"
                    "确保内容准确、排版优美、包含所有关键信息，又能激发用户的兴趣和好奇心。"
                )
                self.c_modelpro.set_system_prompt(system_prompt)
                function_response = self.c_modelpro.get_model_reply(function_response)
                logger.debug(f"实时要闻整理完成: {function_response}")
                self.clear_user_history()  # 清除用户历史记录
                _set_reply_text(function_response, e_context, level=ReplyType.TEXT)
                return
            except requests.RequestException as e:
                logger.error(f"Request to API failed: {e}")
                _set_reply_text("获取最新新闻失败，请稍后再试。", e_context, level=ReplyType.TEXT)
                return
                            
        elif "财经资讯" in context.content:  # 2.获取财经新闻
            api_url = f"{self.base_url()}/financial_news/"            
            try:
                # 发送GET请求到你的FastAPI服务
                response = requests.get(api_url)
                response.raise_for_status()  # 如果响应状态码不是200，将抛出异常
                function_response = response.json()  # 解析JSON响应体为字典
                logger.debug(f"Function response: {function_response}")  # 打印函数响应
                function_response = function_response["results"]  # 返回结果字段中的数据
                elapsed_time = time.time() - start_time  # 计算耗时
                # 仅在成功获取数据后发送信息
                if context.kwargs.get('isgroup'):
                    msg = context.kwargs.get('msg')  # 这是WechatMessage实例
                    nickname = msg.actual_user_nickname  # 获取nickname
                    _send_info(e_context, f"@{nickname}\n✅获取实时财经资讯成功, 正在整理。🕒耗时{elapsed_time:.2f}秒")
                else:
                    _send_info(e_context, f"✅获取实时财经资讯成功，正在整理。🕒耗时{elapsed_time:.2f}秒")
                system_prompt = (
                    "你是一个高级智能助手，专门用于整理和概括财经资讯。"
                    "你的任务是将获取到的财经新闻资讯进行精确的整理和提炼，"
                    "运用适当的emoji和精炼的语言，将经济数据和市场分析以简洁、清晰且专业的方式呈现给用户。"
                    "确保内容既准确且专业，又不失趣味性、实时性、可读性。"
                )
                self.c_modelpro.set_system_prompt(system_prompt)
                function_response = self.c_modelpro.get_model_reply(function_response)
                logger.debug(f"财经资讯整理完成: {function_response}")
                self.c_modelpro.clear_user_history()  # 清除用户历史记录
                _set_reply_text(function_response, e_context, level=ReplyType.TEXT)
                return
            except requests.RequestException as e:
                logger.error(f"Request to API failed: {e}")
                _set_reply_text("获取财经新闻失败，请稍后再试。", e_context, level=ReplyType.TEXT)
                return
            
        elif "天气" in context.content:
            # 使用正则表达式匹配城市名称
            match = re.search(r"(.+?)(的)?天气", context.content)
            city_name = match.group(1) if match else "北京"  # 如果没有匹配到，则默认为北京
            adm = None 
            user_key = self.getwt_key

            if context.kwargs.get('isgroup'):
                msg = context.kwargs.get('msg')  # 这是WechatMessage实例
                nickname = msg.actual_user_nickname  # 获取nickname
                _send_info(e_context, "@{name}\n🔜正在获取{city}的天气情况🐳🐳🐳".format(name=nickname, city=city_name))
            else:
                _send_info(e_context, "🔜正在获取{city}的天气情况🐳🐳🐳".format(city=city_name))

            # 向API端点发送GET请求，获取指定城市的天气情况
            logger.debug(f"向API端点发送GET请求，获取{city_name}的天气情况")
            try:
                response = requests.get(
                    self.base_url() + "/weather/",
                    params={
                        "city_name": city_name,
                        "user_key": user_key,
                        "adm": adm
                    }
                )
                response.raise_for_status()  # 如果请求返回了失败的状态码，将抛出异常
                function_response = response.json()
                function_response = function_response.get("results", "未知错误")
                _set_reply_text(function_response, e_context, level=ReplyType.TEXT)
                return
            except Exception as e:
                logger.error(f"Error fetching weather info: {e}")
                _set_reply_text("获取天气信息失败，请稍后再试。", e_context, level=ReplyType.TEXT)
                return
            
        elif "影院热映" in context.content: 
            if e_context['context'].kwargs.get('isgroup'):
                msg = e_context['context'].kwargs.get('msg')  # 这是WechatMessage实例
                nickname = msg.actual_user_nickname  # 获取nickname
                _send_info(e_context, f"@{nickname}\n🔜正在获取最新影讯🐳🐳🐳")
            else:
                _send_info(e_context, "🔜正在获取最新影讯🐳🐳🐳")

            # 构建API请求的URL
            api_url = f"{self.base_url()}/now_playing_movies/"

            # 向FastAPI端点发送GET请求
            try:
                response = requests.get(api_url)
                response.raise_for_status()  # 检查请求是否成功

                # 解析响应数据
                data = response.json()
                function_response = data.get('results')
                status_msg = data.get('status')
                elapsed_time = data.get('elapsed_time')

                # 根据响应设置回复文本
                if status_msg == '失败':
                    _set_reply_text(f"\n❌获取失败: {status_msg}", e_context, level=ReplyType.TEXT)
                else:
                    _set_reply_text(f"\n✅获取成功，耗时: {elapsed_time:.2f}秒\n{function_response}", e_context, level=ReplyType.TEXT)
            except requests.HTTPError as http_err:
                # 如果请求出错，则设置失败消息
                _set_reply_text(f"\n❌HTTP请求错误: {http_err}", e_context, level=ReplyType.TEXT)
            return
                
        elif "热播电视剧" in context.content:  # 7.获取豆瓣最热电视剧榜单              
            # 从message里提取函数调用参数
            limit = 10
            type_ = 'tv'  # 默认为电视剧
            if context.kwargs.get('isgroup'):
                msg = context.kwargs.get('msg')  # 这是WechatMessage实例
                nickname = msg.actual_user_nickname  # 获取nickname
                _send_info(e_context,"@{name}\n☑️正在为您查询豆瓣的最热电视剧榜单🐳🐳🐳".format(name=nickname)) 
            else:
                _send_info(e_context, "☑️正在为您查询豆瓣的最热电视剧榜单，请稍后...") 
            # 调用函数，获取豆瓣最热电视剧榜单
            try:
                response = requests.get(
                    self.base_url() + "/top_tv_shows/",
                    params={
                        "limit": limit,
                        "type": type_,
                    }
                )
                response.raise_for_status()  # 如果请求返回了失败的状态码，将抛出异常
                function_response = response.json()
                function_response = function_response.get("results", "未知错误")
                _set_reply_text(function_response, e_context, level=ReplyType.TEXT)
                return
            except Exception as e:
                logger.error(f"Error fetching top TV shows info: {e}")
                _set_reply_text("获取最热影视剧榜单失败，请稍后再试。", e_context, level=ReplyType.TEXT)
                return  

        elif "AI资讯" in context.content:  # 7.获取AI资讯
            max_items = 6
            try:
                response = requests.get(
                    self.base_url() + "/ainews/",
                    params={"max_items": max_items}
                )
                response.raise_for_status()  # 如果请求返回了失败的状态码，将抛出异常
            except Exception as e:
                logger.error(f"Error fetching AI news: {e}")
                _set_reply_text(f"获取AI新闻失败，请稍后再试。错误信息: {e}", e_context, level=ReplyType.TEXT)
                return  # 终止后续代码执行
            try:
                function_response = response.json()
                function_response = function_response.get("results", "未知错误")
                logger.debug("AI资讯获取完成")  # 打印函数响应
                system_prompt = (
                    "你是一个高级智能助手，专门用于整理和概括AI相关的资讯。"
                    "你的任务是将获取到的AI新闻进行精确的整理和提炼，"
                    "运用适当的emoji和精炼的语言，将最新AI领域的资讯以简洁、清晰且专业的方式呈现给用户。"
                    "确保内容既准确且专业，又不失趣味性和可读性，排版优美，主题提炼得当，激发用户对AI领域的兴趣。"
                )
                self.c_modelpro.set_system_prompt(system_prompt)
                function_response = self.c_modelpro.get_model_reply(function_response)
                logger.debug("AI资讯整理完成")  # 打印整理后的响应
                self.c_modelpro.clear_user_history()  # 清除用户历史记录
                _set_reply_text(function_response, e_context, level=ReplyType.TEXT)
                return
            except ValueError as e:  # 捕获JSON解析错误
                logger.error(f"JSON parsing error: {e}")
                _set_reply_text(f"获取AI新闻失败，请稍后再试。错误信息: {e}", e_context, level=ReplyType.TEXT)
                return  # 终止后续代码执行

                
        elif "早报" in context.content:  # 11.获取每日早报
            logger.debug("获取每日早报")
            function_response = fun.get_morning_news(api_key=self.alapi_key)
            system_prompt = "你是每日新闻的早报助手，需要将获取到的新闻晨报资讯进行整理后，搭配适当emoji，返回给用户进行阅读。"
            self.c_modelpro.set_system_prompt(system_prompt, user_id)
            function_response = self.c_modelpro.get_model_reply(function_response, user_id)
            logger.debug(f"已获取，交由模型处理")
            self.c_modelpro.clear_user_history(user_id)  # 清除用户历史记录
            _set_reply_text(function_response, e_context, level=ReplyType.TEXT)
            return

                                       
        elif "英雄" in context.content and "的数据" in context.content:
            # 使用正则表达式匹配英雄名称
            match = re.search(r"英雄(.+?)的数据", context.content)
            hero_name = match.group(1).strip() if match else "未指定英雄"
            # 调用函数并获取返回值
            function_response = fun.get_hero_info(hero_name)
            _set_reply_text(function_response, e_context, level=ReplyType.TEXT)
            return

            
        elif "英雄梯度榜" in context.content:  # 9.获取英雄梯度榜
            # 构建 API 请求的 URL
            api_url = f"{self.base_url()}/hero_ranking/"
            # 向 FastAPI 端点发送 GET 请求
            try:
                response = requests.get(api_url)
                response.raise_for_status()  # 检查请求是否成功
                # 解析响应数据
                data = response.json()
                function_response = data.get('results')                    
                # 根据响应设置回复文本
                if function_response is None or "查询出错" in function_response:
                    _set_reply_text(f"❌获取失败: {function_response}", e_context, level=ReplyType.TEXT)
                else:
                    _set_reply_text(f"✅获取成功，数据如下：\n{function_response}", e_context, level=ReplyType.TEXT)
            except requests.HTTPError as http_err:
                # 如果请求出错，则设置失败消息
                _set_reply_text(f"❌HTTP请求错误: {http_err}", e_context, level=ReplyType.TEXT)
            except Exception as err:
                # 如果发生其他错误，则设置失败消息
                _set_reply_text(f"❌请求失败: {err}", e_context, level=ReplyType.TEXT)             
            # 记录响应
            return
                                        
        elif re.search(r"(电视剧|电影|动漫)(.+)", context.content):
            match = re.search(r"(电视剧|电影|动漫)(.+)", context.content)
            media_type_raw, tv_show_name = match.groups()
            tv_show_name = tv_show_name.strip()  # 去除可能的前后空格

            # 根据匹配到的媒体类型设置 media_type
            if media_type_raw == "电影":
                media_type = "movie"
            else:
                media_type = "tv"  # 默认为电视剧，包括动漫
            com_reply = Reply()
            com_reply.type = ReplyType.TEXT
            count = 8  # 默认10条评论
            order_by = "hot"  # 默认按照'hot'排序

            if context.kwargs.get('isgroup'):
                msg = context.kwargs.get('msg')  # 这是WechatMessage实例
                nickname = msg.actual_user_nickname  # 获取nickname
                _send_info(e_context,"@{name}\n☑️正在为您获取《{show}》的{media_type_text}信息和剧评，请稍后...".format(name=nickname, show=tv_show_name, media_type_text="电影" if media_type == "movie" else "电视剧")) 
            else:
                _send_info(e_context,"☑️正在为您获取《{show}》的{media_type_text}信息和剧评，请稍后...".format(show=tv_show_name, media_type_text="电影" if media_type == "movie" else "电视剧")) 
                
            # 使用 fetch_tv_show_id 获取电视剧 ID
            tv_show_id, status_msg, elapsed_time = fetch_tv_show_id.fetch_tv_show_id(tv_show_name)  # 假设函数返回 ID, 状态信息和耗时
            logger.debug(f"TV show ID: {tv_show_id}, status message: {status_msg}, elapsed time: {elapsed_time:.2f}秒")  # 打印获取的 ID 和状态信息                
            # 初始化回复内容
            com_reply.content = ""   # 假设 Reply 是一个您定义的类或数据结构
            
            # 根据获取的电视剧 ID 设置回复内容
            if tv_show_id is None:
                # 如果获取 ID 失败，设置失败消息
                com_reply.content += f"❌获取影视信息失败: {status_msg}"
            else:
                # 如果获取 ID 成功，设置成功消息和链接
                com_reply.content += f"✅获取影视信息成功，耗时: {elapsed_time:.2f}秒\n现可访问页面：https://m.douban.com/movie/subject/{tv_show_id}/\n以下为平台及播放跳转链接:"
                
                # 调用 fetch_media_details 函数获取影视详细信息
                media_details = tvinfo.fetch_media_details(tv_show_name, media_type)
                com_reply.content += f"\n{media_details}\n-----------------------------\n😈即将为你呈现精彩剧评🔜"  # 将详细信息添加到回复内容中
                
            # 发送回复
            _send_info(e_context, com_reply.content)
            # 调用函数
            function_response = tvinfo.get_tv_show_interests(tv_show_name, media_type=media_type, count=count, order_by=order_by)  # 注意这里我们直接调用函数，并没有使用shows_map   
            response_text = "\n".join(function_response)  # 将评论列表转换为单个字符串
            _set_reply_text(response_text, e_context, level=ReplyType.TEXT)  # 发送格式化后的评论字符串
            return          

        # elif context.content.startswith("搜索"):
        #     logger.debug("用户请求搜索")
        #     # 从用户输入中提取搜索内容，假设搜索关键字后面的内容是实际的查询内容
        #     search_query = context.content[2:].strip()  # 从第三个字符开始到字符串末尾

        #     # 设置Perplexity模型需要的系统提示信息
        #     system_prompt = (
        #         "你是一个高级智能搜索引擎，具备强大的联网搜索能力。"
        #         "你的任务是根据用户的查询请求，在网络上搜寻信息，并从中提取最相关、最权威的资料。"
        #         "在处理信息时，你能够理解复杂的概念，整理并归纳关键内容，并且能够理解和使用emoji来增强信息的表达效果。"
        #         "你会以清晰、有逻辑且易于理解的方式组织回复，确保信息准确、全面且格式一致，满足用户对信息的具体需求。"
        #         "在呈现结果时，你会考虑到用户的阅读体验，通过适当的排版和使用emoji，使得内容既信息丰富又视觉上吸引人。"
        #     )

        #     # 构建消息格式
        #     messages = self.c_model._build_perplexity_messages(system_prompt, search_query)

        #     # 调用ModelGenerator实例的方法请求Perplexity接口响应
        #     function_response = self.c_model._generate_summary_with_perplexity(messages)

        #     # 处理模型响应
        #     logger.debug(f"搜索结果：{function_response}")
        #     # 假设 _set_reply_text 是用来设置回复文本的方法
        #     _set_reply_text(function_response, e_context, level=ReplyType.TEXT)


        elif context.content == "帮助" or context.content == "功能":
            # 完整的功能指南
            features_guide = (
                "🌈 CCLite 插件功能指南 🌈\n\n"
                "🔄 '重置会话' - 清除当前会话历史\n"
                "🔍 '找+资源名称' - 查询指定电影电视剧网盘资源\n"
                "⭐ '白羊座运势' - 查看星座运势\n"
                "🔮 '求签''解签' - 抽取、解读今日签文\n"
                "📚 '答案之书' - 向智慧的答案之书提问\n"
                "🍲 '吃什么' - 获取美食推荐\n"
                "☀️ '城市+天气' - 查询指定城市的天气情况\n"
                "🎥 '影院热映' - 获取当前影院热映电影信息\n"
                "📺 '热播电视剧' - 获取当前热播的电视剧\n"
                "📰 '实时要闻、财经资讯、AI资讯' - 接收最新新闻\n"
                "📅 '早报' - 获取每日新闻早报\n"
                "🎮 '英雄+英雄名+的数据' - 查询指定英雄的游戏数据\n"
                "🏅 '英雄梯度榜' - 查看当前英雄游戏排行榜\n"
                "📖 '电视剧xxx' 或 '电影xxx' - 获取指定电视剧/电影的评论和详情\n"
                "🔮 '周公解梦' - 提供梦境解析服务\n"
                "👩‍🍳 '厨房助手' - 提供烹饪技巧和食谱建议\n"
                "🍲 '答题模式' - 进入答题模式\n"
                "🎨 '画+一只可爱的猫咪' - 根据描述生成图像\n"
                "💬 其他普通文本 - 聊天机器人智能回复\n"
                "\n🌟 有任何问题或建议，随时欢迎反馈！"
            )
            _set_reply_text(features_guide, e_context, level=ReplyType.TEXT)
            return

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
            logger.debug(f"进入通用会话处理模式")
            user_input = context.content
            response = self.c_modelpro.get_model_reply(user_input, user_id)
            _set_reply_text(response, e_context, level=ReplyType.TEXT)     
            return

    # 以下为进入特殊会话的处理函数
    # 以下为个性化会话处理模式
    def handle_answer_book(self, e_context: EventContext, session_data):
        context, _, user_id, _, _ = self.extract_e_context_info(e_context)
        logger.debug("进入答案之书会话")     
        # 构建提示词
        system_prompt = "你是一本《答案之书》，人生的每个问题，都能从你这找到答案，你拥有丰富的生活经验和深邃的洞察力。10秒沉思，你会从你的答案之书中寻找答案，帮助他人找到人生方向，解决疑惑，找到任何问题的答案，有时候，我不会告诉你我的问题，只是想要一个答案，我会在心中虔诚地默念，无论如何，你每次都要直接从答案之书中给出1个富有启发性的、简洁的(20字以内的)、尽量确切的、具有方向性、指导性的答案，为任何问题，或不存在的问题，解惑。记住，只需要给出问题答案，不需要解释，不需要任何其他内容。"
        self.c_modelpro.set_system_prompt(system_prompt,user_id)
        # 接收用户的问题
        if context.content == "答案":
            user_input = "刚才，我在心中虔诚地默念了我的困惑，现在，请你直接从答案之书随机开启一个答案给我吧。"
        else:
            user_input = f"现在，我的问题是 {context.content} ，请你直接从答案之书随机开启一个答案给我吧。"
        # 调用OpenAI处理函数
        model_response = self.c_modelpro.get_model_reply(user_input, user_id)
        # 构建最终的回复消息
        final_response = f"🔮 你的答案：\n{model_response}"
        logger.debug(f"已获取答案: {final_response}")
        # 使用_set_reply_text发送回复
        final_response = f"{final_response}\n\n🆗 完成解答，自动退出当前模式。"
        _set_reply_text(final_response, e_context, level=ReplyType.TEXT)
        # 结束当前会话
        self.c_modelpro.clear_user_history(user_id)
        self.end_session(user_id)
        logger.debug(f"结束答案之书会话后，用户 {user_id} 的会话状态: {self.session_data.get(user_id)}")
        return
    
    def handle_zhou_gong_dream(self, e_context: EventContext, session_data):
        context, isgroup, user_id, _, _ = self.extract_e_context_info(e_context)
        logger.debug("进入周公之梦会话")     
        self.c_modelpro.clear_user_history(user_id)
        # nickname = msg.actual_user_nickname  # 获取nickname   
        system_prompt = "你是一个拥有 25 年经验的解梦专家，你精通《周公解梦》（作者：周公）、《梦林玄解》（作者：李隆基）、《梦的解析》 作者：西格蒙德·弗洛伊德、《解梦大全》（作者：是詹姆斯·R·刘易斯）等解梦书籍。你正在为需要的人进行解梦。用户会向你描述他的梦境是什么？你要运用你渊博的解梦知识对用户的梦境进行专业解读。梦境解读搭配emoji, 发送给用户字数控制在100字以内。" 
        self.c_modelpro.set_system_prompt(system_prompt,user_id)
        model_response = self.c_modelpro.get_model_reply(context.content, user_id)
        logger.debug(f"已获取周公之解梦: {model_response}")
        model_response = f"{model_response}\n\n🆗 完成解梦，自动退出当前模式。"
        _set_reply_text(model_response, e_context, level=ReplyType.TEXT)
        self.c_modelpro.clear_user_history(user_id)
        self.end_session(user_id)
        return
    
    def handle_recipe_request(self, e_context: EventContext, session_data):
        context, isgroup, user_id, _, _ = self.extract_e_context_info(e_context)
        logger.debug("进入厨房助手会话")
        
        system_prompt = """
            你现在是一个中餐大厨，擅长做简单美味的食物，我会告诉你我目前有的食材，我喜欢的口味，下面请你依据我的食材帮我提供食谱
            要求：
            1、提供菜品名称和做法，一到三个菜之间
            2、不需要在一道菜里用完所有食材
            3、注意排版美观，适当搭配emoji        
        """ 
        self.c_modelpro.set_system_prompt(system_prompt,user_id)
        model_response = self.c_modelpro.get_model_reply(context.content, user_id)
        logger.debug(f"已获取厨房助手食谱: {model_response}")
    # 在模型回复后面添加一行提醒
        final_response = f"{model_response}\n\n🔄 发送‘退出’，可退出当前模式。"
        _set_reply_text(final_response, e_context, level=ReplyType.TEXT)
        return

    def handle_quiz_mode(self, e_context: EventContext, session_data):   
        context, isgroup, _, session_id, _ = self.extract_e_context_info(e_context)
        logger.debug("进入答题模式会话")
        
        # 此处可以根据您的需求设计问题和回答的逻辑
        system_prompt = "我想让大模型充当出题助手，你作为一个精通各个领域专业知识的出题专家，每次都会给出一道有趣的题目，题目是科学的、可以带有科普性质的、符合公共认知的[单项选择题]，注意题目内容不能胡编乱造，要[尊重客观规律，客观事实]。不用表明你的身份。其他要求如下:1.每次询问用户或由用户选择想要什么类型的题目，都要根据用户选择的题目类型，出一道题；2.注意[只给出题目和选项]，等到用户回答之后，再解析答案，你要告诉用户它回答是否正确；3.在解析答案过程中，要尽量简洁地说明各个选项对或不对的理由。4.如果用户没有更改题目类型，[解析完之后不用询问，直接给出下一到同类型的题目]，以此类推进行多轮问答，直到用户主动更改题目类型。现在，用户会告诉你想要答题的题目类型，请直接开始出题。"
        self.c_modelpro.set_system_prompt(system_prompt, session_id)
        model_response = self.c_modelpro.get_model_reply(context.content, session_id)
        logger.debug(f"已获取答题模式回复: {model_response}")
        final_response = f"{model_response}\n\n🔄 发送‘退出’，可退出当前模式。"
        _set_reply_text(final_response, e_context, level=ReplyType.TEXT)
        return
    
    def handle_comfort_mode(self, e_context: EventContext, session_data):   
        context, _, user_id, session_id, _ = self.extract_e_context_info(e_context)
        logger.debug(f"进入哄哄模式会话, session_data: {session_data}")

        if session_data == "1":
            tips = "请直接给出一个女朋友生气的理由，例如'每次回家太晚，很生气','被同事夸漂亮，男朋友不开心了'..."
            tips_response = self.c_modelpro.get_model_reply(tips, "comfort_id")
            logger.debug(f"已获取哄哄模式生气词: {tips_response}")
            self.c_modelpro.clear_user_history("comfort_id")
            self.update_session_data(user_id, 2)

            system_prompt = f"你要扮演一个生气的女朋友，每次都会有一个生气的理由，用户作为你的另一半会通过各种方式哄你，你内心要评估他哄你的方式，如果连续2次哄对了，你就表示不再生气，任何时候没哄好，则直接跟他说：分手吧。现在开始吧。你这次生气的理由是 '{tips_response}' ，你刚才说了一'哼'，等待他的回应吧。"
            self.c_modelpro.set_system_prompt(system_prompt, session_id)
            model_response = self.c_modelpro.get_model_reply(context.content, session_id)
            logger.debug(f"已获取哄哄模式回复: {model_response}")
            final_response = f"{model_response}\n\n🔄 如果哄完了，就发送‘退出’，可退出当前模式。"
            _set_reply_text(final_response, e_context, level=ReplyType.TEXT)
        else:
            model_response = self.c_modelpro.get_model_reply(context.content, session_id)
            logger.debug(f"已获取哄哄模式回复: {model_response}")
            final_response = f"{model_response}\n\n🔄 如果哄完了，就发送‘退出’，可退出当前模式。"
            _set_reply_text(final_response, e_context, level=ReplyType.TEXT)
        return

    # 以下为插件的一些辅助函数
    def has_user_drawn_today(self, user_id):
        """检查用户是否在当天已求过签"""
        if user_id in self.user_divinations:
            last_divination_date = self.user_divinations[user_id].get('date')
            return last_divination_date == datetime.now().date().isoformat()
        return False

    def extract_e_context_info(self, e_context: EventContext):
        context = e_context['context']
        isgroup = context.get("isgroup")
        msg: ChatMessage = context['msg']
        user_id = msg.actual_user_id if isgroup else msg.from_user_id
        session_id = msg.from_user_nickname if isgroup else msg.from_user_id
        nickname = msg.actual_user_nickname  # 获取nickname   
        return context, isgroup, user_id, session_id, nickname

    def base_url(self):
        return self.cc_api_base

    def start_session(self, user_session_id, state, data=None):
        self.session_data[user_session_id] = (state, data)
        logger.debug(f"用户{user_session_id}进入会话，状态: {state}, 数据: {data}")
        
    def end_session(self, user_id, session_id=None):
        # 结束基于user_id的会话
        self.session_data.pop(user_id, None)
        logger.debug(f"结束用户{user_id}的特殊会话状态")

        # 如果提供了session_id，同时结束基于session_id的会话
        if session_id:
            self.session_data.pop(session_id, None)
            logger.debug(f"结束特殊会话用户{session_id}的状态")
            
    def get_session_state(self, user_id, session_id=None):
        # 如果提供了session_id且其状态非NORMAL，则使用session_id的状态
        if session_id and self.session_data.get(session_id, ("NORMAL", None))[0] != "NORMAL":
            logger.debug(f"检测到有特殊会话状态的session_id: {session_id}, 状态为：{self.session_data.get(session_id)}")
            return self.session_data.get(session_id)
        else:
            # 否则，使用user_id的状态
            logger.debug(f"检测到当前user_id: {user_id}的会话状态: {self.session_data.get(user_id)}")
            return self.session_data.get(user_id, ("NORMAL", None))

    def update_session_data(self, user_session_id, new_data):
        if user_session_id in self.session_data:
            current_state, _ = self.session_data[user_session_id]
            self.session_data[user_session_id] = (current_state, new_data)
            logger.debug(f"更新用户{user_session_id}的会话数据为: {new_data}")


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




