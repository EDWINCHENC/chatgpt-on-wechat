import openai
import google.generativeai as genai
import json
import os
from http import HTTPStatus
import dashscope
from zhipuai import ZhipuAI
from common.log import logger
# import logging
# logger = logging.getLogger(__name__)

class UnifiedChatbot:
    def __init__(self):
        # 从配置文件中加载模型配置
        curdir = os.path.dirname(__file__)
        self.config_path = os.path.join(curdir, "config.json")
        print(f"尝试读取配置文件: {self.config_path}")
        with open(self.config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
        print("配置文件内容:", config)
        logger.debug(f"配置文件内容: {config}")

        # OpenAI配置
        self.openai_api_key = config.get("openai_api_key", "")
        self.openai_api_base = config.get("open_ai_api_base", "https://api.openai.com/v1")
        self.openai_model = "gpt-4-1106-preview"
        openai.api_key = self.openai_api_key
        openai.api_base = self.openai_api_base


        # Gemini配置
        self.gemini_api_key = config.get("gemini_api_key", "")
        self.gemini_model = genai.GenerativeModel('gemini-pro')
        genai.configure(api_key=self.gemini_api_key)
        
        # Qwen配置
        self.dashscope_api_key = config.get("dashscope_api_key", "")
        self.qwen_model = 'qwen-max'  # 模型名称
        # 配置 Dashscope API
        dashscope.api_key=self.dashscope_api_key
        
        # ZhipuAI配置
        self.zhipuai_api_key = config.get("zhipuai_api_key", "")
        self.zhipuai_model = "glm-4"
        self.zhipuai_client = ZhipuAI(api_key=self.zhipuai_api_key)
        # ZhipuAI图像模型配置
        self.zhipuai_image_model = "cogview-3"

        # 其他配置
        self.user_histories = {}
        # 设置默认用户 ID
        self.user_histories[self.DEFAULT_USER_ID] = []
        self.ai_model = config.get("ai_model", "OpenAI")

    # 常量定义
    DEFAULT_USER_ID = "default_user"

    def set_ai_model(self, model_name):
        """设置 AI 模型"""
        # 将输入的模型名称转换为全部小写，以便进行不区分大小写的比较
        model_name_lower = model_name.lower()
        # 在切换模型前清除所有用户的历史记录
        self.clear_all_histories()
        if model_name_lower == "openai":
            self.ai_model = "OpenAI"  # 使用规范的模型名称
            logger.debug(f"已切换到 OpenAI 模型。")
            return "已切换到 OpenAI 模型。"
        elif model_name_lower == "gemini":
            self.ai_model = "Gemini"  # 使用规范的模型名称
            logger.debug(f"已切换到 Gemini 模型。")
            return "已切换到 Gemini 模型。"
        elif model_name_lower == "qwen":
            self.ai_model = "Qwen"
            logger.debug(f"已切换到 Qwen 模型。")
            return "已切换到 Qwen 模型。"
        elif model_name_lower == "zhipuai":
            self.ai_model = "ZhipuAI"
            logger.debug(f"已切换到 ZhipuAI 模型。")
            return "已切换到 ZhipuAI 模型。"
        else:
            return "无效的模型名称。"

    def get_user_history(self, user_id=None):
        user_id = user_id or self.DEFAULT_USER_ID
        if user_id not in self.user_histories:
            self.user_histories[user_id] = []
        # logger.debug(f"当前用户 {user_id} 的历史记录: {self.user_histories[user_id]}")
        return self.user_histories[user_id]
    
    def clear_user_history(self, user_id=None):
        user_id = user_id or self.DEFAULT_USER_ID
        if user_id in self.user_histories:
            self.user_histories[user_id] = []
            logger.debug(f"已清空用户 {user_id} 的历史记录。")
            return True
        return False

    def clear_all_histories(self):
        self.user_histories.clear()
        logger.debug("已清空所有历史记录。")

    def set_system_prompt(self, prompt, user_id=None):
        user_id = user_id or self.DEFAULT_USER_ID
        # 设置特定用户的系统级别提示
        history = self.get_user_history(user_id)
        # 检查历史记录是否为空
        if not history:
            # 直接添加新的系统提示
            history.append({"role": "system", "content": prompt})
            logger.debug(f"已设置用户 {user_id} 的系统提示: {prompt}")
        else:
            # 检查第一条记录是否是系统提示，进行更新或插入操作
            if history[0]["role"] == "system":
                history[0]["content"] = prompt
            else:
                history.insert(0, {"role": "system", "content": prompt})
            logger.debug(f"已更新或插入用户 {user_id} 的系统提示: {prompt}")

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
    
    def add_message_qwen(self, role, content, user_id=None):
        user_id = user_id or self.DEFAULT_USER_ID
        history = self.get_user_history(user_id)
        history.append({'role': role, 'content': content})
        self._trim_history(history)

    def add_message_zhipuai(self, role, content, user_id=None):
        user_id = user_id or self.DEFAULT_USER_ID
        history = self.get_user_history(user_id)
        history.append({'role': role, 'content': content})
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
        max_history_length = 7  # 示例值
        
        if not history:
            return
        # 移除第一条 'assistant' 记录（如果存在）
        if history[0]["role"] == "assistant":
            history.pop(0)
            logger.debug("移除1条助手记录")

        # 如果模型不是 OpenAI 或 Qwen 且第一条是 'system'，则移除
        if self.ai_model not in ["OpenAI", "Qwen", "ZhipuAI"] and history[0]["role"] == "system":
            history.pop(0)
            logger.debug("移除1条系统提示")

        # 根据模型特定逻辑修剪历史记录
        if self.ai_model in ["OpenAI", "Qwen", "ZhipuAI"] and history and history[0]["role"] == "system":
            while len(history) > max_history_length:
                # 确保至少有3条历史记录
                if len(history) > 3:
                    logger.debug("移除2条历史记录")
                    history[:] = history[:1] + history[3:]
                else:
                    break
        else:
            while len(history) > max_history_length - 1:
                if len(history) > 2:
                    logger.debug("移除2条历史记录")
                    history[:] = history[2:]
                else:
                    break

    def get_model_reply(self, user_input, user_id=None):
        user_id = user_id or self.DEFAULT_USER_ID
        logger.debug(f"当前使用的模型为：{self.ai_model}")
        if self.ai_model == "OpenAI":
            logger.debug("调用 _get_reply_openai")  # 调试打印
            return self._get_reply_openai(user_input, user_id)
        elif self.ai_model == "Gemini":
            logger.debug("调用 _get_reply_gemini")  # 调试打印
            return self._get_reply_gemini(user_input, user_id)
        elif self.ai_model == "Qwen":
            logger.debug("调用 _get_reply_qwen")  # 调试打印
            return self._get_reply_qwen(user_input, user_id)
        elif self.ai_model == "ZhipuAI":
            logger.debug("调用 _get_reply_zhipuai")  # 调试打印
            return self._get_reply_zhipuai(user_input, user_id)
        else:
            return "未知的 AI 模型。"

    # 获取OpenAI 模型的响应
    def _get_reply_openai(self, user_input, user_id=None):
        logger.debug(f"进入 _get_reply_openai 方法")
        if not user_input.strip():
            return "用户输入为空"
        user_id = user_id or self.DEFAULT_USER_ID
        logger.debug(f"当前用户 ID: {user_id}")
        logger.debug(f"向 OpenAI 发送消息: {user_input}")
        self.add_message_openai("user", user_input, user_id)
        try:
            history = self.get_user_history(user_id)
            logger.debug(f"传递给 OpenAI 的历史记录: {history}")  # 调试打印")
            response = openai.ChatCompletion.create(
                model=self.openai_model,
                messages=history
            )
            reply_text = response["choices"][0]["message"]['content']
            self.add_message_openai("assistant", reply_text, user_id)
            return f"{reply_text}[O]"
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

    # 获取Gemini 模型的响应
    def _get_reply_gemini(self, user_input, user_id=None):
        user_id = user_id or self.DEFAULT_USER_ID
        logger.debug(f"进入 _get_reply_gemini 方法")
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
                return f"{model_response}[G]" 
            else:
                # 模型未产生有效回应，可选择移除该轮用户输入
                history.pop(-1)
                return "对不起，我没能理解你的意思。"
        
        except Exception as e:
            return f"发生错误: {e}"

    # 获取Qwen 模型的响应       
    def _get_reply_qwen(self, user_input, user_id=None):
        user_id = user_id or self.DEFAULT_USER_ID
        logger.debug(f"进入 _get_reply_qwen 方法")
        logger.debug(f"当前用户 ID: {user_id}")
        logger.debug(f"向 Qwen API 发送消息: {user_input}")
        self.add_message_qwen('user', user_input, user_id)
        try:
            history = self.get_user_history(user_id)
            logger.debug(f"传递给 Qwen API 的历史记录: {history}")  # 调试打印
            # 调用 Dashscope API
            response = dashscope.Generation.call(
                model=self.qwen_model,
                messages=history,
                enable_search=True,
                # max_tokens=5000,
                result_format='message'
            )
            # logger.debug(f"来自 Dashscope 的回复: {json.dumps(response, ensure_ascii=False)}")
            if response.status_code == HTTPStatus.OK:
                # 直接提取所需信息
                reply_content = response.output.get("choices", [{}])[0].get("message", {}).get("content", "")
                self.add_message_qwen('assistant', reply_content, user_id)
                reply_content = self.remove_markdown(reply_content)
                return f"{reply_content}[Q]" if reply_content else "未收到有效回复。"
            else:
                # 移除最后一条用户输入
                history.pop(-1) if history and history[-1]["role"] == "user" else None
                return f"请求错误: 状态码 {response.status_code}, 消息: {response.message}"
        except Exception as e:
            # logger.error(f"Error generating summary with Dashscope: {e}")
            history.pop(-1) if history and history[-1]["role"] == "user" else None
            return f"Qwen模型调用出错: {e}"

    # 获取Zhipuai 模型的响应
    def _get_reply_zhipuai(self, user_input, user_id=None):
        user_id = user_id or self.DEFAULT_USER_ID
        logger.debug(f"进入 _get_reply_zhipuai 方法")
        logger.debug(f"当前用户 ID: {user_id}")
        logger.debug(f"向 Zhipuai API 发送消息: {user_input}")
        self.add_message_zhipuai('user', user_input, user_id)
        try:
            history = self.get_user_history(user_id)
            logger.debug(f"传递给 Zhipuai API 的历史记录: {history}")  # 调试打印
            response = self.zhipuai_client.chat.completions.create(
                model=self.zhipuai_model,
                messages=history,
                # top_p=0.7,
                # temperature=0.9,
                # stream=False,
                max_tokens=1500
            )
            reply_text = response.choices[0].message.content
            self.add_message_zhipuai('assistant', reply_text, user_id)
            reply_text = self.remove_markdown(reply_text)
            return f"{reply_text}[Z]"
        except Exception as e:
            history.pop(-1) if history and history[-1]["role"] == "user" else None
            return self.handle_exception(e)

    def _generate_image_zhipuai(self, prompt):
        model_name = self.zhipuai_image_model
        logger.debug(f"调用 Zhipuai API 生成图像: {prompt}")
        try:
            response = self.zhipuai_client.images.generations(
                model=model_name,
                prompt=prompt
            )
            return response.data[0].url if response.data else "未能生成图像"
        except Exception as e:
            return f"生成图像时发生错误: {e}"



    def remove_markdown(self, text):
        # 替换Markdown的粗体标记
        text = text.replace("**", "")
        # 替换Markdown的标题标记
        text = text.replace("### ", "").replace("## ", "").replace("# ", "")
        return text
    
    
# # 1. 实例化 UnifiedChatbot 类
# chatbot = UnifiedChatbot()

# # 2. 设置系统提示
# system_prompt = "你好，我是一个智能助手，有什么可以帮助你的吗？"
# chatbot.set_system_prompt(system_prompt)

# # 3. 设置初始对话历史并打印
# initial_messages = [
#     {"role": "user", "content": "你能告诉我当前的天气吗？"},
#     {"role": "assistant", "content": "当然，当前在北京的天气是晴朗的。"}
# ]
# chatbot.set_initial_history(initial_messages)

# # 4. 模拟一轮对话并打印结果
# user_input = "明天北京的天气怎么样？"
# print("\n用户输入:", user_input)
# response = chatbot.get_model_reply(user_input)
# print("模型回复:", response)

# # 5. 模拟多轮会话并打印结果
# additional_inputs = ["还会下雨吗？", "谢谢你的帮助！"]
# for input in additional_inputs:
#     print("\n用户输入:", input)
#     response = chatbot.get_model_reply(input)
#     print("模型回复:", response)

# # 6. 打印最终的会话历史
# final_history = chatbot.get_user_history()
# print("\n最终的会话历史:")
# for message in final_history:
#     role = message.get("role")
#     content = message.get("content")
#     print(f"{role}: {content}")

# # 7. 清空会话历史并打印结果
# chatbot.clear_user_history()
# print("\n清空后的会话历史:", chatbot.get_user_history())


# # 创建UnifiedChatbot实例
# chatbot = UnifiedChatbot()

# # 设置AI模型为Qwen
# chatbot.set_ai_model("Qwen")

# # 预设一些初始历史对话
# initial_history = [
#     {"role": "user", "content": "你觉得未来的科技趋势是什么？"},
#     {"role": "assistant", "content": "我认为人工智能和量子计算将是重要的趋势。"}
# ]
# chatbot.set_initial_history(initial_history)

# # 打印预设的历史对话
# print("预设的历史对话:", chatbot.get_user_history())

# # 开始测试三轮对话
# # 第一轮会话
# user_input1 = "那你认为人工智能会带来哪些改变？"
# print(f"\n用户输入: {user_input1}")
# response1 = chatbot.get_model_reply(user_input1)
# print("模型回复:", response1)
# print("第一轮会话后的历史记录:", chatbot.get_user_history())

# # 第二轮会话
# user_input2 = "人工智能在医疗领域的应用前景如何？"
# print(f"\n用户输入: {user_input2}")
# response2 = chatbot.get_model_reply(user_input2)
# print("模型回复:", response2)
# print("第二轮会话后的历史记录:", chatbot.get_user_history())

# # 第三轮会话
# user_input3 = "人工智能对人类的伦理和社会有什么影响？"
# print(f"\n用户输入: {user_input3}")
# response3 = chatbot.get_model_reply(user_input3)
# print("模型回复:", response3)
# print("第三轮会话后的历史记录:", chatbot.get_user_history())
