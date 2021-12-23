import enum
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)  #抑制InsecureRequestWarning 打印
from custom_requests import requests_get
import re

'''
爬取jd上某个商品的评论
'''

if __name__ == '__main__':
    url = 'https://club.jd.com/comment/productPageComments.action'

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.93 Safari/537.36'
    }

    params = {
        'callback': 'fetchJSON_comment98',
        'productId': '100026922720',
        'score': '0',
        'sortType': '5',
        'page': '1',
        'pageSize': '10',
        'isShadowSku': '0',
        'rid': '0',
        'fold': '1'
    }

    comments_list = []
    #爬取前10页
    for i in range(1,10):
        params.update({'page': str(i)})
        response = requests_get(url=url,headers=headers,params=params,timeout=5,verify=False)
        page_text = response.text
        #使用正则匹配所有的评论内容
        res = re.findall(r'"content":"(.*?)"', page_text, re.DOTALL)
        # print(f"res is {res}")
        comments_list += res

    print(comments_list)
    with open('jd_comments.txt','w',encoding='utf-8') as fp:
        for i,value in enumerate(comments_list):
            fp.writelines("*"*20+'\n')
            fp.writelines(f"第{i+1}个人的评论:\n")
            fp.writelines(value + "\n")

    print('Over!!!')
