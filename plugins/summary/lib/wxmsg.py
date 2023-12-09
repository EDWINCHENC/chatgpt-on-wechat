import sqlite3
import blackboxprotobuf
import json
from datetime import datetime, timedelta, time
import os
import jieba
import re
from collections import defaultdict, Counter
import csv
import random


def get_msg_from_db(days=None):

    # 加载roomdata1.json文件中的昵称映射
    curdir = os.path.dirname(os.path.realpath(__file__))
    json_path = os.path.join(curdir, 'roomdata1.json')
    with open(json_path, 'r', encoding='utf-8') as file:
        members_list = json.load(file)
    nickname_mapping2 = {member['ID']: member['Nickname'] for member in members_list}
    
    # 加载配置文件
    config_path = os.path.join(curdir, 'config.json')
    with open(config_path, 'r') as config_file:
        config = json.load(config_file)

    # 从配置文件中提取数据库路径
    db_paths = config['db_paths']
    micro_msg_db_path = config['micro_msg_db_path']
    target_talker = config['target_talker']
    # 如果没有指定days，则使用配置文件中的默认值
    if days is None:
        days = config.get('default_days', 90)  # 如果配置文件中没有default_days，则默认为90


    # 提取微信昵称映射
    nickname_mapping = {}
    with sqlite3.connect(micro_msg_db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT UserName, NickName FROM Contact")  # 替换SomeTable为实际的表名
        for row in cursor.fetchall():
            wechat_id, nickname = row
            nickname_mapping[wechat_id] = nickname


    # 获取当前日期并计算N个月前的日期
    current_date = datetime.now()
    analysis_start_date = current_date - timedelta(days=days)

    # 类型映射字典
    type_mapping = {
        1: "文本",
        3: "图片",
        34: "语音",
        43: "视频",
        47: "表情",
        49:"小程序",
        10000:"拍了拍或者红包"
    }

    # 存储所有数据库提取出的聊天记录
    all_extracted_messages = []

    # 对每个数据库路径执行操作
    for db_path in db_paths:
        # 连接到 SQLite 数据库
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # 构建SQL查询，筛选从一个月前到当前日期的消息记录
        start_of_period = int(analysis_start_date.timestamp())
        end_of_period = int(current_date.timestamp())

        sql_query = f"""
        SELECT Issender, Type, SubType, CreateTime, StrTalker, StrContent, BytesExtra
        FROM MSG
        WHERE
            StrTalker = '{target_talker}' AND
            CreateTime >= {start_of_period} AND
            CreateTime <= {end_of_period}
        """

        cursor.execute(sql_query)
        rows = cursor.fetchall()

        # 迭代每一行数据
        for row in rows:
            issender, msg_type, sub_type, create_time, str_talker, str_content, bytes_extra = row
            # 解析BytesExtra字段以获取微信ID
            wechat_id = None

            # 转换消息类型
            # 如果Type为10000，检查SubType确定具体的消息类型
            if msg_type == 10000:
                if sub_type == 4:
                    msg_type_str = "拍一拍"
                elif sub_type == 0:
                    msg_type_str = "撤回消息"
                else:
                    msg_type_str = "系统消息"
            else:
                msg_type_str = type_mapping.get(msg_type, "未知类型")

            # 如果消息类型不是文本，并且内容包含xml或msg标签，则清空内容
            if msg_type != 1 and ('<xml>' in str_content or '<msg>' in str_content):
                str_content = ""
            # 当消息是由用户自己发送时，设置wechat_id为用户自己的ID
            wechat_id = config.get('my_wechat_id','') if issender == 1 else None
            
            # 如果消息不是用户发送的，解析BytesExtra字段以获取微信ID
            if issender != 1 and bytes_extra:
                try:
                    decoded_message_json, message_type = blackboxprotobuf.protobuf_to_json(bytes_extra)
                    decoded_message = json.loads(decoded_message_json)
                    
                    # 获取第一个 '2' 键的值
                    if '3' in decoded_message and isinstance(decoded_message['3'], list):
                        for item in decoded_message['3']:
                            if isinstance(item, dict) and '2' in item:
                                wechat_id = item['2']
                                break  # 只获取第一个 '2' 键的值后退出循环

                except json.JSONDecodeError as e:
                    print(f"Error decoding JSON: {e}")
                    continue  # 如果解析错误，跳过这条记录


            # 使用数据库中的昵称
            nickname = nickname_mapping.get(wechat_id, "未知成员")
            # print(f"nickname: {nickname}")
            # 新增：从roomdata1.json中获取的昵称
            nickname2 = nickname_mapping2.get(wechat_id, "未知成员")
            # print(f"nickname2: {nickname2}")
            # 转换消息类型
            msg_type_str = type_mapping.get(msg_type, "未知类型")
            # 记录消息记录，包括解析后的微信ID
            time_str = datetime.fromtimestamp(create_time).strftime('%Y-%m-%d %H:%M:%S')
            all_extracted_messages.append({
                "issender": issender,
                "type": msg_type_str,
                "create_time": time_str,
                "talker": str_talker,
                "content": str_content,
                "wechat_id": wechat_id,
                "nickname": nickname,  # 新增昵称信息
                "nickname2": nickname2  # 新增nickname2字段,自定义的昵称
            })
        # 关闭数据库连接
        conn.close()
    return all_extracted_messages
#打印提取出的聊天记录
# results = get_msg_from_db(10)
# print(results)



# 定义函数，用于找出每天消息数最多的人
def find_most_active_user_by_day():
    # 创建一个默认字典来记录每天的消息发送者及其计数
    daily_activity = defaultdict(Counter)
    messages = get_msg_from_db()

    # 遍历消息列表，记录每个人每天的消息数
    for message in messages:
        # 将字符串日期转换为日期对象
        date = datetime.strptime(message["create_time"], '%Y-%m-%d %H:%M:%S').date()
        # 增加该用户在这一天的消息计数
        daily_activity[date][message["nickname"]] += 1

    # 现在我们有了每天每个人的消息数，我们将找出每天消息数最多的人
    most_active_by_day = {}
    for date, activity in daily_activity.items():
        # 找到计数最多的用户
        most_active = activity.most_common(1)[0]  # 这将返回一个格式为 (nickname, count) 的元组
        most_active_by_day[date] = most_active

    return most_active_by_day

# 调用函数并打印结果
# most_active_by_day = find_most_active_user_by_day()
# for date, (nickname, count) in most_active_by_day.items():
#     print(f"日期: {date}, 昵称: {nickname}, 消息数: {count}")
    

# 定义函数，用于统计每天的消息条数
def count_messages_per_day():
    # 创建一个字典来计数每天的消息条数
    daily_counts = defaultdict(int)
    messages = get_msg_from_db()

    # 遍历消息列表
    for message in messages:
        # 提取每条消息的日期部分
        date = message["create_time"].split(" ")[0]
        # 在对应日期的计数上加1
        daily_counts[date] += 1

    # 格式化每天的消息条数
    formatted_counts = "\n".join([f"日期: {date}, 消息数: {count}" for date, count in sorted(daily_counts.items())])

    return formatted_counts

# 调用函数并获取格式化后的数据
# formatted_daily_message_counts = count_messages_per_day()
# print(formatted_daily_message_counts)


# 定义函数，用于统计@别人的次数
def analyze_mentions():
    messages = get_msg_from_db()  # 使用您现有的函数获取消息
    mention_pattern = re.compile(r"@([\w\-\u4e00-\u9fa5]+)")  # 正则表达式，用来匹配@后跟着的昵称

    mentions_counter = Counter()  # 用于统计每个人被@的次数
    interactions = defaultdict(Counter)  # 用于统计每个人@别人的次数

    for message in messages:
        sender = message['nickname']  # 发送者的昵称
        mentions = mention_pattern.findall(message['content'])  # 在消息内容中查找所有提及

        for mention in mentions:
            mentions_counter[mention] += 1  # 统计被@的次数
            interactions[sender][mention] += 1  # 统计发送者@别人的次数

    # 将interactions转换为Counter对象
    interactions_counter = Counter({k: sum(v.values()) for k, v in interactions.items()})

    # 选择一个特定用户来格式化输出其@别人的情况，例如取互动次数最多的用户
    most_interactive_user = interactions_counter.most_common(1)[0][0] if interactions_counter else None
    user_interactions_formatted = ""
    if most_interactive_user:
        user_interactions_formatted = "\n".join([f"{most_interactive_user} @了 {person}: {count}次" for person, count in interactions[most_interactive_user].most_common(5)])

    # 格式化输出被@最多的人
    most_mentioned_formatted = "\n".join([f"{person}: {count}次" for person, count in mentions_counter.most_common(5)])

    # 合并两部分结果
    result = f"被@最多的人:\n{most_mentioned_formatted}\n\n{user_interactions_formatted}"

    return result

# 使用示例
# analysis_result = analyze_mentions()
# print(analysis_result)

# 定义函数，用于加载停用词列表
def load_stopwords():
    """
    加载停用词列表。

    :return: 一个包含停用词的集合。
    """
    # 获取当前脚本所在目录
    curdir = os.path.dirname(os.path.realpath(__file__))
    # 构建停用词文件的完整路径
    stopwords_path = os.path.join(curdir, 'cn_stopwords.txt')

    with open(stopwords_path, 'r', encoding='utf-8') as f:
        stopwords = set([line.strip() for line in f])
    return stopwords
# 分析特定用户的聊天记录
def analyze_user_messages(nickname, num_words=5):
    """
    分析特定昵称用户的聊天记录。

    :param messages: 聊天记录的列表。
    :param nickname: 要分析的用户昵称。
    :param num_words: 返回的高频词数量。
    :return: 包含各类统计数据的字典。
    """
    stopwords = load_stopwords()
    messages = get_msg_from_db()
    mention_pattern = re.compile(r"@([\w\-\u4e00-\u9fa5]+)")  # 用于匹配@后的昵称

    texts, message_counts, message_length, hourly_counts = [], Counter(), 0, Counter()
    daily_message_count, daily_message_length = Counter(), defaultdict(int)
    user_mentions = Counter()  # 新增：用于统计该用户@别人的次数

    # 遍历消息列表
    for msg in messages:
        # print(f"Processing message: Type: {msg['type']}, Nickname: {msg['nickname']}")
        if msg['nickname'] == nickname:
            # 统计消息类型
            message_counts[msg['type']] += 1

            # 对文本消息进行处理
            if msg['type'] == '文本':  # 文本消息
                content = msg['content'].strip()
                texts.append(content)
                message_length += len(msg['content'])

                # 统计每天的字数
                date = msg['create_time'].split(' ')[0]
                daily_message_length[date] += len(msg['content'])

            # 统计每个小时的消息数量
            hour = datetime.strptime(msg['create_time'], '%Y-%m-%d %H:%M:%S').hour
            hourly_range = f"{hour // 2 * 2:02d}-{(hour // 2 + 1) * 2:02d}"
            hourly_counts[hourly_range] += 1

            # 统计每天的消息数量
            date = msg['create_time'].split(' ')[0]
            daily_message_count[date] += 1
            
            # 新增：处理@的情况
            mentions = mention_pattern.findall(msg['content'])
            for mention in mentions:
                user_mentions[mention] += 1
    # 只获取被艾特最多的前5个人
    top_mentions = user_mentions.most_common(5)

    # 找出发言最多的那天及其字数
    most_talkative_day, max_messages, max_messages_length = None, 0, 0
    if daily_message_count:
        most_talkative_day, max_messages = daily_message_count.most_common(1)[0]
        max_messages_length = daily_message_length[most_talkative_day]

    # 对文本消息进行分词
    all_text = ' '.join(texts)
    all_text = re.sub(r'[^\w\s]', '', all_text)  # 移除标点符号
    words = [word for word in jieba.cut(all_text, cut_all=False) if word not in stopwords and len(word) > 1]
    word_counts = Counter(words)

    # 将高频词转换为字典格式以便于使用JSON格式化
    high_freq_words_dict = {word[0]: f"{word[1]}次" for word in word_counts.most_common(num_words)}

    # 结果汇总并格式化
    formatted_result = (
        f"消息类型统计:\n{json.dumps(message_counts, indent=4, ensure_ascii=False)}\n"
        f"高频词:\n{json.dumps(high_freq_words_dict, indent=4, ensure_ascii=False)}\n"
        f"每2小时发言频率:\n{json.dumps(hourly_counts, indent=4, ensure_ascii=False)}\n"
        f"总发言条数: {sum(daily_message_count.values())}\n"
        f"总字数: {message_length}\n"
        f"最话痨的一天: {most_talkative_day} (发言条数: {max_messages}, 字数: {max_messages_length})"
        f"\n该用户@了以下人员:\n{json.dumps(top_mentions, indent=4, ensure_ascii=False)}"
    )

    return formatted_result


#测试代码
# if __name__ == "__main__":
#     nickname = '眠眠羊₊⁺'  # 替换为实际要分析的昵称
#     formatted_analysis_result = analyze_user_messages(nickname)
#     print(formatted_analysis_result)



# 定义函数，用于分析指定关键词的提及情况
def analyze_keyword_in_messages(keyword):
    """
    分析指定关键词在聊天记录中的提及情况。

    :param messages: 包含聊天记录的列表
    :param keyword: 要搜索的关键词
    :return: 关于关键词的分析结果，包括提及次数、最活跃的日期、星期几、昵称和示例消息
    """
    
    # 初始化计数器
    # keyword_mention_counts: 用于计算每个日期关键词提及的次数
    # keyword_by_date: 用于存储每个日期及其对应星期的关键词提及次数
    # keyword_by_user: 用于计算每个用户提及关键词的次数
    keyword_mention_counts = Counter()
    keyword_by_date = defaultdict(Counter)
    keyword_by_user = Counter()

    # 编译正则表达式以匹配关键词（忽略大小写）
    keyword_regex = re.compile(re.escape(keyword), re.IGNORECASE)
    messages = get_msg_from_db()
    # 遍历消息列表
    for message in messages:
        # 检查消息内容中是否包含关键词
        if keyword_regex.search(message['content']):
            # 提取消息创建日期
            date = message['create_time'].split(' ')[0]
            # 将日期转换为星期
            weekday = datetime.strptime(date, '%Y-%m-%d').strftime('%A')
            # 获取发送者昵称
            nickname = message['nickname']

            # 更新计数器
            keyword_mention_counts[date] += 1
            keyword_by_date[date][weekday] += 1
            keyword_by_user[nickname] += 1

    # 检查是否找到含有关键词的消息
    if not keyword_mention_counts:
        return None

    # 找出提及关键词最多的日期及其次数
    most_mentioned_date, most_mentioned_count = keyword_mention_counts.most_common(1)[0]
    # 获取最多提及日期的星期
    most_mentioned_weekday = list(keyword_by_date[most_mentioned_date].keys())[0]
    # 找出提及关键词次数最多的用户及其次数
    most_active_nickname, mention_count = keyword_by_user.most_common(1)[0] if keyword_by_user else (None, 0)

    # 选取提及关键词最多的用户的部分消息作为示例
    sample_messages_with_date = [
        f"{message['create_time']} - {message['content'].strip()}"
        for message in messages
        if message['nickname'] == most_active_nickname and keyword_regex.search(message['content'])
    ][:10]

    # 构建并返回分析结果
    result = {
        "关键词": keyword,
        "总提及次数": sum(keyword_mention_counts.values()),
        "讨论最多的日期": f"{most_mentioned_date} ({most_mentioned_weekday})",
        "该日提及次数": most_mentioned_count,
        "提及最多的人": most_active_nickname,
        "提及次数": mention_count,
        "聊天记录摘取": '\n'.join(sample_messages_with_date)
    }

    return result


# 使用示例
# keyword_analysis = analyze_keyword_in_messages("奶茶")
# print(keyword_analysis)


def analyze_chat_year_report():
    stopwords = load_stopwords()
    messages = get_msg_from_db(365)  # 获取消息

    # 初始化统计变量
    total_messages = len(messages)
    total_words = 0
    all_word_counts = Counter()
    night_messages = []
    message_type_count = defaultdict(int)
    daily_messages = defaultdict(list)
    keywords = ["奶茶", "剧", "电视", "不行", "滴滴", "哈喽", "我不行", "观战", "意外", "哈哈", "相亲", "废物", "肯德基", "王者", "睡觉"]

    # 初始化关键词统计字典
    keyword_stats = {keyword: {'总次数': 0, '提及最多的人': None, '提及次数': 0} for keyword in keywords}
    keyword_mentions = {keyword: defaultdict(int) for keyword in keywords}

    for msg in messages:
        # 统计不同类型的消息数量
        message_type_count[msg['type']] += 1

        # 统计总字数和高频词
        if msg['type'] == "文本":
            content_length = len(msg['content'])
            total_words += content_length
            words = [word for word in jieba.cut(msg['content'], cut_all=False) if word not in stopwords and len(word) > 1]
            all_word_counts.update(words)
            for keyword in keywords:
                if keyword in msg['content']:
                    keyword_stats[keyword]['总次数'] += msg['content'].count(keyword)
                    keyword_mentions[keyword][msg['nickname']] += msg['content'].count(keyword)

        # 收集夜间消息
        msg_time = datetime.strptime(msg['create_time'], '%Y-%m-%d %H:%M:%S')
        if 0 <= msg_time.hour < 6:
            night_messages.append(msg)

        # 按日期收集消息
        daily_messages[msg_time.date()].append(msg)

    # 计算每个关键词提到最多的人及其提及次数
    for keyword in keywords:
        if keyword_mentions[keyword]:
            most_mentioned_person = max(keyword_mentions[keyword].items(), key=lambda x: x[1])
            keyword_stats[keyword]['提及最多的人'] = most_mentioned_person[0]
            keyword_stats[keyword]['提及次数'] = most_mentioned_person[1]

    # 统计每个用户（按昵称）的消息数
    user_message_count = Counter([msg['nickname'] for msg in messages])
    top_five_users = user_message_count.most_common(5)

    # 最活跃用户的详细分析（按昵称）
    most_active_user_nickname = top_five_users[0][0]
    most_active_user_messages = [msg for msg in messages if msg['nickname'] == most_active_user_nickname]
    most_active_user_word_counts = Counter()

    for msg in most_active_user_messages:
        if msg['type'] == "文本":
            words = [word for word in jieba.cut(msg['content'], cut_all=False) if word not in stopwords and len(word) > 1]
            most_active_user_word_counts.update(words)

    # 随机获取10条夜间消息
    random_night_messages = random.sample(night_messages, min(10, len(night_messages)))
    formatted_night_messages = [{'content': msg['content'], 'time': msg['create_time'], 'nickname': msg['nickname']} for msg in random_night_messages]

    # 聊天量最高的一天
    most_active_day, most_active_day_messages = max(daily_messages.items(), key=lambda x: len(x[1]))
    random_most_active_day_messages = random.sample(most_active_day_messages, min(5, len(most_active_day_messages)))

    # 转换最活跃天的消息为所需格式
    formatted_most_active_day_messages = [{'nickname': msg['nickname'], 'time': msg['create_time'], 'content': msg['content']} for msg in random_most_active_day_messages]

    return {
        '最活跃的排名前五用户': [{'昵称': user[0], '消息数': user[1]} for user in top_five_users],
        '年度最活跃用户': {
            '昵称': most_active_user_nickname,
            '聊天记录总条数': len(most_active_user_messages),
            '总字数': sum(len(msg['content']) for msg in most_active_user_messages if isinstance(msg['content'], str)),
            '平均每天发言数': len(most_active_user_messages) / 365,
            '最活跃的一天': most_active_day.strftime('%Y-%m-%d'),
            '高频词': [{'词汇': word[0], '频次': word[1]} for word in most_active_user_word_counts.most_common(10)],
            '最常@的人': [{'昵称': mention[0], '次数': mention[1]} for mention in Counter(re.findall(r'@([\u4e00-\u9fa5\w]+)', ' '.join([msg['content'] for msg in most_active_user_messages]))).most_common(5)]
        },
        '年度统计': {
            '总消息条数': total_messages,
            '总字数': total_words,
            '平均每天的聊天条数': total_messages / 365,
            '聊天量最高的一天': most_active_day.strftime('%Y-%m-%d'),
            '当天聊天记录': formatted_most_active_day_messages,
            '高频词汇': [{'词汇': word[0], '频次': word[1]} for word in all_word_counts.most_common(10)],
            '夜间消息': formatted_night_messages,
            '消息类型统计': dict(message_type_count),
            '关键词统计': keyword_stats
        }
    }

# 使用该函数
# chat_year_report = analyze_chat_year_report()

# 以美化的JSON格式打印结果
# print(json.dumps(chat_year_report, indent=4, ensure_ascii=False))



def get_messages_and_export_to_csv(nickname, days=40):
    """
    获取指定用户在近半年内的所有聊天记录，并将其导出为CSV文件。

    :param nickname: 指定用户的昵称。
    :param days: 查找的天数范围，默认为近半年（180天）。
    """
    all_messages = get_msg_from_db(days)
    user_messages = []

    # 过滤出指定用户的消息，并排除不需要的字段
    for message in all_messages:
        if message['nickname'] == nickname:
            message['create_time'] = message['create_time'].split(' ')[0]
            filtered_message = {key: message[key] for key in message if key not in ['issender']}
            user_messages.append(filtered_message)

    # 导出到CSV
    csv_file_name = f"{nickname}_messages_last_{days}_days.txt"
    with open(csv_file_name, 'w', newline='', encoding='utf-8') as file:
        if user_messages:
            fieldnames = user_messages[0].keys()
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()
            for message in user_messages:
                writer.writerow(message)

    # print(f"聊天记录已导出到文件：{csv_file_name}")

# 调用函数
# nickname = "小羊"
# get_messages_and_export_to_csv(nickname)




