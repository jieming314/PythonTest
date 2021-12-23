'''
爬取三国演义所有的章节目录和内容，耗时77s 左右
https://www.shicimingju.com/book/sanguoyanyi.html
使用bs4
'''

import requests
from bs4 import BeautifulSoup
import os
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)  #抑制InsecureRequestWarning 打印
import time
from custom_requests import requests_get

if __name__=='__main__':

    s_time= time.time()

    url = 'https://www.shicimingju.com/book/sanguoyanyi.html'

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.93 Safari/537.36'
    }

    response = requests_get(url=url,headers=headers,timeout=5,verify=False)
    response.encoding = 'utf-8'    #原始的coding为ISO-8859-1，这里改为utf-8
    response_text = response.text

    soup = BeautifulSoup(response_text,'lxml')
    li_tag_list = soup.select('.book-mulu > ul > li')  #使用选择器，获取class属性是book-mulu，ul 标签下的li标签

    url_template = 'https://www.shicimingju.com/{}'
    chap_title_list = []
    chap_content_link = []

    for each in li_tag_list:
        chap_title_list.append(each.a.string)
        chap_content_link.append(each.a['href'])
    
    fp = open('sanguo.txt','w',encoding='utf-8')
    for x,y in zip(chap_title_list,chap_content_link):
        tmp_url = url_template.format(y)
        response = requests_get(url=tmp_url,headers=headers,timeout=5,verify=False)
        response.encoding='utf-8'
        response_text = response.text

        soup = BeautifulSoup(response_text,'lxml')
        tag = soup.find('div',class_='chapter_content')
        chap_content = tag.text
        fp.write(f'title:{x.strip()}\n{chap_content.strip()}')
    
    fp.close()
    print('over!!!')

    e_time = time.time()
    print('{} seconds cost...'.format(int(e_time - s_time)))

