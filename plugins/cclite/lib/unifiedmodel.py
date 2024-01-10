import openai
import google.generativeai as genai
import json
import os

class UnifiedChatbot:
    def __init__(self):
        # 从配置文件中加载模型配置
        curdir = os.path.dirname(__file__)
        self.config_path = os.path.join(curdir, "config.json")
        print(f"尝试读取配置文件: {self.config_path}")
        with open(self.config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
        print("配置文件内容:", config)

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

    def set_ai_model(self, model_name):
        """设置 AI 模型"""
        # 将输入的模型名称转换为全部小写，以便进行不区分大小写的比较
        model_name_lower = model_name.lower()
        if model_name_lower == "openai":
            self.ai_model = "OpenAI"  # 使用规范的模型名称
            return "已切换到 OpenAI 模型。"
        elif model_name_lower == "gemini":
            self.ai_model = "Gemini"  # 使用规范的模型名称
            return "已切换到 Gemini 模型。"
        else:
            return "无效的模型名称。请使用 'OpenAI' 或 'Gemini'。"

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
        # 检查历史记录是否为空
        if not history:
            # 直接添加新的系统提示
            history.append({"role": "system", "content": prompt})
        else:
            # 检查第一条记录是否是系统提示，进行更新或插入操作
            if history[0]["role"] == "system":
                history[0]["content"] = prompt
            else:
                history.insert(0, {"role": "system", "content": prompt})

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
        user_id = user_id or self.DEFAULT_USER_ID
        if not isinstance(initial_messages, list):
            raise ValueError("initial_messages 应该是一个列表。")

        history = self.get_user_history(user_id)
        for message in initial_messages:
            if 'content' in message:
                # 直接向历史记录中添加消息
                history.append({"role": message['role'], "content": message['content']})
            elif 'parts' in message:
                # 如果使用 Gemini API，处理 parts
                history.append({'role': message['role'], 'parts': message['parts']})
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


    def get_model_reply(self, user_input, user_id=None):
        user_id = user_id or self.DEFAULT_USER_ID
        print(f"当前 AI 模型: {self.ai_model}")  # 调试打印
        if self.ai_model == "OpenAI":
            print("调用 _get_reply_openai")  # 调试打印
            return self._get_reply_openai(user_input, user_id)
        elif self.ai_model == "Gemini":
            print("调用 _get_reply_gemini")  # 调试打印
            return self._get_reply_gemini(user_input, user_id)

    def _get_reply_openai(self, user_input, user_id=None):
        print("进入 _get_reply_openai 方法")  # 调试打印
        if not user_input.strip():
            return "用户输入为空"
        user_id = user_id or self.DEFAULT_USER_ID
        print(f"当前用户 ID: {user_id}， 输入为{user_input}")
        self.add_message_openai("user", user_input, user_id)
        try:
            history = self.get_user_history(user_id)
            print("传递给OpenAI的历史记录:", history)  # 调试打印
            response = openai.ChatCompletion.create(
                model=self.openai_model,
                messages=history
            )
            reply_text = response["choices"][0]["message"]['content']
            self.add_message_openai("assistant", reply_text, user_id)
            return reply_text
        except Exception as e:
            # 发生异常时，移除最后一条用户输入
            print(f"发生异常: {e}")
            history = self.get_user_history(user_id)
            history.pop(-1) if history and history[-1]["role"] == "user" else None
            return self.handle_exception(e)

    def handle_exception(self, e):
        message = "出现了一些问题，请稍后再试。"
        if isinstance(e, openai.error.RateLimitError):
            # logger.warn("[OPENAI] RateLimitError: {}".format(e))
            message = f"请求太频繁，请稍后再试。错误信息：{e}"
        elif isinstance(e, openai.error.Timeout):
            # logger.warn("[OPENAI] Timeout: {}".format(e))
            message = f"请求超时，请稍后再试。错误信息：{e}"
        elif isinstance(e, openai.error.APIError):
            # logger.warn("[OPENAI] APIError: {}".format(e))
            message = f"API 错误，请稍后再试。错误信息：{e}"
        elif isinstance(e, openai.error.APIConnectionError):
            # logger.warn("[OPENAI] APIConnectionError: {}".format(e))
            message = f"网络连接错误，请稍后再试。错误信息：{e}"
        else:
            message = (f"Error: {e}")

        return message



    def _get_reply_gemini(self, user_input, user_id=None):
        user_id = user_id or self.DEFAULT_USER_ID
        self.add_message_gemini('user', user_input, user_id)
        try:
            history = self.get_user_history(user_id)
            print("调用 Gemini API 前的历史记录:", history)  # 调试打印
            response = self.gemini_model.generate_content(history)
            if response.prompt_feedback and response.prompt_feedback.block_reason:
                print(f"提示被阻止，原因: {response.prompt_feedback.block_reason}")
                # 移除这次的用户输入
                history.pop(-1)
                return None

            model_response = response.text
            if model_response:
                model_response = self.remove_markdown(model_response)
                self.add_message_gemini('model', model_response, user_id)
                print("调用 Gemini API 后的历史记录:", self.get_user_history(user_id))  # 调试打印
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
    
    
# 1. 实例化 UnifiedChatbot 类
chatbot = UnifiedChatbot()

# 2. 设置系统提示
system_prompt = "你好，我是一个智能助手，有什么可以帮助你的吗？"
chatbot.set_system_prompt(system_prompt)

# 3. 设置初始对话历史并打印
initial_messages = [
    {"role": "user", "content": "你能告诉我当前的天气吗？"},
    {"role": "assistant", "content": "当然，当前在北京的天气是晴朗的。"}
]
chatbot.set_initial_history(initial_messages)

# 4. 模拟一轮对话并打印结果
user_input = "明天北京的天气怎么样？"
print("\n用户输入:", user_input)
response = chatbot.get_model_reply(user_input)
print("模型回复:", response)

# 5. 模拟多轮会话并打印结果
additional_inputs = ["还会下雨吗？", "谢谢你的帮助！"]
for input in additional_inputs:
    print("\n用户输入:", input)
    response = chatbot.get_model_reply(input)
    print("模型回复:", response)

# 6. 打印最终的会话历史
final_history = chatbot.get_user_history()
print("\n最终的会话历史:")
for message in final_history:
    role = message.get("role")
    content = message.get("content")
    print(f"{role}: {content}")

# 7. 清空会话历史并打印结果
chatbot.clear_user_history()
print("\n清空后的会话历史:", chatbot.get_user_history())
