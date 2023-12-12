import requests
import datetime

def fetch_horoscope(sign: str) -> str:
    """获取并整合两个API的星座运势信息"""
    url1 = f"https://api.52vmy.cn/api/wl/xingzuo?type=json&msg={sign}"
    url2 = f"https://service-m9yegcn9-1311248022.sh.apigw.tencentcs.com/release/star?n={sign}"

    try:
        response1 = requests.get(url1)
        response2 = requests.get(url2)
        if response1.status_code == 200 and response2.status_code == 200:
            data1 = response1.json().get('data', {})
            data2 = response2.json()
            return format_horoscope(sign, data1, data2)
        else:
            return "无法获取星座运势，请稍后再试。"
    except requests.RequestException as e:
        return f"请求异常：{e}"

def percent_to_stars(percent: str) -> str:
    """将百分比评分转换为星星emoji，包括半星的处理"""
    try:
        score = int(percent.rstrip('%'))
        full_stars = score // 20  # 每20%一个满星
        half_star = 1 if score % 20 >= 10 else 0  # 超过10%就算半星
        return '⭐' * full_stars + '🌟' * half_star + '✰' * (5 - full_stars - half_star)
    except ValueError:
        return "评分不可用"


def format_horoscope(sign: str, data1: dict, data2: dict) -> str:
    """格式化星座运势信息，整合两个API的数据"""
    date = datetime.datetime.fromtimestamp(data1['date'] / 1000).strftime('%Y年%m月%d日')
    return (
        f"🌟 {date}，✨{sign}✨运势：\n"
        f"⏰ 幸运时间：{data1['lucklyTime'].strip()}\n"
        f"🎨 幸运颜色：{data1['lucklyColor']}\n"
        f"🍀 幸运数字：{data1['numbers']}\n"
        f"🧭 幸运方向：{data1['direction'].strip()}\n"
        f"🤝 友好星座：{data1['friends'].strip()}\n"
        f"📈 综合评分：{percent_to_stars(data2['index']['composite'])}\n"
        f"💌 爱情评分：{percent_to_stars(data2['index']['love'])}\n"
        f"💼 事业评分：{percent_to_stars(data2['index']['cause'])}\n"
        f"💰 财运评分：{percent_to_stars(data2['index']['money'])}\n"
        f"🍀 健康评分：{percent_to_stars(data2['index']['heath'])}\n"
        f"🗣️ 交流评分：{percent_to_stars(data2['index']['talk'])}\n"
        f"✨ 适宜：{data2['fitting']}\n"
        f"🚫 避免：{data2['avoid']}\n"
        f"📌 小贴士：{data1['shorts'].strip()}\n"
        f"🔮 综合运势：{data1['contentAll'].strip()}\n"
        f"💼 事业运势：{data1['contentCareer'].strip()}\n"
        f"💰 财运：{data1['contentFortune'].strip()}\n"
        f"❤️ 爱情运势：{data1['contentLove'].strip()}\n"
    )
    

def fetch_divination() -> dict:
    """调用第三方接口进行求签，并返回结果"""
    url = "https://api.t1qq.com/api/tool/cq?key=s8sMrfY2iUpYQXuHlXVXOXtwRN"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            return response.json()
    except requests.RequestException:
        pass
    return None

# 示例调用
# sign = "白羊座"
# result = fetch_horoscope(sign)
# print(result)

