import requests
import os
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)  #抑制InsecureRequestWarning 打印
from custom_requests import requests_get

'''
利用requests.get() 获取百度搜索的页面
'''

if __name__ == '__main__':

    url = 'https://www.baidu.com'
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.45 Safari/537.36'}
    response = requests_get(url=url,headers=headers,timeout=5,verify=False)
    page_text = response.text

    with open('baidu_search.html', 'w', encoding='utf-8') as fp:
        fp.write(page_text)

    print("over!!!")


