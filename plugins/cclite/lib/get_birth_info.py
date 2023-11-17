import json
from datetime import datetime, timedelta
import os


curdir = os.path.dirname(__file__)
filepath = os.path.join(curdir, "people_data.json")
def load_data(filepath):
    with open(filepath, 'r', encoding='utf-8') as file:
        return json.load(file)

def get_next_birthday(birthday):
    today = datetime.now()
    this_years_birthday = datetime(year=today.year, month=birthday.month, day=birthday.day)

    # 如果今年的生日已经过去，则计算下一年的生日
    if this_years_birthday < today:
        next_years_birthday = datetime(year=today.year + 1, month=birthday.month, day=birthday.day)
        return next_years_birthday
    else:
        return this_years_birthday

def find_birthday_info(name, data):
    # 首先尝试匹配昵称（submitter）
    person_info = next((item for item in data if item['submitter'] == name), None)

    # 如果没有匹配到昵称，尝试匹配名字（name）
    if not person_info:
        person_info = next((item for item in data if item['name'] == name), None)

    if not person_info:
        return "未找到该昵称或名字的信息。"

    # 解析生日日期
    birthday_str = person_info['birthday']
    birthday_date = datetime.strptime(birthday_str, '%Y%m%d')
    lunar_birthday = person_info['lunar_birthday']

    
    # 计算距离下一个生日的天数
    next_birthday = get_next_birthday(birthday_date)
    weekday = next_birthday.strftime('%A')
    days_until_next_birthday = (next_birthday - datetime.now()).days

    # 返回格式化后的信息
    return f"🎉{name}的生日是：{birthday_date.strftime('%Y年%m月%d日')}🥳，农历{lunar_birthday}🌙，那天是{weekday}，距离{name}生日还有 {days_until_next_birthday} 天 🎈。"

def find_next_birthday_person(data):
    closest_birthday = None
    closest_days = float('inf')  # 表示无限大
    person_info = None

    for person in data:
        birthday_str = person['birthday']
        birthday_date = datetime.strptime(birthday_str, '%Y%m%d')
        next_birthday = get_next_birthday(birthday_date)
        days_until_next_birthday = (next_birthday - datetime.now()).days

        if days_until_next_birthday < closest_days:
            closest_days = days_until_next_birthday
            closest_birthday = next_birthday
            person_info = person

    # 返回最接近的生日和对应的人
    if person_info:
        name = person_info['name']
        lunar_birthday = person_info['lunar_birthday']
        weekday = closest_birthday.strftime('%A')
        return f"🎉 下一个即将过生日的是{name} 🥳，生日是：{closest_birthday.strftime('%Y年%m月%d日')} 📅，农历{lunar_birthday} 🌙，那天是{weekday}，距离生日还有 {closest_days} 天 🎈。"

    else:
        return "没有找到即将生日的人。"

def find_birthday(name=None):
    data = load_data(filepath)
    if name:
        return find_birthday_info(name, data)
    else:
        return find_next_birthday_person(data)


# # 加载数据
# data = load_data('people_data.json')

# 用户输入
name = input("请输入人名查询生日信息，直接回车则查询最近一个即将过生日的人：").strip()

# 执行查询并打印结果
birthday_info = find_birthday(name if name else None)
print(birthday_info)

