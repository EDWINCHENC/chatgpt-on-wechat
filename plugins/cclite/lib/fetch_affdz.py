import requests
from lxml import etree
import random
from common.log import logger


# 扩展的User-Agent列表
HEADERS_LIST = [
    {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"},
    {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/81.0.4044.138 Safari/537.36"},
    # 可以添加更多的User-Agent选项
]

def fetch_html(url, max_retries=3):
    logger.debug("开始获取HTML内容。")
    """
    使用简单重试逻辑从给定URL获取HTML内容。
    Args:
        url (str): 获取内容的URL。
        max_retries (int): 失败情况下的最大重试次数。
    Returns:
        str: 页面的HTML内容，如果出现错误则为None。
    """
    retries = 0
    while retries < max_retries:
        try:
            response = requests.get(url, headers=random.choice(HEADERS_LIST), timeout=10)
            response.raise_for_status()
            logger.debug(f"成功获取 {url} 的内容。")  
            return response.text
        except requests.RequestException as e:
            logger.debug(f"获取 {url} 时出错: {e}。正在重试 {retries + 1}/{max_retries}")
            retries += 1

    logger.debug(f"多次重试后未能获取 {url} 的内容。")
    return None


def parse_html(html_content, movie_name):
    logger.debug("开始解析HTML内容。")
    """
    Parse HTML content to extract movie links and titles.

    Args:
        html_content (str): HTML content to parse.
        movie_name (str): Name of the movie to search for.

    Returns:
        list: List of dictionaries containing movie titles and links.
    """
    tree = etree.HTML(html_content)
    items = tree.xpath('//div[@class="sou-con-list"]/ul/li')

    results = []
    for item in items:
        link = item.xpath(f'.//a[contains(@title, "{movie_name}")]/@href')
        title = item.xpath(f'.//a[contains(@title, "{movie_name}")]/@title')

        if link and title:
            clean_title = etree.HTML(title[0]).xpath('string(.)').strip()
            results.append({'title': clean_title, 'link': link[0]})
    logger.debug(f"成功解析内容。")
    return results

def fetch_final_link(link):
    """
    Fetch the final link from the given page URL.

    Args:
        link (str): The URL of the page to fetch the final link from.

    Returns:
        dict: A dictionary containing the final link and its text.
    """
    html_content = fetch_html(link)
    if not html_content:
        return {"final_link": None, "link_text": None}

    tree = etree.HTML(html_content)
    final_link = tree.xpath('//div[@class="article-content"]//a/@href')[0]
    link_text_full = tree.xpath('//div[@class="article-content"]//a/text()')[0]

    # 提取所需部分，例如 "夸克网盘"、"迅雷网盘" 等
    link_text_simplified = link_text_full.split("（")[0].strip()

    return {"final_link": final_link, "link_text": link_text_simplified}

def fetch_movie_info(movie_name):
    logger.debug("开始获取电影信息。")
    """
    根据电影名获取电影信息，并进一步获取最终链接。
    Args:
        movie_name (str): 要获取信息的电影名。
    Returns:
        str: 格式化的电影信息字符串。
    """
    url = f"https://affdz.com/search.php?q={movie_name}"
    html_content = fetch_html(url)

    if not html_content:
        return "未能获取到资源。"

    movie_info = parse_html(html_content, movie_name)
    final_results = []
    for info in movie_info:
        final_link_info = fetch_final_link(info['link'])
        final_results.append({
            "title": info['title'],
            "link": info['link'],
            "final_link": final_link_info['final_link'],
            "link_text": final_link_info['link_text']
        })

    # 格式化输出
    formatted_output = f"🎬 共找到 {len(final_results)} 个相关资源:\n\n"
    for result in final_results:
        formatted_output += f"🎥 资源名称: {result['title']}\n🔗 链接: {result['final_link']} - {result['link_text']}\n--------------------------------\n"
    logger.debug("电影信息获取完成。")
    return formatted_output

# 示例：获取电影或电视剧的信息
# movie_name = "步步惊心"  # 可以替换为任何您想查询的影视剧名称
# formatted_movie_info = fetch_movie_info(movie_name)
# print(formatted_movie_info)