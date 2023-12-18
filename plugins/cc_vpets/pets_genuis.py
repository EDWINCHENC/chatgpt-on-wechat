import json
import os
import random
# from ..cclite.lib.model_factory import ModelGenerator

class VirtualPet:
    def __init__(self, name, hunger=50, happiness=50, health=50, level=1, experience=0):
        self.name = name
        self.hunger = hunger
        self.happiness = happiness
        self.health = health
        self.level = level
        self.experience = experience

    def gain_experience(self, amount):
        self.experience += amount
        if self.experience >= 100:  # 假设每级所需经验值为 100
            self.experience -= 100
            self.level_up()

    def level_up(self):
        self.level += 1
        # 每升一级，提升宠物的属性
        self.hunger += 10
        self.happiness += 10
        self.health += 10
        self.normalize_stats()
        return f"{self.name}升级了！现在是 {self.level} 级。"


    def feed(self):
        self.hunger += 10
        self.happiness += 5
        self.normalize_stats()

    def play(self):
        self.happiness += 15
        self.hunger -= 5
        self.normalize_stats()

    def checkup(self):
        self.health += 10
        self.normalize_stats()
        
    def walk(self):
        self.happiness += 10
        self.health += 5
        self.normalize_stats()

    def train(self):
        self.happiness -= 5
        self.health += 10
        self.gain_experience(15)
        self.normalize_stats()

    def bathe(self):
        self.happiness -= 10
        self.health += 20
        self.normalize_stats()


    def normalize_stats(self):
        # 确保所有属性值在 0-100 之间
        self.hunger = min(100, max(0, self.hunger))
        self.happiness = min(100, max(0, self.happiness))
        self.health = min(100, max(0, self.health))

    def status(self):
        # 返回宠物的当前状态
        return f"{self.name}的状态：饥饿度 {self.hunger}, 快乐度 {self.happiness}, 健康度 {self.health}"

# 用户ID到宠物的映射
user_pets = {}

def handle_message(user_id, message):
    if user_id not in user_pets:
        # 如果用户没有宠物，提供领养选项
        return adopt_pet(user_id, message)
    else:
        # 处理与宠物的互动
        return interact_with_pet(user_pets[user_id], message)

def adopt_pet(user_id, pet_name):
    # 创建新宠物实例
    user_pets[user_id] = VirtualPet(pet_name)
    return f"恭喜你领养了宠物 {pet_name}!"

def interact_with_pet(pet, command):
    if command == "feed":
        pet.feed()
        return f"你喂了{pet.name}，{pet.status()}"
    elif command == "play":
        pet.play()
        return f"你和{pet.name}玩耍了，{pet.status()}"
    elif command == "checkup":
        pet.checkup()
        return f"你为{pet.name}做了健康检查，{pet.status()}"
    elif command == "walk":
        pet.walk()
        return f"你带{pet.name}去散步了，{pet.status()}"
    elif command == "train":
        pet.train()
        return f"你训练了{pet.name}，{pet.status()}"
    elif command == "bathe":
        pet.bathe()
        return f"你给{pet.name}洗了澡，{pet.status()}"
    elif command == "status":
        return pet.status()
    else:
        return "我不明白你想要做什么。"

def random_event(pet):
    event = random.choice(["find_food", "get_sick", "nothing"])
    if event == "find_food":
        pet.hunger += 20
        return f"{pet.name}意外发现了食物！"
    elif event == "get_sick":
        pet.health -= 15
        return f"不幸的是，{pet.name}生病了。"
    else:
        return f"今天是平凡的一天。"

    
def save_pets_to_json(user_pets, filename="pets.json"):
    """将所有宠物的状态保存到 JSON 文件中"""
    with open(filename, "w") as file:
        pets_data = {user_id: pet.__dict__ for user_id, pet in user_pets.items()}
        json.dump(pets_data, file, indent=4)

def load_pets_from_json(filename="pets.json"):
    """从 JSON 文件中加载宠物的状态"""
    if not os.path.exists(filename):
        return {}

    with open(filename, "r") as file:
        pets_data = json.load(file)
        return {user_id: VirtualPet(**data) for user_id, data in pets_data.items()}


def simulate_interaction():
    # 模拟用户互动
    user_actions = [
        ("user123", "小宝"),
        ("user123", "feed"),
        ("user123", "play"),
        ("user123", "checkup"),
        ("user123", "walk"),
        ("user123", "train"),
        ("user123", "bathe"),
        ("user123", "status"),
        ("user456", "小花"),
        ("user456", "feed")
    ]

    for user_id, action in user_actions:
        print(f"用户{user_id}执行操作: {action}")
        response = handle_message(user_id, action)
        print("反馈:", response)
        print()

    # 模拟随机事件
    print("触发随机事件:")
    for _ in range(3):
        print(random_event(user_pets["user123"]))
        print()

    # 保存宠物状态
    save_pets_to_json(user_pets)
    print("宠物状态已保存。")

    # 加载宠物状态
    loaded_pets = load_pets_from_json()
    print("加载宠物状态：")
    for user_id, pet in loaded_pets.items():
        print(f"用户{user_id}的宠物{pet.name}状态: {pet.status()}")

# 运行模拟互动
simulate_interaction()
