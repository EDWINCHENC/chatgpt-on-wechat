import datetime
import json
import os
import random
import time

class VirtualPet:
    
    # 将进化路线数据作为类属性
    upgrade_routes = None

    @classmethod
    def load_upgrade_routes(cls):
        if cls.upgrade_routes is None:
            curdir = os.path.dirname(__file__)
            config_path = os.path.join(curdir, "config.json")
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            cls.upgrade_routes = config['routes']
            
    def __init__(self, name, owner, species, birth_date=None, level=1, experience=0, coins=1000):
        # 确保进化路线数据已加载
        VirtualPet.load_upgrade_routes()
        self.name = name
        self.owner = owner
        self.species = species
        self.level = level
        self.experience = experience
        self.coins = coins
        self.birth_date = birth_date if birth_date else datetime.date.today()
        self.max_level = 30
        self.skill_level = level
        self.intelligence = 5 * level
        self.stamina = 10 * level
        self.stats = {
            "hunger": 50,
            "happiness": 50,
            "health": 50,
            "loyalty": 50,
        }
        self.last_interaction_time = 0
        self.interaction_cooldown = 600  # 单位是秒
        self.last_sign_in_date = None  # 用于跟踪上次签到的日期

    @staticmethod
    def get_available_species():
        # 确保进化路线数据已加载
        VirtualPet.load_upgrade_routes()
        next_species_names = {info["name"] for info in VirtualPet.upgrade_routes.values()}
        available_species = [name for name in VirtualPet.upgrade_routes if name not in next_species_names]
        return [{"name": species, "species": species} for species in available_species]

    def gain_experience(self, amount):
        if self.level < self.max_level:
            self.experience += amount
            while self.experience >= self.next_level_exp() and self.level < self.max_level:
                self.experience -= self.next_level_exp()
                self.level_up()

    def level_up(self):
        if self.level < self.max_level:
            self.level += 1
            self.skill_level += 3
            self.intelligence += 5
            self.stamina += 8
            for key in self.stats:
                self.stats[key] += 10
            self.normalize_stats()
            evolution_message = self.update_species()  # 捕获进化信息
            level_up_message = f"{self.name}升级了！现在是 {self.level} 级。"
            # print(f"升级消息：{evolution_message}")  # 打印进化消息
            return level_up_message + (f"\n{evolution_message}" if evolution_message else "")

    def next_level_exp(self):
        return 100 * (1.2 ** (self.level - 1))

    def update_species(self):
        # print(f"检查进化：当前进化阶段 {self.species}, 当前等级 {self.level}")
        if self.species not in self.upgrade_routes:
            return "当前种类没有进化路线。"

        next_species = self.upgrade_routes[self.species]
        evolution_message = ""
        if self.level >= next_species["level"]:
            self.species = next_species["name"]
            evolution_message += f"{self.name}进化成了{self.species}！"

        # 检查是否存在下一个进化阶段
        if self.species in self.upgrade_routes:
            next_level_species = self.upgrade_routes[self.species]
            evolution_message += f" 下一次进化：{next_level_species['name']}, 需要等级 {next_level_species['level']}"
        else:
            evolution_message += " 当前已是最终进化形态。"

        return evolution_message


    # 例如，一个宠物可以通过完成任务来增加金币
    def complete_task(self):
        earned_coins = random.randint(100, 200)  # 生成100到200之间的随机数
        self.coins += earned_coins  # 将随机数加到宠物的金币总数
        return f"{self.name} 完成了任务，获得了 {earned_coins} 金币！"

    # 新增日常签到方法
    def daily_sign_in(self):
        current_date = datetime.date.today()
        if self.last_sign_in_date == current_date:
            return f"{self.name} 今天已经签到过了。"

        # 签到逻辑
        self.gain_experience(10)
        self.stats["loyalty"] += 5
        self.last_sign_in_date = current_date
        return f"📅 {self.name} 已完成签到，获得了 10 点经验值！\n当前状态：{self.status()}"
    
    def feed(self):
        if self.coins >= 50:
            self.stats["hunger"] += 10
            self.stats["happiness"] += 5
            self.stats["loyalty"] += 2
            self.coins -= 50  # 扣除金币
            self.normalize_stats()
        else:
            return "金币不足，无法喂食。"

    def play(self):
        if self.coins >= 50:
            self.stats["happiness"] += 15
            self.stats["hunger"] -= 5
            self.stats["loyalty"] += 2
            self.coins -= 50  # 扣除金币
            self.gain_experience(15)
            self.normalize_stats()
        else:
            return "金币不足，无法玩耍。"

    def checkup(self):
        if self.coins >= 50:
            self.stats["health"] += 10
            self.stats["loyalty"] += 2
            self.coins -= 50  # 扣除金币
            self.normalize_stats()
        else:
            return "金币不足，无法进行体检。"

    def walk(self):
        if self.coins >= 50:
            self.stats["happiness"] += 10
            self.stats["health"] += 5
            self.stats["loyalty"] += 2
            self.coins -= 50  # 扣除金币
            self.gain_experience(10)
            self.normalize_stats()
        else:
            return "金币不足，无法散步。"

    def train(self):
        if self.coins >= 50:
            self.stats["happiness"] -= 5
            self.stats["health"] += 10
            self.coins -= 50  # 扣除金币
            self.gain_experience(15)
            self.stats["loyalty"] += 2
            self.normalize_stats()
        else:
            return "金币不足，无法训练。"

    def bathe(self):
        if self.coins >= 50:
            self.stats["happiness"] -= 10
            self.stats["health"] += 20
            self.stats["loyalty"] += 2
            self.coins -= 50  # 扣除金币
            self.normalize_stats()
        else:
            return "金币不足，无法洗澡。"

    def normalize_stats(self):
        for stat in self.stats:
            self.stats[stat] = min(100, max(0, self.stats[stat]))
        
    def status(self):
        status_str = f"{self.name}的状态："
        for stat, value in self.stats.items():
            status_str += f" {stat} {value},"
        return status_str.rstrip(',')

    def interact_with_user(self, action):
        # 确保动作名称是小写
        action = action.lower()
        previous_stats = self.stats.copy()
        previous_coins = self.coins
        current_time = time.time()
        if current_time - self.last_interaction_time < self.interaction_cooldown:
            return "您刚刚与宠物互动过，请稍后再试。"
        if action in ["喂食", "玩耍", "体检", "散步", "训练", "洗澡"]:
            self.last_interaction_time = current_time

        # 动作名称需要与方法名完全匹配，这里假设方法名是中文
        action_method = {
            "喂食": self.feed,
            "玩耍": self.play,
            "体检": self.checkup,
            "散步": self.walk,
            "训练": self.train,
            "洗澡": self.bathe
        }.get(action, None)

        # 如果找不到对应的方法，返回错误信息
        if not action_method:
            return "❓ 我不明白你想要做什么。"

        # 执行找到的方法
        message = action_method()
        if message:
            return message

        # 根据动作选择表情符号
        activity_emojis = {
            "喂食": "🍴", "玩耍": "🎉", "体检": "🩺",
            "散步": "🚶", "训练": "🏋️", "洗澡": "🛁"
        }
        activity_emoji = activity_emojis.get(action, "❓")

        # 生成详细的活动结果信息
        detailed_result = f"{activity_emoji} {self.name} 完成了{action}！"
        coin_change = self.coins - previous_coins
        for stat, value in self.stats.items():
            change = value - previous_stats[stat]
            if change != 0:
                detailed_result += f" {stat}增加了{change}点，"

        detailed_result = detailed_result.strip("，")  # 移除最后一个逗号
        detailed_result += f" 金币减少了{-coin_change}。"  # 显示金币变化

        # 添加总体状态信息
        detailed_result += f"\n{activity_emoji} 当前状态：{self.status()}"
        return detailed_result



    def random_event(self):
        event = random.choice(["find_food", "get_sick", "nothing", "find_treasure"])
        if event == "find_food":
            self.stats["hunger"] += 20
            self.normalize_stats()
            return f"{self.name}意外发现了食物！"
        elif event == "get_sick":
            self.stats["health"] -= 15
            self.normalize_stats()
            return f"不幸的是，{self.name}生病了。"
        elif event == "find_treasure":
            self.coins += random.randint(10, 50)
            return f"{self.name}发现了一个宝藏，获得了 {random.randint(10, 50)} 金币！"
        else:
            return f"今天是平凡的一天。"
        
    def display_pet_card(self):
        card = f"🐾 宠物名片 🐾\n"
        card += f"🐾 名字：{self.name}\n"
        card += f"👤 主人：{self.owner}\n"
        card += f"🧬 进化阶段：{self.species}\n"
        card += f"🌟 等级：{self.level}\n"
        card += f"⚡ 经验值：{int(self.experience)}/{int(self.next_level_exp())}\n"
        card += f"💰 金币数：{self.coins}\n"
        
        status_names = {
            "hunger": "🍔 饥饿度",
            "happiness": "😊 快乐值",
            "health": "💖 健康值",
            "loyalty": "💕 忠诚度"
        }

        for stat, value in self.stats.items():
            filled_bars = '█' * (value // 10)   # 每10点代表一个填充的条
            empty_bars = '░' * (10 - len(filled_bars))  # 剩余的未填充条
            card += f"{status_names[stat]}：[{filled_bars}{empty_bars}] {value}/100\n"

        # 计算距离下一等级所需的经验
        exp_to_next_level = int(self.next_level_exp()) - int(self.experience)
        card += f"🔜 下一等级还需经验：{exp_to_next_level}\n"

        # 添加下一进化阶段信息
        if self.species in self.upgrade_routes and self.level < self.max_level:
            next_species_info = self.upgrade_routes[self.species]
            card += f"🔄 下一进化阶段：{next_species_info['name']} (等级 {next_species_info['level']})\n"
        else:
            card += "🏆 当前已是最终进化形态。\n"


        return card



# 创建一个 VirtualPet 实例
my_pet = VirtualPet(name="cc", owner="小明", species="滚球兽")

# 打印初始状态
print("初始状态:")
print(my_pet.display_pet_card())

# 给宠物足够的经验进行几次升级
experience_to_gain = 3000
print(f"\n给宠物增加 {experience_to_gain} 点经验.")
my_pet.gain_experience(experience_to_gain)

# 打印升级后的状态
print("\n升级后状态:")
print(my_pet.display_pet_card())



# 测试代码
pet = VirtualPet(name="xiaoxiao", owner="小明", species="滚球兽")

# 尝试与宠物互动
print(pet.interact_with_user("喂食"))
time.sleep(6)  # 等待冷却时间过去
print(pet.interact_with_user("玩耍"))
print(pet.interact_with_user("状态"))
