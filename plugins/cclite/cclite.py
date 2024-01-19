import plugins
import requests
import json
from bridge.context import ContextType
from bridge.reply import Reply, ReplyType
from channel.chat_message import ChatMessage
from plugins import *
from common.log import logger
import os
from .lib.model_factory import ModelGenerator
from .lib.unifiedmodel import UnifiedChatbot


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
                logger.info("[cclite] inited")
        except Exception as e:
            logger.error(f"[cclite] init error: {e}")

    
    def on_handle_context(self, e_context: EventContext):
        context = e_context['context']
        msg: ChatMessage = context['msg']
        # user_id = msg.from_user_id
        isgroup = e_context["context"].get("isgroup")
        user_id = msg.actual_user_id if isgroup else msg.from_user_id
        # 过滤不需要处理的内容类型
        if context.type not in [ContextType.TEXT, ContextType.IMAGE, ContextType.IMAGE_CREATE, ContextType.FILE, ContextType.SHARING]:
            return

        if context.type == ContextType.TEXT:

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
            elif "cmodel" in content_lower:
                response = self.c_model.get_current_model()
                _set_reply_text(response, e_context, level=ReplyType.TEXT)
                return

            user_input = context.content
            response = self.c_modelpro.get_model_reply(user_input, user_id)
            _set_reply_text(response, e_context, level=ReplyType.TEXT)     
            return

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




