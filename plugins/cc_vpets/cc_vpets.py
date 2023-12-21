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
import time


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
                # 加载宠物数据
                self.user_pets = self.load_pets_from_json()
                logger.debug(f"[cc_vpets] 初始化加载宠物数据: {self.user_pets}")
                self.last_decay_time = time.time()
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
        user_id = msg.actual_user_nickname if isgroup else msg.from_user_nickname
        logger.debug(f"获取到的user_id: {user_id}")
        nickname = msg.actual_user_nickname if isgroup else msg.from_user_nickname # 获取nickname
        pet = self.user_pets.get(user_id)
        logger.debug(f"获取到的实例化数据加载: |||||{pet}|||||")
        pet_interaction_commands = ["喂食", "玩耍", "体检", "散步", "训练", "洗澡", "状态"]
        # 过滤不需要处理的内容类型
        if context.type != ContextType.TEXT:
            return

       # 在处理用户请求之前调用状态衰减方法
        self.decay_pets_stats_if_needed()
        content = context.content.strip()
        if "宠物领养" in content:
            response = self.adopt_pet(user_id, nickname)  # 直接调用领养方法，不需提供宠物名
            logger.info(f"[cc_vpets] {user_id} {nickname} 领养了宠物")
            _send_info(e_context, response)

            # 确保 user_id 在 self.user_pets 中，并且 pet 实例不是 None
            if user_id in self.user_pets and self.user_pets[user_id] is not None:
                pet = self.user_pets[user_id]
                logger.debug(f"[cc_vpets] {nickname} 领养了宠物 {pet.species}")
                prompt = f"""你是一只数码宝贝(就是东映公司旗下动画工作室制作的电视动画片《数码宝贝》的原型)，你是数码宝贝{pet.species}，你每次都会向主人介绍{pet.species}是什么，会怎么样进化等。你要以数码宝贝的身份和主人相处，使他感受到你的陪伴，和他成为真正的朋友。"""
                user_input = f"你是数码宝贝{pet.species}，你现在是由{nickname}领养的，他将在今后陪伴你，会和你进行一系列的互动（例如'喂食', '玩耍', '体检', '散步', '训练', '洗澡'）等等，现在以{pet.species}的角色向主人打招呼，简单介绍你自己，并且欢迎主人{nickname}来到数码宝贝的世界！字数在50字以内。"
                model_response = self.c_model._generate_model_analysis(prompt, user_input)
                _set_reply_text(f"{pet.species}: {model_response}\n\n💡 提示：试试'宠物命名[名字]'，或输入 '宠物状态' 随时查看我的最新状态！", e_context, level=ReplyType.TEXT)
                return

        elif "宠物命名" in content:
            if user_id in self.user_pets and self.user_pets[user_id] is not None:
                pet_name = content.split("宠物命名")[1].strip()
                if pet_name:
                    response = self.name_pet(user_id, pet_name)
                    logger.info(f"[cc_vpets] {user_id} {nickname} 命名了宠物")
                    self.save_pets_to_json(self.user_pets)  # 保存宠物状态
                else:
                    response = "请提供一个宠物的名字。"
                _set_reply_text(response, e_context, level=ReplyType.TEXT)
                return
            else:
                _set_reply_text("你还没有领养宠物。输入 '宠物领养' 来领养一只数码宝贝。", e_context, level=ReplyType.TEXT)
                return

        # 处理宠物状态查看命令
        elif content == "宠物状态":
            if user_id in self.user_pets and self.user_pets[user_id] is not None:
                pet = self.user_pets[user_id]
                response = pet.status(nickname)
                logger.debug(f"[cc_vpets]{nickname} 查看了宠物状态:{response}")
                _set_reply_text(response, e_context, level=ReplyType.TEXT)
            else:
                _set_reply_text("你还没有领养宠物。", e_context, level=ReplyType.TEXT)
            return

        # 处理其他宠物互动命令
        elif content in pet_interaction_commands:
            model_response = ""
            pet = self.user_pets.get(user_id)  # 使用 .get() 来避免 KeyError
            logger.debug(f"{user_id}宠物实例化数据加载：{pet}")
            if pet is not None:  # 确保宠物已经被领养
                response = pet.interact_with_user(content)
                logger.debug(f"[cc_vpets]{nickname} 进行了互动:{response}")
                prompt = f"""你是一只数码宝贝(就是东映公司旗下动画工作室制作的电视动画片《数码宝贝》的原型)，你现在是由{nickname}领养的，他将在今后陪伴你，会和你进行一系列的互动（例如"喂食", "玩耍", "体检", "散步", "训练", "洗澡"）等等，你需要以数码宝贝{pet.species}的身份和他用简短的语言（50字以内）进行交流，使他感受到你的陪伴。"""
                user_input = content
                # 调用OpenAI处理函数
                model_response = self.c_model._generate_model_analysis(prompt, user_input)
                self.save_pets_to_json(self.user_pets)  # 保存宠物状态
                final_response = (
                    f"{pet.species}: {model_response}"
                    f"\n\n🌟 {response}"
                )
            else:
                response = "你还没有领养宠物。输入 '宠物领养' 来领养一只数码宝贝。"
                final_response = response  # 不包含 pet.species

            _set_reply_text(final_response, e_context, level=ReplyType.TEXT)
            return

        elif "宠物签到" in content:
            if user_id in self.user_pets and self.user_pets[user_id] is not None:
                pet = self.user_pets[user_id]
                response = pet.daily_sign_in(nickname)
                logger.debug(f"[cc_vpets]{nickname} 进行了签到:{response}")
                self.save_pets_to_json(self.user_pets)  # 保存宠物状态
                _set_reply_text(response, e_context, level=ReplyType.TEXT)
            else:
                _set_reply_text("你还没有领养宠物。", e_context, level=ReplyType.TEXT)
            return

        elif "我的宠物" in content:
            if user_id in self.user_pets:
                pet = self.user_pets[user_id]
                response = pet.display_pet_card()
                _set_reply_text(response, e_context, level=ReplyType.TEXT)
            else:
                _set_reply_text("你还没有领养宠物。", e_context, level=ReplyType.TEXT)
            return

    def decay_pets_stats(self):
        """遍历所有宠物并更新其状态。"""
        for pet in self.user_pets.values():
            pet.decay_stats_over_time()
            
    def decay_pets_stats_if_needed(self):
        """检查是否需要更新宠物的状态。"""
        current_time = time.time()
        # 检查是否已过足够的时间（例如半小时）
        if current_time - self.last_decay_time >= 1800:  # 半小时 = 1800秒
            self.decay_pets_stats()
            self.last_decay_time = current_time

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
                # 调用 display_pet_card 方法并获取宠物信息卡片
                pet = self.user_pets[user_id]  # 获取新创建的宠物实例
                pet_card = pet.display_pet_card()  # 从宠物实例调用 display_pet_card 方法
                logger.debug(f"数据已获取:{pet_card}")
                adopt_message = f"恭喜你领养到了数码宝贝，它是一只{species}！\n\n{pet_card}"
                # 添加查看宠物信息的提示
                adopt_message += "\n\n💡 提示：输入 '我的宠物' 随时查看最新卡片。"                
                return adopt_message
            except Exception as e:
                logger.error(f"领养宠物时出错: {str(e)}")
                return "抱歉，领养过程中出现了一些问题，请稍后再试。"
        else:
            pet = self.user_pets[user_id]
            return f"你已经有一只数码宝贝了，它是一只{pet.species}。"

    def name_pet(self, user_id, pet_name):
        if user_id not in self.user_pets:
            return "你还没有领养宠物。请先通过'宠物领养'领养一只数码宝贝。"
        elif not pet_name:
            return "请提供一个宠物的名字。"
        else:
            pet = self.user_pets[user_id]
            pet.name = pet_name
            self.save_pets_to_json(self.user_pets)  # 保存新名字
            return f"你的宠物{pet.species}的名字现在是--{pet_name}--。"

    # 在外部类或函数中
    def save_pets_to_json(self, user_pets, filename="pets.json"):
        # 获取当前文件的目录
        curdir = os.path.dirname(__file__)
        # 构造完整的文件路径
        filepath = os.path.join(curdir, filename)
        # 使用 to_json 方法转换所有 VirtualPet 实例
        pets_data = {user_id: pet.to_json() for user_id, pet in user_pets.items()}
        logger.info(f"保存宠物数据到 {filepath}")
        with open(filepath, "w", encoding='utf-8') as file:
            json.dump(pets_data, file, indent=4, ensure_ascii=False)

    def load_pets_from_json(self, filename="pets.json"):
        # 获取当前文件的目录
        curdir = os.path.dirname(__file__)
        # 构造完整的文件路径
        filepath = os.path.join(curdir, filename)
        logger.debug(f"读取宠物数据 {filepath}")
        try:
            with open(filepath, 'r',encoding='utf-8') as file:
                pets_data = json.load(file)

            pets = {}
            for user_id, data in pets_data.items():
                # 处理日期格式
                birth_date = datetime.date.fromisoformat(data['birth_date']) if data['birth_date'] else None
                last_sign_in_date = datetime.date.fromisoformat(data['last_sign_in_date']) if data.get('last_sign_in_date') else None
                
                # 创建 VirtualPet 实例
                pet = VirtualPet(
                    name=data['name'],
                    owner=data['owner'],
                    species=data['species'],
                    birth_date=birth_date,
                    level=data['level'],
                    experience=data['experience'],
                    coins=data['coins'],
                    last_sign_in_date=last_sign_in_date  # 添加这一行
                )
                
                # 设置额外的属性
                pet.max_level = data.get('max_level', pet.max_level)
                pet.skill_level = data.get('skill_level', pet.skill_level)
                pet.intelligence = data.get('intelligence', pet.intelligence)
                pet.stamina = data.get('stamina', pet.stamina)
                pet.stats = data.get('stats', pet.stats)
                pet.last_interaction_time = datetime.datetime.fromisoformat(data['last_interaction_time']).timestamp() if data.get('last_interaction_time') else pet.last_interaction_time
                pet.interaction_window_start = datetime.datetime.fromisoformat(data['interaction_window_start']).timestamp() if data.get('interaction_window_start') else pet.interaction_window_start
                
                pets[user_id] = pet

            return pets
        except FileNotFoundError:
            logger.error(f"File not found: {filepath}")
            return {}
        except json.JSONDecodeError:
            logger.error(f"Error decoding JSON from file: {filepath}")
            return {}
        except Exception as e:
            logger.error(f"An error occurred: {e}")
            return {}



def _send_info(e_context: EventContext, content: str):
    reply = Reply(ReplyType.TEXT, content)
    channel = e_context["channel"]
    channel.send(reply, e_context["context"])


def _set_reply_text(content: str, e_context: EventContext, level: ReplyType = ReplyType.ERROR):
    reply = Reply(level, content)
    e_context["reply"] = reply
    e_context.action = EventAction.BREAK_PASS
