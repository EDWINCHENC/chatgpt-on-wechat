import openai
import google.generativeai as genai
import json
import os
from common.log import logger

class UnifiedChatbot:
    def __init__(self):
        # 从配置文件中加载模型配置
        curdir = os.path.dirname(__file__)
        self.config_path = os.path.join(curdir, "config.json")
        with open(self.config_path, "r", encoding="utf-8") as f:
            config = json.load(f)

        # OpenAI配置
        self.openai_api_key = config.get("openai_api_key", "")
        self.openai_api_base = config.get("open_ai_api_base", "https://api.openai.com/v1")
        self.openai_model = "gpt-3.5-turbo-0613"
        openai.api_key = self.openai_api_key
        openai.api_base = self.openai_api_base


        # Gemini配置
        self.gemini_api_key = config.get("gemini_api_key", "")
        self.gemini_model = genai.GenerativeModel('gemini-pro')
        genai.configure(api_key=self.gemini_api_key)

        self.user_histories = {}
        # 设置默认用户 ID
        self.user_histories[self.DEFAULT_USER_ID] = []
        self.ai_model = config.get("ai_model", "OpenAI")

    # ... 其他已有的方法 ...
    DEFAULT_USER_ID = "default_user"

    def get_user_history(self, user_id=None):
        user_id = user_id or self.DEFAULT_USER_ID
        if user_id not in self.user_histories:
            self.user_histories[user_id] = []
        return self.user_histories[user_id]
    
    def clear_user_history(self, user_id=None):
        user_id = user_id or self.DEFAULT_USER_ID
        if user_id in self.user_histories:
            self.user_histories[user_id] = []
            return True
        return False

    def clear_all_histories(self):
        self.user_histories.clear()

    def set_system_prompt(self, prompt, user_id=None):
        user_id = user_id or self.DEFAULT_USER_ID
        # 设置特定用户的系统级别提示
        history = self.get_user_history(user_id)
        if history[0]["role"] == "system":
            history[0]["content"] = prompt  # 更新已存在的系统提示
        else:
            history.insert(0, {"role": "system", "content": prompt})  # 插入新的系统提示

    def add_message_openai(self, role, content, user_id=None):
        user_id = user_id or self.DEFAULT_USER_ID
        history = self.get_user_history(user_id)
        history.append({"role": role, "content": content})
        self._trim_history(history)

    def add_message_gemini(self, role, text, user_id=None):
        user_id = user_id or self.DEFAULT_USER_ID
        history = self.get_user_history(user_id)
        history.append({'role': role, 'parts': [text]})
        self._trim_history(history)

    def set_initial_history(self, initial_messages, user_id=None):
        """
        为指定的用户设置初始的对话历史。
        initial_messages 应该是一个列表，其中包含字典，每个字典代表一条消息，包含 'role' 和 'content' 或 'parts' 键。
        """
        user_id = user_id or self.DEFAULT_USER_ID
        if not isinstance(initial_messages, list):
            raise ValueError("initial_messages 应该是一个列表。")

        history = self.get_user_history(user_id)
        for message in initial_messages:
            if 'content' in message:
                self.add_message_openai(user_id, message['role'], message['content'])
            elif 'parts' in message:
                self.add_message_gemini(user_id, message['role'], message['parts'][0])
            else:
                raise ValueError("消息应该包含 'content' 或 'parts' 键。")

        self._trim_history(history)  # 确保历史记录不会超出预设的长度

    def _trim_history(self, history):
        max_history_length = 13  # 示例值
        # 首先检查历史记录是否为空
        if not history:
            return

        # 如果当前模型是 OpenAI 并且历史记录中包含 system 提示，那么保留 system 提示
        if self.ai_model == "OpenAI" and history[0]["role"] == "system":
            while len(history) > max_history_length:
                history[:] = history[:1] + history[3:]
        # 如果当前模型是 Gemini 或者历史记录中没有 system 提示，那么直接移除最旧的记录
        else:
            # 如果历史记录中有 system 提示，先移除它
            if history[0]["role"] == "system":
                history.pop(0)
            # 然后根据历史记录的最大长度移除最旧的记录
            while len(history) > max_history_length - 1:  # 减去 1 因为不再包含 system 提示
                history[:] = history[2:]


    def get_reply(self, user_input, user_id=None):
        user_id = user_id or self.DEFAULT_USER_ID
        if self.ai_model == "OpenAI":
            return self._get_reply_openai(user_id, user_input)
        elif self.ai_model == "Gemini":
            return self._get_reply_gemini(user_id, user_input)

    def _get_reply_openai(self, user_input, user_id=None):
        user_id = user_id or self.DEFAULT_USER_ID
        self.add_message_openai(user_id, "user", user_input)
        try:
            history = self.get_user_history(user_id)
            response = openai.ChatCompletion.create(
                model=self.openai_model,
                messages=history
            )
            reply_text = response["choices"][0]["message"]['content']
            self.add_message_openai(user_id, "assistant", reply_text)
            return reply_text
        except Exception as e:
            # 发生异常时，移除最后一条用户输入
            history = self.get_user_history(user_id)
            history.pop(-1) if history and history[-1]["role"] == "user" else None
            return self.handle_exception(e)

    def handle_exception(self, e):
        message = "出现了一些问题，请稍后再试。"
        if isinstance(e, openai.error.RateLimitError):
            logger.warn("[OPENAI] RateLimitError: {}".format(e))
            message = "请求太频繁，请稍后再试。"
        elif isinstance(e, openai.error.Timeout):
            logger.warn("[OPENAI] Timeout: {}".format(e))
            message = "请求超时，请稍后再试。"
        elif isinstance(e, openai.error.APIError):
            logger.warn("[OPENAI] APIError: {}".format(e))
            message = "API 错误，请稍后再试。"
        elif isinstance(e, openai.error.APIConnectionError):
            logger.warn("[OPENAI] APIConnectionError: {}".format(e))
            message = "网络连接错误，请稍后再试。"
        else:
            logger.error(f"Error: {e}")

        return message



    def _get_reply_gemini(self, user_input, user_id=None):
        user_id = user_id or self.DEFAULT_USER_ID
        self.add_message_gemini(user_id, 'user', user_input)
        try:
            history = self.get_user_history(user_id)
            response = self.gemini_model.generate_content(history)
            if response.prompt_feedback and response.prompt_feedback.block_reason:
                print(f"提示被阻止，原因: {response.prompt_feedback.block_reason}")
                # 移除这次的用户输入
                history.pop(-1)
                return None

            model_response = response.text
            if model_response:
                model_response = self.remove_markdown(model_response)
                self.add_message_gemini(user_id, 'model', model_response)
                return model_response
            else:
                # 模型未产生有效回应，可选择移除该轮用户输入
                history.pop(-1)
                return "对不起，我没能理解你的意思。"
        except Exception as e:
            return f"发生错误: {e}"

    def remove_markdown(self, text):
        # 替换Markdown的粗体标记
        text = text.replace("**", "")
        # 替换Markdown的标题标记
        text = text.replace("### ", "").replace("## ", "").replace("# ", "")
        return text

