import sqlite3
import blackboxprotobuf
import json
from datetime import datetime, timedelta
import os
import jieba
import re
from collections import defaultdict, Counter


def get_msg_from_db(days=90):

    # 加载群成员的昵称映射数据
    # 获取当前脚本的目录
    curdir = os.path.dirname(os.path.realpath(__file__))
    # 构建roomdata1.json文件的路径
    json_path = os.path.join(curdir, 'roomdata1.json')

    # 使用动态路径加载群成员的昵称映射数据
    with open(json_path, 'r', encoding='utf-8') as file:
        members_list = json.load(file)

    # 创建wechat_id到Nickname的映射字典
    nickname_mapping = {member['ID']: member['Nickname'] for member in members_list}

    # 数据库文件路径列表
    # db_paths = [
    #     'D:\\MyWeb\\WeChatMsg\\app\\DataBase\\msg\\MSG0.db',
    #     'D:\\MyWeb\\WeChatMsg\\app\\DataBase\\msg\\MSG1.db',
    #     'D:\\MyWeb\\WeChatMsg\\app\\DataBase\\msg\\MSG2.db',
    #     'D:\\MyWeb\\WeChatMsg\\app\\DataBase\\msg\\MSG3.db',
    #     'D:\\MyWeb\\WeChatMsg\\app\\DataBase\\msg\\MSG5.db',
    #     'D:\\MyWeb\\WeChatMsg\\app\\DataBase\\msg\\MSG6.db',
    #     'D:\\MyWeb\\WeChatMsg\\app\\DataBase\\msg\\MSG7.db',
    #     'D:\\MyWeb\\WeChatMsg\\app\\DataBase\\msg\\MSG8.db'
    # ]
    
    db_paths = [
        '/home/ccc/MSG0.db',
        '/home/ccc/MSG1.db',
        '/home/ccc/MSG2.db',
    ]

    # 指定的群聊ID
    target_talker = '13291955218@chatroom'
    # 获取当前日期并计算一个月前的日期
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
            wechat_id = 'wxid_9jvcn4tu30q622' if issender == 1 else None
            
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


            # 如果wechat_id已经设置（用户自己的消息）或者解析BytesExtra成功，则从映射中获取昵称
            nickname = nickname_mapping.get(wechat_id, "未知成员") if wechat_id else "未知成员"
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
                "nickname": nickname  # 新增昵称信息
            })

        # all_extracted_messages.extend(extracted_messages)
        # 关闭数据库连接
        conn.close()
    return all_extracted_messages
#打印提取出的聊天记录
# results = get_msg_from_db(5)
# print(results)


# 定义函数，用于找出每天消息数最多的人
def find_most_active_user_by_day():
    # 创建一个默认字典来记录每天的消息发送者及其计数
    daily_activity = defaultdict(Counter)
    messages = get_msg_from_db(90)

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
# most_active_by_day = find_most_active_user_by_day(all_extracted_messages)
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

    # 找出发言最多的那天及其字数
    most_talkative_day, max_messages = None, 0
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
        f"\n该用户@了以下人员:\n{json.dumps(user_mentions, indent=4, ensure_ascii=False)}"
    )

    return formatted_result


#测试代码
if __name__ == "__main__":
    nickname = '小羊'  # 替换为实际要分析的昵称
    formatted_analysis_result = analyze_user_messages(nickname)
    print(formatted_analysis_result)


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



# 假设已有 get_msg_from_db, load_stopwords, analyze_user_messages 函数

def generate_annual_report():
    messages = get_msg_from_db(days=365)

    # 统计每个用户的消息数
    user_message_counts = Counter()
    user_message_lengths = defaultdict(int)  # 存储每个用户的总字数
    user_first_message_time = defaultdict(lambda: 23)  # 假设最早发言时间为23点
    user_weekday_activity = defaultdict(lambda: Counter())  # 记录每个用户每周哪天最活跃
    for message in messages:
        user = message["nickname"]
        user_message_counts[user] += 1
        user_message_lengths[user] += len(message["content"])
        message_time = datetime.strptime(message["create_time"], '%Y-%m-%d %H:%M:%S')
        if message_time.hour < user_first_message_time[user]:
            user_first_message_time[user] = message_time.hour
        user_weekday_activity[user][message_time.strftime("%A")] += 1

    # 找到年度最活跃用户
    most_active_user = user_message_counts.most_common(1)[0][0]
    total_messages = user_message_counts[most_active_user]
    total_words = user_message_lengths[most_active_user]
    avg_daily_messages = total_messages / 365
    earliest_message_time = user_first_message_time[most_active_user]
    most_active_weekday = user_weekday_activity[most_active_user].most_common(1)[0][0]

    # 获取最活跃用户的高频词和最常@的人
    user_analysis = analyze_user_messages(most_active_user, num_words=5)
    user_high_freq_words = json.loads(user_analysis)["高频词"]
    user_most_mentioned = json.loads(user_analysis)["该用户@了以下人员"].most_common(1)[0][0]

    # 组装年报
    annual_report = {
        "年度最活跃用户": most_active_user,
        "消息总条数": total_messages,
        "聊天总字数": total_words,
        "平均每天发言数": avg_daily_messages,
        "最早发言时间": earliest_message_time,
        "最活跃的星期": most_active_weekday,
        "高频词": user_high_freq_words,
        "最常@的人": user_most_mentioned
    }

    return annual_report

# 使用示例
# annual_report = generate_annual_report()
# print(json.dumps(annual_report, indent=4, ensure_ascii=False))


