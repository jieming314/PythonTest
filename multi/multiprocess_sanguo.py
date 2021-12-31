'''
使用进程池爬取三国演义的章节目录
'''
import os
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)  #抑制InsecureRequestWarning 打印
import time
from multiprocessing import Pool
from custom_requests import requests_get
from lxml import etree


def retrieve_chapter_info_from_url(url,**kw):
    c_pid = os.getpid()
    print(f'current pid is {c_pid}')
    print(f'url is {url}')

    chapter_content = ''
    chapter_content_url = 'https://www.shicimingju.com{}'.format(url)
    response = requests_get(url=chapter_content_url,**kw)
    response.encoding='utf-8'
    response_text = response.text

    parser = etree.HTMLParser(encoding='utf-8')
    tree = etree.HTML(response_text,parser=parser)
    
    chapter_content = tree.xpath('//div[@class="chapter_content"]/text()')[0].strip()
    # print(chapter_content)

    print('pid %s crawl over!' % os.getpid())

    return chapter_content

if __name__=='__main__':
    
    s_time= time.time()

    url = 'https://www.shicimingju.com/book/sanguoyanyi.html'

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.93 Safari/537.36'
    }

    request_dict = {
        'headers': headers,
        'timeout': 5,
        'verify': False
    }

    response = requests_get(url=url,**request_dict)
    response.encoding = 'utf-8'
    response_text = response.text

    parser = etree.HTMLParser(encoding='utf-8')
    tree = etree.HTML(response_text,parser=parser)
    li_tag_list = tree.xpath('//div[@class="book-mulu"]/ul/li')

     # print(li_tag_list)
    print(len(li_tag_list))

    chapter_title_list =[]
    chapter_content_url_list = []
    for li_tag in li_tag_list:
        chapter_content_url = li_tag.xpath('./a/@href')[0]
        chapter_content_url_list.append(chapter_content_url)
        chapter_title_list.append(li_tag.xpath('.//text()')[0])
    
    print(chapter_title_list)
    print(chapter_content_url_list)

    # retrieve_chapter_info_from_url(chapter_content_url_list[0],**request_dict)

    with Pool() as p:
        result = []
        for url in chapter_content_url_list:
            result.append(p.apply_async(retrieve_chapter_info_from_url,(url,),request_dict))
        p.close()
        p.join()
    
    print([each.get() for each in result])

    print('over!!!')

    e_time = time.time()
    print('{} seconds cost...'.format(int(e_time - s_time)))
