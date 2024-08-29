import requests
import json

def ask_question(question):
    send_url = "https://ai.ysxkj.com/send_message.php"
    get_url = "https://ai.ysxkj.com/get_response.php"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
        "Authorization": "Basic eXN4OjEyMzQ1Ng==",
        "content-type": "application/x-www-form-urlencoded",
        "cookie": "PHPSESSID=q54jgttaljtnf69vklgch6tuah"
    }

    try:
        # 发送问题
        payload = { "message": question }
        send_response = requests.post(send_url, data=payload, headers=headers)
        send_response.raise_for_status()  # 检查请求是否成功
        send_response_json = send_response.json()
    except requests.exceptions.RequestException as e:
        return None

    try:
        # 获取响应
        get_response = requests.get(get_url, headers=headers, stream=True)
        get_response.raise_for_status()  # 检查请求是否成功
        
        # 处理流式响应
        full_response_text = ""
        for line in get_response.iter_lines():
            if line:
                decoded_line = line.decode('utf-8')
                if decoded_line.startswith("data: "):
                    json_data = decoded_line[6:]  # 去掉 "data: " 前缀
                    try:
                        json_object = json.loads(json_data)
                        content = json_object.get("content", "")
                        full_response_text += content
                    except json.JSONDecodeError as e:
                        pass

        return full_response_text

    except requests.exceptions.RequestException as e:
        return None

# if __name__ == "__main__":
#     question = "你是谁？"
#     response = ask_question(question)
#     if response:
#         print("Final Response:", response)