# # 实例化 UnifiedChatbot
# bot = UnifiedChatbot()

# # 用户列表
# user_ids = ["user1", "user2"]

# # 为每个用户设置系统级提示词
# system_prompts = {
#     "user1": "你是一个诗歌生成工具，每次都会生成一首诗。",
#     "user2": "你是一个科学问答机器人，专门回答科学相关的问题。"
# }

# # 设置系统级提示词并进行对话
# for user_id in user_ids:
#     # 设置系统级提示词
#     bot.set_system_prompt(user_id, system_prompts[user_id])
#     print(f"--- 开始与 {user_id} 的会话 ---")
#     for i in range(3):
#         user_input = input(f"{user_id} 输入: ")
#         reply = bot.get_reply(user_id, user_input)
#         print(f"模型回复: {reply}")

# def display_history(user_id):
#     history = bot.get_user_history(user_id)
#     print(f"\n--- {user_id} 的历史记录 ---")
#     for message in history:
#         role = message.get("role")
#         content = ""
#         if role == "system":
#             content = message.get("content")
#         elif role in ["user", "assistant", "model"]:
#             # 针对 Gemini 和 OpenAI 的不同历史记录格式进行检查
#             parts = message.get("parts")
#             content = parts[0] if parts else message.get("content", "消息内容缺失")
#         print(f"{role.capitalize()}: {content}")



# for user_id in user_ids:
#     display_history(user_id)
