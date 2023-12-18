import plugins
import json
from bridge.context import ContextType
from bridge.reply import Reply, ReplyType
from channel.chat_message import ChatMessage
from config import conf
from plugins import *
from common.log import logger
import os
from .lib.pets_genuis import VirtualPet, interact_with_pet


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
                # self.c_model = ModelGenerator()
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
        # 过滤不需要处理的内容类型
        if context.type != ContextType.TEXT:
            return

        content = context.content.strip()
        if "领养宠物" in content:
            pet_name = content.split("领养宠物")[1].strip()
            if pet_name:
                response = self.adopt_pet(user_id, pet_name)
            else:
                response = "请提供一个宠物的名字。"
            logger.info(f"[cc_vpets] {user_id} adopt pet {pet_name}")
            _set_reply_text(response, e_context, level=ReplyType.TEXT)
            return

            # 处理其他宠物互动命令
        elif pet and content in ["喂食", "玩耍", "体检", "散步", "训练", "洗澡", "状态"]:
            response = interact_with_pet(pet, content)
            self.save_pets_to_json(self.user_pets)  # 保存宠物状态
            _set_reply_text(response, e_context, level=ReplyType.TEXT)
            return
        elif not pet:
            response = "你还没有领养宠物。输入 '领养宠物 [宠物名]' 来领养一个宠物。"
            _set_reply_text(response, e_context, level=ReplyType.TEXT)
            return
        else:
            response = "我不明白你想要做什么。"
            _set_reply_text(response, e_context, level=ReplyType.TEXT)
            return

    def adopt_pet(self, user_id, pet_name):
        if user_id not in self.user_pets:
            self.user_pets[user_id] = VirtualPet(pet_name)
            self.save_pets_to_json(self.user_pets)  # 保存宠物状态
            return f"恭喜你领养了宠物 {pet_name}!"
        else:
            return f"您已经有一个宠物了，它的名字是 {self.user_pets[user_id].name}。"

    def save_pets_to_json(self,user_pets, filename="pets.json"):
        pets_data = {}
        for user_id, pet in user_pets.items():
            pets_data[user_id] = {
                "name": pet.name,
                "hunger": pet.hunger,
                "happiness": pet.happiness,
                "health": pet.health,
                "level": pet.level,
                "experience": pet.experience
            }
        with open(filename, "w") as file:
            json.dump(pets_data, file, indent=4)

    def load_pets_from_json(self, filename="pets.json"):
        if not os.path.exists(filename) or os.path.getsize(filename) == 0:
            return {}  # 如果文件不存在或为空，则返回空字典

        with open(filename, "r") as file:
            pets_data = json.load(file)
            return {user_id: VirtualPet(**data) for user_id, data in pets_data.items()}



def _send_info(e_context: EventContext, content: str):
    reply = Reply(ReplyType.TEXT, content)
    channel = e_context["channel"]
    channel.send(reply, e_context["context"])


def _set_reply_text(content: str, e_context: EventContext, level: ReplyType = ReplyType.ERROR):
    reply = Reply(level, content)
    e_context["reply"] = reply
    e_context.action = EventAction.BREAK_PASS
