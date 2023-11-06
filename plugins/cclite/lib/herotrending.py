import json
import requests
import os

def get_hero_id_from_name(hero_name):
    # 获取当前文件（脚本）的目录路径
    curdir = os.path.dirname(__file__)
    
    # 创建一个完整的文件路径来定位kingherolist.json
    json_path = os.path.join(curdir, "kingherolist.json")
    
    # 用utf-8编码打开文件，并加载JSON数据
    with open(json_path, 'r', encoding='utf-8') as f:
        hero_list = json.load(f)
        
    # 搜索英雄名，并返回相应的ID
    for hero in hero_list:
        if hero["cname"] == hero_name:
            return str(hero["ename"])
    return None


def fetch_and_parse_data(hero_name):
    hero_id_to_fetch = get_hero_id_from_name(hero_name)
    if hero_id_to_fetch is None:
        return f"No ID found for hero {hero_name}"


    url = "https://api.91m.top/hero/v1/app.php?type=getHeroChartsLog&aid=7"
    response = requests.get(url)
    
    if response.status_code == 200:
        data = response.json()
        rows = data['data']['result']['rows']
        
        if hero_id_to_fetch in rows:
            hero_data = rows[hero_id_to_fetch]
            output = [f"Hero ID: {hero_id_to_fetch}, Hero Name: {hero_name}"]
            
            for entry in hero_data:
                date = entry['日期']
                heat = entry['热度']
                output.append(f"{date}: {heat}")
            return "\n".join(output)
        else:
            return f"No data available for Hero ID {hero_id_to_fetch}"
    else:
        return f"Failed to fetch data, status code: {response.status_code}"

# if __name__ == "__main__":
#     hero_name_to_fetch = "云缨"  # 你可以更改这个名称为你想查询的英雄名称
#     fetch_and_parse_data(hero_name_to_fetch)
