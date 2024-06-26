import os
import json
from config import conf
from common.log import logger
import openai
import google.generativeai as genai
from http import HTTPStatus
import dashscope
import requests

class ModelGenerator:
    def __init__(self):
        # 设置数据库路径和API配置
        curdir = os.path.dirname(__file__)
        self.openai_api_key = conf().get("open_ai_api_key")
        self.openai_api_base = conf().get("open_ai_api_base", "https://api.openai.com/v1")
        self.gemini_api_key = conf().get("gemini_api_key")

        logger.debug(f"[ModelGenerator] openai_api_key: {self.openai_api_key}")
        logger.debug(f"[ModelGenerator] gemini_api_key: {self.gemini_api_key}")

        # 从配置文件中加载模型类型
        self.config_path = os.path.join(curdir, "config.json")
        with open(self.config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
            logger.info(f"[ModelGenerator] config content: {config}")
        self.ai_model = config.get("ai_model", "OpenAI")
        self.dashscope_api_key = config.get("dashscope_api_key")
        
        self.perplexity_api_key = config.get("perplexity_api_key")  # 确保这里正确地获取了API密钥


    def set_ai_model(self, model_name):
        """设置 AI 模型"""
        # 将输入的模型名称转换为全部小写，以便进行不区分大小写的比较
        model_name_lower = model_name.lower()
        if model_name_lower == "openai":
            self.ai_model = "OpenAI"  # 使用规范的模型名称
            logger.debug(f"[ModelGenerator] ai_model: {self.ai_model}")
            return "已切换到 OpenAI 模型。"
        elif model_name_lower == "gemini":
            self.ai_model = "Gemini"  # 使用规范的模型名称
            logger.debug(f"[ModelGenerator] ai_model: {self.ai_model}")
            return "已切换到 Gemini 模型。"
        elif model_name.lower() == "qwen":
            self.ai_model = "Qwen"
            logger.debug(f"[ModelGenerator] ai_model: {self.ai_model}")
            return "已切换到 Qwen 模型。"
        else:
            return "无效的模型名称。请使用 'OpenAI' 或 'Gemini' 或 'Qwen'。"

    def get_current_model(self):
        """获取当前 AI 模型"""
        return f"当前模型为: {self.ai_model}"

    def _generate_model_analysis(self, prompt, combined_content):
        if self.ai_model == "OpenAI":
            messages = self._build_openai_messages(prompt, combined_content)
            return self._generate_summary_with_openai(messages)

        elif self.ai_model == "Gemini":
            messages = self._build_gemini_messages(prompt, combined_content)
            return self._generate_summary_with_gemini_pro(messages)
        
        elif self.ai_model == "Qwen":
            messages = self._build_dashscope_messages(prompt, combined_content)
            return self._generate_summary_with_dashscope(messages)

        elif self.ai_model == "Perplexity":
            messages = self._build_perplexity_messages(prompt, combined_content)
            return self._generate_summary_with_perplexity(messages)

    def _build_openai_messages(self, prompt, user_input):
        return [
            {"role": "system", "content": prompt},
            {"role": "user", "content": user_input}
        ]

    def _build_gemini_messages(self, prompt, user_input):
        prompt_parts = [
            prompt,
            "input: " + user_input,
            "output: "
        ]
        return prompt_parts

    def _build_dashscope_messages(self, prompt, user_input):
        return [
            {'role': 'system', 'content': prompt},
            {'role': 'user', 'content': user_input}
        ]
        
    def _build_perplexity_messages(self, prompt, user_input):
        # 构建适用于Mistral的消息格式
        return [
            {"role": "system", "content": prompt},
            {"role": "user", "content": user_input}
        ]

    def _generate_summary_with_openai(self, messages):
        """使用 OpenAI ChatGPT 生成总结"""
        try:
            # 设置 OpenAI API 密钥和基础 URL
            openai.api_key = self.openai_api_key
            openai.api_base = self.openai_api_base

            logger.debug(f"向 OpenAI 发送消息: {messages}")

            # 调用 OpenAI ChatGPT
            response = openai.ChatCompletion.create(
                model="gpt-4-1106-preview",
                messages=messages
            )
            logger.debug(f"来自 OpenAI 的回复: {json.dumps(response, ensure_ascii=False)}")
            reply_text = response["choices"][0]["message"]['content']  # 获取模型返回的消息
            return f"{reply_text}[O]"
        except Exception as e:
            logger.error(f"Error generating summary with OpenAI: {e}")
            return "有些累了，请稍后再试。"

    def _generate_summary_with_gemini_pro(self, messages):
        """使用 Gemini Pro 生成总结"""
        try:
            # 配置 Gemini Pro API 密钥
            genai.configure(api_key=self.gemini_api_key)
            # Set up the model
            # generation_config = {
            # "temperature": 0.8,
            # "top_p": 1,
            # "top_k": 1,
            # "max_output_tokens": 8192,
            # }

            # 创建 Gemini Pro 模型实例
            model = genai.GenerativeModel(model_name="gemini-pro")    # optionally: generation_config=generation_config
            logger.debug(f"向 Gemini Pro 发送消息: {messages}")
            # 调用 Gemini Pro 生成内容
            response = model.generate_content(messages)
            reply_text = self.remove_markdown(response.text)
            logger.debug(f"从 Gemini Pro 获取的回复: {reply_text}")
            return f"{reply_text}[G]"

        except Exception as e:
            logger.error(f"Error generating summary with Gemini Pro: {e}")
            return "有些累了，请稍后再试。"

    def _generate_summary_with_dashscope(self, messages):
        # 使用 Dashscope 生成总结
        try:
            # 配置 Dashscope API
            dashscope.api_key=self.dashscope_api_key
            logger.debug(f"向 Dashscope 发送消息: {messages}")
            # 调用 Dashscope API
            response = dashscope.Generation.call(
                model='qwen-max-1201',
                messages=messages,
                # max_tokens=5000,
                result_format='message'
            )
            logger.debug(f"来自 Dashscope 的回复: {json.dumps(response, ensure_ascii=False)}")
            if response.status_code == HTTPStatus.OK:
                # 直接提取所需信息
                reply_content = response.output.get("choices", [{}])[0].get("message", {}).get("content", "")
                return f"{reply_content}[Q]" if reply_content else "未收到有效回复。"
            else:
                return f"请求错误: 状态码 {response.status_code}, 消息: {response.message}"

        except Exception as e:
            logger.error(f"Error generating summary with Dashscope: {e}")
            return "有些累了，请稍后再试。"

    def _generate_summary_with_perplexity(self, messages):
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.perplexity_api_key}'
        }
        data = {
            "model": "pplx-7b-online",
            "messages": messages
        }
        try:
            logger.debug(f"向 Perplexity 发送消息: {messages}")
            api_url = "https://api.perplexity.ai/chat/completions"
            response = requests.post(api_url, headers=headers, json=data)
            logger.debug(f"来自 Perplexity 的回复: {json.dumps(response.json(), ensure_ascii=False)}")
            response.raise_for_status()
            # 处理响应数据
            response_data = response.json()
            # 这里可以根据你的需要处理响应数据
            # 解析 JSON 并获取 content
            if "choices" in response_data and len(response_data["choices"]) > 0:
                first_choice = response_data["choices"][0]
                if "message" in first_choice and "content" in first_choice["message"]:
                    reply_content = first_choice["message"]["content"]
                    return f"{reply_content}[P]" if reply_content else "未收到有效回复。"
                else:
                    return "Content not found in the response"
            else:
                return "No choices available in the response"
        except requests.exceptions.RequestException as e:
            # 处理可能出现的错误
            logger.error(f"Error calling perplexity: {e}")



    def remove_markdown(self, text):
        # 替换Markdown的粗体标记
        text = text.replace("**", "")
        # 替换Markdown的标题标记
        text = text.replace("### ", "").replace("## ", "").replace("# ", "")
        return text