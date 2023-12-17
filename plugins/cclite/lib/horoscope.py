import requests
import datetime

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


def fetch_horoscope(sign: str) -> str:
    """获取并整合单个API的星座运势信息"""
    sign = "魔羯座" if sign == "摩羯座" else sign

    url = f"https://service-m9yegcn9-1311248022.sh.apigw.tencentcs.com/release/star?n={sign}"

    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            return format_horoscope(sign, data)
        else:
            return "无法获取星座运势，请稍后再试。"
    except requests.RequestException as e:
        return f"请求异常：{e}"

def percent_to_stars(percent: str) -> str:
    """将百分比评分转换为星星emoji，包括半星的处理"""
    try:
        score = int(percent.rstrip('%'))
        full_stars = score // 20
        half_star = 1 if score % 20 >= 10 else 0
        return '⭐' * full_stars + '🌟' * half_star + '✰' * (5 - full_stars - half_star)
    except ValueError:
        return "评分不可用"

def format_horoscope(sign: str, data: dict) -> str:
    """格式化星座运势信息，整合API的数据"""
    date = datetime.datetime.now().strftime('%Y年%m月%d日')
    return (
        f"🌟 {date}，✨{sign}✨运势：\n"
        f"🎨 幸运颜色：{data['luckColor']}\n"
        f"🍀 幸运数字：{data['luckNumber']}\n"
        f"🤝 友好星座：{data['adaptiveConstellation']}\n"
        f"📈 综合评分：{percent_to_stars(data['index']['composite'])}\n"
        f"💌 爱情评分：{percent_to_stars(data['index']['love'])}\n"
        f"💼 事业评分：{percent_to_stars(data['index']['cause'])}\n"
        f"💰 财运评分：{percent_to_stars(data['index']['money'])}\n"
        f"🍀 健康评分：{percent_to_stars(data['index']['heath'])}\n"
        f"🔮 综合运势：{data['composite']}\n"
        f"❤️ 爱情运势：{data['love']}\n"
        f"💼 事业运势：{data['cause']}\n"
        f"💰 财运：{data['money']}\n"
        f"✨ 适宜：{data['fitting']}\n"
        f"🚫 避免：{data['avoid']}\n"        
    )
    

# 示例调用
# sign = "白羊座"
# result = fetch_horoscope(sign)
# print(result)
