'''
使用多进程爬取三国演义的章节目录
未完成，最后q.empty()的while 循环这里不准确
'''
import requests
from bs4 import BeautifulSoup
import os
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)  #抑制InsecureRequestWarning 打印
import time
from multiprocessing import Process, Queue
from custom_requests import requests_get


def retrieve_chapter_info_from_litag(q,tag,**kw):
    print('current pid is %s' % os.getpid())
    print('current tag is %s' % tag)

    chapter_title = tag.a.string.strip()
    chapter_link = tag.a['href']
    chapter_content = ''
    url = 'https://www.shicimingju.com/{}'.format(chapter_link)
    kw.update({'url': url})
    response = requests_get(**kw)
    response.encoding='utf-8'
    response_text = response.text
    soup = BeautifulSoup(response_text,'lxml')
    div_tag = soup.find('div',class_='chapter_content')
    chapter_content = div_tag.text.strip()
    q.put((chapter_title, chapter_content))

    print('pid %s crawl over!' % os.getpid())
    print('current q size is %s' % q.qsize())

    return

if __name__=='__main__':
    
    s_time= time.time()

    url = 'https://www.shicimingju.com/book/sanguoyanyi.html'

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.93 Safari/537.36'
    }

    request_dict = {
        'url': url,
        'headers': headers,
        'timeout': 5,
        'verify': False
    }

    response = requests_get(**request_dict)
    response.encoding = 'utf-8'
    response_text = response.text
    soup = BeautifulSoup(response_text,'lxml')
    li_tag_list = soup.select('.book-mulu > ul > li')  #使用选择器，获取class属性是book-mulu，ul 标签下的li标签

    #调用Q
    q = Queue()
    max_queue_num = len(li_tag_list)

    print(max_queue_num)
    for each in li_tag_list:
        p = Process(target=retrieve_chapter_info_from_litag,args=(q,each),kwargs=request_dict)
        p.daemon = True
        p.start()
        time.sleep(0.2)

    while q.qsize() < max_queue_num:
        time.sleep(0.1)
    
    print('*'*30)
    print('current q size is %s' % q.qsize())

    write_lines = []
    while not q.empty():
        q_content = q.get()
        print(f'q_content is {q_content[0]}')
        print('remaining q size is %s' % q.qsize())
        write_lines.append(str(q_content[0]) + '\n' + str(q_content[1]) + '\n')
    
    print('*'*30)
    print('current q size is %s' % q.qsize())
    
    print(len(write_lines))
    
    with open('sanguo_multi.txt','w',encoding='utf-8') as fp:
        fp.writelines(write_lines)

    print('over!!!')

    e_time = time.time()
    print('{} seconds cost...'.format(int(e_time - s_time)))
