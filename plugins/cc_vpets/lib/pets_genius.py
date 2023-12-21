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
        self.interaction_count = 0
        self.interaction_window_start = time.time()  # 设置交互窗口的开始时间
        self.last_sign_in_date = None  # 用于跟踪上次签到的日期
        self.last_interaction_time = time.time()


    def to_json(self):
        # 创建一个代表宠物状态的字典
        return {
            "name": self.name,
            "owner": self.owner,
            "species": self.species,
            "birth_date": self.birth_date.isoformat() if self.birth_date else None,
            "level": self.level,
            "experience": self.experience,
            "coins": self.coins,
            "max_level": self.max_level,
            "skill_level": self.skill_level,
            "intelligence": self.intelligence,
            "stamina": self.stamina,
            "stats": self.stats,
            "last_interaction_time": datetime.datetime.fromtimestamp(self.last_interaction_time).isoformat() if self.last_interaction_time else None,
            "last_sign_in_date": self.last_sign_in_date.isoformat() if self.last_sign_in_date else None,
            "interaction_window_start": datetime.datetime.fromtimestamp(self.interaction_window_start).isoformat() if self.interaction_window_start else None,
        }

    
    # 类属性，用于映射状态名称到中文
    status_names = {
        "hunger": "🍔 饱食度",
        "happiness": "😊 快乐值",
        "health": "💖 健康值",
        "loyalty": "💕 忠诚度"
    }
    status_names2 = {
        "hunger": "饱食度",
        "happiness": "快乐值",
        "health": "健康值",
        "loyalty": "忠诚度"
    }    

    def decay_stats_over_time(self):
        # 每小时减少的状态值
        decay_amount = {
            "hunger": -5,  # 每小时饥饿度减少5点
            "happiness": -4,  # 每小时快乐值减少4点
            "health": -3,  # 每小时健康值减少2点
            "loyalty": -3
        }

        for stat, decay in decay_amount.items():
            self.stats[stat] = max(0, self.stats[stat] + decay)  # 确保状态值不会小于0

        self.normalize_stats()  # 规范化状态值

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
            level_up_messages = []  # 存储升级消息
            while self.experience >= self.next_level_exp() and self.level < self.max_level:
                self.experience -= self.next_level_exp()
                level_up_message = self.level_up()
                level_up_messages.append(level_up_message)
                # print(f"等级提升后的消息: {level_up_message}")  # 打印消息

            # 返回一个包含所有升级消息的字符串
            return '\n'.join(level_up_messages) if level_up_messages else f"当前经验值：{self.experience}, 等级：{self.level}"
        else:
            return "已达到最大等级。"

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
            # print(f"进化信息: {evolution_message}")  # 打印进化信息

            # 构建升级消息，包括各项属性的增加
            level_up_message = f"🎉 {self.species}{self.name} 升级了！现在是 {self.level} 级。\n"
            level_up_message += f"🔧 技能等级增加了 3 点。\n"
            level_up_message += f"🧠 智力增加了 5 点。\n"
            level_up_message += f"💪 耐力增加了 8 点。\n"
            for stat in self.stats:
                level_up_message += f"{self.status_names[stat]} 增加了 10 点。\n"
            
            level_up_message += evolution_message if evolution_message else ""
            # 添加查看宠物信息的提示
            level_up_message += "\n💡 提示：输入 '我的宠物' 查看最新宠物信息。"

            return level_up_message

    def next_level_exp(self):
        return 100 * (1.2 ** (self.level - 1))

    def update_species(self):
        # print(f"检查进化：当前进化阶段 {self.species}, 当前等级 {self.level}")
        if self.species not in self.upgrade_routes:
            return "当前种类没有进化路线。"

        next_species = self.upgrade_routes[self.species]
        evolution_message = ""
        if self.level >= next_species["level"]:
            # 保存原始种类名称
            original_species = self.species
            # 更新种类
            self.species = next_species["name"]
            # 构建进化消息
            evolution_message += f"\n✨🌟✨{self.name}从--{original_species}--进化成了【{self.species}】!!✨🌟✨"

        # 检查是否存在下一个进化阶段
        if self.species in self.upgrade_routes:
            next_level_species = self.upgrade_routes[self.species]
            evolution_message += f"\n🌟下一次进化：{next_level_species['name']}, 需要等级 {next_level_species['level']}"
        else:
            evolution_message += " 当前已是最终进化形态。"

        return evolution_message


    # 例如，一个宠物可以通过完成任务来增加金币
    def complete_task(self):
        earned_coins = random.randint(100, 200)  # 生成100到200之间的随机数
        self.coins += earned_coins  # 将随机数加到宠物的金币总数
        return f"{self.species}{self.name} 完成了任务，获得了 {earned_coins} 金币！"

    # 新增日常签到方法
    def daily_sign_in(self,nickname):
        current_date = datetime.date.today()
        if self.last_sign_in_date == current_date:
            return f"{self.species}{self.name} 今天已经签到过了。"

        # 签到逻辑
        level_up_message = self.gain_experience(20)  # 获得经验和处理升级
        self.stats["loyalty"] += 5
        self.coins += 100  # 增加100金币
        self.last_sign_in_date = current_date

        # 计算距离下一等级所需的经验
        exp_to_next_level = int(self.next_level_exp()) - int(self.experience)

        sign_in_message = f"📅 {self.species}{self.name} 已完成签到，🆙获得了⚡ 20 点经验值和💰 100 金币！"
        if level_up_message:  # 如果有升级消息，添加到签到消息中
            sign_in_message += f"\n✅ {level_up_message}"
        else:
            sign_in_message += f" 还需 {exp_to_next_level} 点经验升级到下一级。"

        sign_in_message += f"\n\n🔵 {self.status(nickname)}"
        return sign_in_message


    
    def feed(self):
        changes = {}
        if self.coins >= 50:
            changes["hunger"] = 10
            changes["happiness"] = 5
            changes["loyalty"] = 2
            self.coins -= 50
            changes["coins"] = -50  # 金币减少

            # 更新状态
            self.stats["hunger"] += changes["hunger"]
            self.stats["happiness"] += changes["happiness"]
            self.stats["loyalty"] += changes["loyalty"]
            self.normalize_stats()

            # 假设喂食获得一定经验值
            gained_exp = 2  # 例如，喂食获得2点经验
            level_up_message = self.gain_experience(gained_exp)
            changes["exp"] = gained_exp
            changes["level_up_message"] = level_up_message  # 存储升级消息

            return changes
        else:
            return "金币不足，无法喂食。"


    def play(self):
        changes = {}
        if self.coins >= 50:
            # 状态变化
            changes["happiness"] = 15  # 快乐值增加
            changes["hunger"] = -5     # 饱食度减少
            changes["loyalty"] = 2     # 忠诚度增加

            # 金币和经验值变化
            self.coins -= 50  # 扣除金币
            gained_exp = 15   # 获得经验值
            level_up_message = self.gain_experience(gained_exp)  # 处理经验值增加和升级

            changes["coins"] = -50    # 金币变化
            changes["exp"] = gained_exp  # 经验值变化
            changes["level_up_message"] = level_up_message  # 存储升级消息

            # 更新状态
            self.stats["happiness"] += changes["happiness"]
            self.stats["hunger"] += changes["hunger"]
            self.stats["loyalty"] += changes["loyalty"]
            self.normalize_stats()

            return changes
        else:
            return "金币不足，无法玩耍。"


    def checkup(self):
        changes = {}
        if self.coins >= 50:
            # 状态变化
            changes["health"] = 20   # 健康值增加
            changes["loyalty"] = 2   # 忠诚度增加

            # 金币和经验值变化
            self.coins -= 50  # 扣除金币
            gained_exp = 5   # 假设体检获得5点经验值
            level_up_message = self.gain_experience(gained_exp)  # 处理经验值增加和升级

            changes["coins"] = -50    # 金币变化
            changes["exp"] = gained_exp  # 经验值变化
            changes["level_up_message"] = level_up_message  # 存储升级消息

            # 更新状态
            self.stats["health"] += changes["health"]
            self.stats["loyalty"] += changes["loyalty"]
            self.normalize_stats()

            return changes
        else:
            return "金币不足，无法进行体检。"

    def walk(self):
        changes = {}
        if self.coins >= 50:
            # 状态变化
            changes["happiness"] = 10  # 快乐值增加
            changes["health"] = 5      # 健康值增加
            changes["loyalty"] = 2     # 忠诚度增加
            changes["hunger"] = -5     # 饱食度减少

            # 金币和经验值变化
            self.coins -= 50  # 扣除金币
            gained_exp = 10   # 获得经验值
            level_up_message = self.gain_experience(gained_exp)  # 处理经验值增加和升级

            changes["coins"] = -50    # 金币变化
            changes["exp"] = gained_exp  # 经验值变化
            changes["level_up_message"] = level_up_message  # 存储升级消息

            # 更新状态
            self.stats["happiness"] += changes["happiness"]
            self.stats["health"] += changes["health"]
            self.stats["loyalty"] += changes["loyalty"]
            self.stats["hunger"] += changes["hunger"]
            self.normalize_stats()

            return changes
        else:
            return "金币不足，无法散步。"

    def train(self):
        changes = {}
        if self.coins >= 50:
            # 状态变化
            changes["happiness"] = -5  # 快乐值减少
            changes["health"] = 20    # 健康值增加
            changes["loyalty"] = 2    # 忠诚度增加
            changes["hunger"] = -5    # 饱食度减少

            # 金币和经验值变化
            self.coins -= 50  # 扣除金币
            gained_exp = 20   # 获得经验值
            level_up_message = self.gain_experience(gained_exp)  # 处理经验值增加和升级

            changes["coins"] = -50    # 金币变化
            changes["exp"] = gained_exp  # 经验值变化
            changes["level_up_message"] = level_up_message  # 存储升级消息

            # 更新状态
            self.stats["happiness"] += changes["happiness"]
            self.stats["health"] += changes["health"]
            self.stats["loyalty"] += changes["loyalty"]
            self.stats["hunger"] += changes["hunger"]
            self.normalize_stats()

            return changes
        else:
            return "金币不足，无法训练。"

    def bathe(self):
        changes = {}
        if self.coins >= 50:
            # 状态变化
            changes["happiness"] = 10 # 快乐值增加
            changes["health"] = 10     # 健康值增加
            changes["loyalty"] = 2     # 忠诚度增加
            changes["hunger"] = -5     # 饱食度减少

            # 金币和经验值变化
            self.coins -= 50  # 扣除金币
            gained_exp = 5   # 假设洗澡获得5点经验值
            level_up_message = self.gain_experience(gained_exp)  # 处理经验值增加和升级

            changes["coins"] = -50    # 金币变化
            changes["exp"] = gained_exp  # 经验值变化
            changes["level_up_message"] = level_up_message  # 存储升级消息

            # 更新状态
            self.stats["happiness"] += changes["happiness"]
            self.stats["health"] += changes["health"]
            self.stats["loyalty"] += changes["loyalty"]
            self.stats["hunger"] += changes["hunger"]
            self.normalize_stats()

            return changes
        else:
            return "金币不足，无法洗澡。"


    def normalize_stats(self):
        for stat in self.stats:
            self.stats[stat] = min(100, max(0, self.stats[stat]))


    def status(self, nickname):
        status_str =  f"{nickname}的{self.species}🐾 | 宠物状态 | 🐾\n\n"
        for stat, value in self.stats.items():
            filled_bars = '█' * (value // 10)   # 每10点代表一个填充的条
            empty_bars = '░' * (10 - len(filled_bars))  # 剩余的未填充条
            status_str += f"{VirtualPet.status_names[stat]}：[{filled_bars}{empty_bars}] {value}/100\n"

            # 根据状态值给出提示
            if value < 50:
                status_str += f"⚠️ 哎呀：{VirtualPet.status_names2[stat]}有些低，请及时关注！\n"
            elif value > 80:
                status_str += f"👍 {VirtualPet.status_names2[stat]}状态很好，战斗力很强！\n"

        # 添加一般提示信息
        status_str += "\n💡 提示：你可以通过['喂食', '玩耍', '体检', '散步', '训练', '洗澡']等指令，来保持数码宝贝处于健康的成长状态哦。"

        # 随机事件触发
        if random.random() < 0.22:  # 假设有20%的概率触发随机事件
            random_event_result = self.random_event()
            status_str += f"\n\n🎁 触发随机事件：{random_event_result}"

        return status_str


    def format_status_changes(self, changes):
        status_str = ""
        for stat, change in changes.items():
            # 跳过金币和经验值的变化
            if stat not in ["coins", "exp","level_up_message"]:
                current_value = self.stats[stat]
                sign = "+" if change >= 0 else ""
                status_str += f"   {VirtualPet.status_names[stat]}: {current_value} ({sign}{change})\n"
        return status_str




    def interact_with_user(self, action):
        # 确保动作名称是小写
        action = action.lower()
        current_time = time.time()
        # 检查是否进入新的15分钟窗口
        if current_time - self.interaction_window_start > 900:  # 15分钟 = 900秒
            self.interaction_count = 0  # 重置计数器
            self.interaction_window_start = current_time  # 更新窗口开始时间

        # 检查交互次数是否已达上限
        if self.interaction_count >= 3:
            next_interaction_time = self.interaction_window_start + 900  # 下一个互动窗口的开始时间
            wait_time = int(next_interaction_time - current_time)  # 等待时间
            return f"您已经和宠物多次互动。请在 {wait_time // 60} 分钟 {wait_time % 60} 秒后再来找它吧。"
        
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

        # 根据动作选择表情符号
        activity_emojis = {
            "喂食": "🍴", "玩耍": "🎉", "体检": "🩺",
            "散步": "🚶", "训练": "🏋️", "洗澡": "🛁"
        }
        activity_emoji = activity_emojis.get(action, "❓")

        # 执行找到的方法并获取反馈
        action_feedback = action_method()
        if isinstance(action_feedback, dict):  # 检查是否返回了状态变化字典
            status_changes = self.format_status_changes(action_feedback)
            coins_change = action_feedback.get("coins", 0)
            exp_change = action_feedback.get("exp", 0)
            level_up_message = action_feedback.get("level_up_message", "")
            
            # 获取当前金币余额
            current_coins = self.coins
            # 计算距离下一等级所需的经验
            exp_to_next_level = int(self.next_level_exp()) - int(self.experience)

            detailed_result = f"{self.species}{self.name}状态更新：\n{status_changes}"
            detailed_result += f"\n💰 金币变化: {coins_change},  剩余金币: {current_coins}\n"

            if exp_change > 0:
                detailed_result += f"⚡ 获得了{exp_change}点经验值！下一次升级还需经验：{exp_to_next_level}"

            # 在这里添加进化检查
            if level_up_message:
                detailed_result += f"\n\n🔧 {level_up_message}"
            
            # 在这里添加随机事件的概率性触发
            if random.random() < 0.15:  # 20%的概率触发随机事件
                random_event_result = self.random_event()
                detailed_result += f"\n\n🎁 出现随机事件：{random_event_result}"

            
        elif isinstance(action_feedback, str):  # 检查是否返回了字符串（如金币不足）
            return f"{activity_emoji} {self.species}{self.name} {action}失败。原因：{action_feedback}"

        # 有效的交互，增加计数器
        self.interaction_count += 1
        self.last_interaction_time = current_time
        return detailed_result

    def random_event(self):
        event = random.choice(["find_food", "get_sick", "nothing", "find_treasure", "meet_friend", "lose_coins", "find_toy"])
        if event == "find_food":
            self.stats["hunger"] += 10
            self.normalize_stats()
            return f"{self.species}{self.name}意外发现了食物！增加了10点饱食度。"
        elif event == "get_sick":
            self.stats["health"] -= 15
            self.normalize_stats()
            return f"{self.species}{self.name}生病了。健康值减少了15点。"
        elif event == "find_treasure":
            self.coins += random.randint(10, 50)
            return f"{self.species}{self.name}发现了一个宝藏，获得了 {random.randint(10, 50)} 金币！"
        elif event == "meet_friend":
            self.stats["happiness"] += 15
            self.normalize_stats()
            return f"{self.species}{self.name}在外出时遇到了朋友！快乐值增加了15点。"
        elif event == "lose_coins":
            lost_coins = random.randint(5, 30)
            self.coins = max(0, self.coins - lost_coins)  # 防止金币变成负数
            return f"{self.species}{self.name}不小心丢失了 {lost_coins} 金币。"
        elif event == "find_toy":
            self.stats["happiness"] += 10
            self.stats["loyalty"] += 5
            self.normalize_stats()
            return f"{self.species}{self.name}找到了一个玩具！快乐值增加了10点，忠诚度增加了5点。"
        else:
            return f"今天是平凡的一天。"

    def display_pet_card(self):
        card = f"🐾 | 宠物名片 | 🐾\n"
        card += f"🐾 名字：{self.name}\n"
        card += f"👤 主人：{self.owner}\n"
        card += f"🧬 进化阶段：{self.species}\n"
        card += f"🌟 等级：{self.level}\n"
        card += f"⚡ 经验值：{int(self.experience)}/{int(self.next_level_exp())}\n"
        card += f"💰 金币数：{self.coins}\n"
        card += f"🔧 技能等级：{self.skill_level}\n"
        card += f"🧠 智力：{self.intelligence}\n"
        card += f"💪 耐力：{self.stamina}\n"
        card += f"🎂 出生日期：{self.birth_date.strftime('%Y-%m-%d')}\n"  # 添加生日信息
        
        status_names = {
            "hunger": "🍔 饱食度",
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
            card += f"🔄 下一进化阶段：{next_species_info['name']} (等级 {next_species_info['level']})"
        else:
            card += "🏆 当前已是最终进化形态。\n"
        return card


# # 创建宠物实例
# pet = VirtualPet(name="小宝", owner="小明", species="黑球兽")

# # 打印初始状态
# print("初始状态:")
# print(pet.display_pet_card())

# # 逐步增加经验值
# for exp_gain in range(100, 601, 100):  # 从100增加到600，每次增加100
#     print(f"\n给宠物增加 {exp_gain} 点经验.")
#     level_up_message = pet.gain_experience(exp_gain)
#     print(level_up_message)

#     # 检查升级和进化情况
#     print("当前状态:")
#     print(pet.display_pet_card())

#     # print("\n检查是否有进化发生:")
#     # print(pet.update_species())

#     # # 再次打印状态以查看升级和进化的效果（如果有的话）
#     # print("\n升级/进化后的状态:")
#     # print(pet.display_pet_card())

# 假设 VirtualPet 类已经定义，且包含您之前提供的方法

def main():
    # 创建一个宠物实例
    pet = VirtualPet(name="测试宠物", owner="测试主人", species="滚球兽")

    # 模拟增加不同数量的经验值
    experience_increments = [20, 40, 60, 80, 100]  # 您可以根据需要调整这些值

    for exp in experience_increments:
        print(f"\n增加 {exp} 点经验值...")
        level_up_message = pet.gain_experience(exp)
        print(level_up_message)

        # 打印宠物当前的详细状态
        print(pet.display_pet_card())

if __name__ == "__main__":
    main()
