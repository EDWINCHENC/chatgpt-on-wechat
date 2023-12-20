import plugins
import json
from bridge.context import ContextType
from bridge.reply import Reply, ReplyType
from channel.chat_message import ChatMessage
from config import conf
from plugins import *
from common.log import logger
import os
from .lib.pets_genius import VirtualPet
from .lib.model_factory import ModelGenerator
import random
import datetime


@plugins.register(
    name="cc_vpets",
    desc="A plugin that supports pets play",
    version="0.1.0",
    author="cc",
    desire_priority=36
)
class CCVPETS(Plugin):
    def __init__(self):
        super().__init__()
        self.handlers[Event.ON_HANDLE_CONTEXT] = self.on_handle_context
        curdir = os.path.dirname(__file__)
        config_path = os.path.join(curdir, "config.json")
        logger.info(f"[cc_vpets] current directory: {curdir}")
        logger.info(f"加载配置文件: {config_path}")
        if not os.path.exists(config_path):
            logger.info('[RP] 配置文件不存在，将使用config.json.template模板')
            config_path = os.path.join(curdir, "config.json.template")
            logger.info(f"[cc_vpets] config template path: {config_path}")
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
                logger.info(f"[cc_vpets] 配置内容: {config}")
                self.c_model = ModelGenerator()
                self.user_pets = {}  # 用于存储用户的宠物
                logger.info("[cc_vpets] inited")
        except Exception as e:
            if isinstance(e, FileNotFoundError):
                logger.warn(f"[cc_vpets] init failed, config.json not found.")
            else:
                logger.warn("[cc_vpets] init failed." + str(e))
            raise e

    def on_handle_context(self, e_context: EventContext):
        context = e_context['context']
        msg: ChatMessage = context['msg']
        # user_id = msg.from_user_id
        isgroup = e_context["context"].get("isgroup")
        user_id = msg.actual_user_id if isgroup else msg.from_user_id
        nickname = msg.actual_user_nickname  # 获取nickname
        pet = self.user_pets.get(user_id)
        pet_interaction_commands = ["喂食", "玩耍", "体检", "散步", "训练", "洗澡", "状态"]
        # 过滤不需要处理的内容类型
        if context.type != ContextType.TEXT:
            return

        content = context.content.strip()
        if "宠物领养" in content:
            response = self.adopt_pet(user_id, nickname)  # 直接调用领养方法，不需提供宠物名
            logger.info(f"[cc_vpets] {user_id} {nickname} 领养了宠物")
            _set_reply_text(response, e_context, level=ReplyType.TEXT)
            return

        elif "宠物命名" in content:
            pet_name = content.split("宠物命名")[1].strip()
            if pet_name:
                response = self.name_pet(user_id, pet_name)
                logger.info(f"[cc_vpets] {user_id} {nickname} 命名了宠物")
            else:
                response = "请提供一个宠物的名字。"
            _set_reply_text(response, e_context, level=ReplyType.TEXT)
            return


        # 处理其他宠物互动命令
        elif content in pet_interaction_commands:
            if user_id in self.user_pets:
                response = pet.interact_with_user(content)
                prompt = f"""你是一只数码宝贝，是由{nickname}领养的，他将在今后陪伴你，你的主人会和你进行一系列的互动（例如"喂食", "玩耍", "体检", "散步", "训练", "洗澡"）等等，你要以数码宝贝的身份和他用简短的语言（50字以内）进行交流，使主人感受到你的陪伴。"""
                user_input = content
                # 调用OpenAI处理函数
                model_response = self.c_model._generate_model_analysis(prompt, user_input)
                self.save_pets_to_json(self.user_pets)  # 保存宠物状态
            else:
                response = "你还没有领养宠物。输入 '领养宠物 [宠物名]' 来领养一个宠物。"
            final_response = (
                f"🌟 {response}\n"
                f"{model_response}"
            )
            _set_reply_text(final_response, e_context, level=ReplyType.TEXT)
            return

    def adopt_pet(self, user_id, nickname):
        if user_id not in self.user_pets:
            try:
                available_species = VirtualPet.get_available_species()
                random_species = random.choice(available_species)
                species = random_species["species"]
                logger.info(f"{nickname}领养了{random_species['species']}")
                # 初始时不设置宠物名字
                self.user_pets[user_id] = VirtualPet(name=None, owner=nickname, species=species)
                self.save_pets_to_json(self.user_pets)  # 保存宠物状态
                logger.debug(f"数据已存储")
                return f"恭喜你领养到了数码宝贝，它是一只{species}！你可以随时为它取一个名字。"
            except Exception as e:
                logger.error(f"领养宠物时出错: {str(e)}")
                return "抱歉，领养过程中出现了一些问题，请稍后再试。"
        else:
            pet = self.user_pets[user_id]
            return f"你已经有一只数码宝贝了，它是一只{pet.species}。"

    def name_pet(self, user_id, pet_name):
        if user_id in self.user_pets:
            pet = self.user_pets[user_id]
            pet.name = pet_name
            self.save_pets_to_json(self.user_pets)  # 保存新名字
            return f"你的宠物名字为 {pet_name}。"
        else:
            return "你还没有宠物。输入 '领养宠物' 来领养一只数码宝贝。"

        
    # 在外部类或函数中
    def save_pets_to_json(self, user_pets, filename="pets.json"):
        # 使用 to_json 方法转换所有 VirtualPet 实例
        pets_data = {user_id: pet.to_json() for user_id, pet in user_pets.items()}
        with open(filename, "w") as file:
            json.dump(pets_data, file, indent=4)

    # 在外部类或函数中
    def load_pets_from_json(self, filename="pets.json"):
        if not os.path.exists(filename) or os.path.getsize(filename) == 0:
            return {}  # 如果文件不存在或为空，则返回空字典

        with open(filename, "r") as file:
            pets_data = json.load(file)
            # 转换日期字符串回 date 对象
            for user_id, data in pets_data.items():
                if data['birth_date'] is not None:
                    data['birth_date'] = datetime.fromisoformat(data['birth_date']).date()
                if data.get('last_sign_in_date') is not None:  # 使用 get 方法以防这个键不存在
                    data['last_sign_in_date'] = datetime.fromisoformat(data['last_sign_in_date']).date()
            return {user_id: VirtualPet(**data) for user_id, data in pets_data.items()}


def _send_info(e_context: EventContext, content: str):
    reply = Reply(ReplyType.TEXT, content)
    channel = e_context["channel"]
    channel.send(reply, e_context["context"])


def _set_reply_text(content: str, e_context: EventContext, level: ReplyType = ReplyType.ERROR):
    reply = Reply(level, content)
    e_context["reply"] = reply
    e_context.action = EventAction.BREAK_PASS
