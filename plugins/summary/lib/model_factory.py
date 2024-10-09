import os
import json
from common.log import logger
from openai import OpenAI

class ModelGenerator:
    def __init__(self):

        self.openai_api_key = "sk-Ov9dJQYqVPDhTE5eBb015cDa7dEb442195Ca857dEe1e762f"
        self.openai_api_base = "https://newapi.ilfei.cc/v1"

        logger.debug(f"[ModelGenerator] openai_api_key: {self.openai_api_key}")
        self.openai_model = "doubao-pro-32k"
        logger.debug(f"[ModelGenerator] openai_model: {self.openai_model}")

        # 初始化OpenAI客户端
        self.openai_client = OpenAI(api_key=self.openai_api_key, base_url=self.openai_api_base)


    def _generate_model_analysis(self, prompt, combined_content):
        messages = self._build_openai_messages(prompt, combined_content)
        return self._generate_summary_with_openai(messages)

    def _build_openai_messages(self, prompt, user_input):
        return [
            {"role": "system", "content": prompt},
            {"role": "user", "content": user_input}
        ]

    def _generate_summary_with_openai(self, messages):
        """使用 OpenAI ChatGPT 生成总结"""
        try:
            logger.debug(f"向 OpenAI 发送消息: {messages}")

            # 调用 OpenAI ChatGPT
            response = self.openai_client.chat.completions.create(
                model=self.openai_model,
                messages=messages
            )
            logger.debug(f"来自 OpenAI 的回复: {response}")
            reply_text = response.choices[0].message.content
            return f"{reply_text}[O]"
        except Exception as e:
            logger.error(f"Error generating summary with OpenAI: {e}")
            return "有些累了，请稍后再试。"

    def remove_markdown(self, text):
        # 替换Markdown的粗体标记
        text = text.replace("**", "")
        # 替换Markdown的标题标记
        text = text.replace("### ", "").replace("## ", "").replace("# ", "")
        return text
