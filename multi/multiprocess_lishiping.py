'''
使用进程池爬取梨视频科技页面的热门的3个视频
'''
import os
import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)  #抑制InsecureRequestWarning 打印
import time
from multiprocessing import Pool
from custom_requests import requests_get
from lxml import etree
import random
import re

def retrieve_real_mp4_url(url):
    print(f'url is {url}')

    video_id = url.split('_')[1]
    url_video = 'https://www.pearvideo.com/videoStatus.jsp'
    mrd = random.random()

    params = {
        'contId': video_id,
        'mrd': str(mrd)
    }

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.93 Safari/537.36',
        'Host': 'www.pearvideo.com',
        'X-Requested-With': 'XMLHttpRequest',
        'Referer': url
    }

    response = requests_get(url=url_video,params=params,headers=headers)
    response.encoding='utf-8'
    fake_video_link = response.json()['videoInfo']['videos']['srcUrl']
    # print(fake_video_link)

    '''
    从json中获取的到视频地址还需要经过处理才能得到真实的地址
    https://video.pearvideo.com/mp4/adshort/20211228/1641015800122-15810627_adpkg-ad_hd.mp4
    https://video.pearvideo.com/mp4/third/20211223/cont-1748493-10097838-230311-hd.mp4

    https://video.pearvideo.com/mp4/third/20211223/1641012225100-10097838-230311-hd.mp4
    https://video.pearvideo.com/mp4/adshort/20211228/cont-1706917-15810627_adpkg-ad_hd.mp4
    '''

    p = re.compile(r'https://(.*)/(\d+?)-(.*)')
    s = r'https://\g<1>/cont-' + video_id + r'-\g<3>'   #这里使用了反向引用，每个分组对应\g<分组id>
    video_link = p.sub(s,fake_video_link)

    # print(video_link)

    return video_link

def download_video(video_tuple):

    c_pid = os.getpid()

    print(f'pid {c_pid} start download...')

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.93 Safari/537.36',
    }

    video_name = video_tuple[0]
    url = video_tuple[1]
    response = requests_get(url=url,headers=headers)
    mp4_content = response.content

    with open(video_name, 'wb') as fp:
        fp.write(mp4_content)

    print(f'pid {c_pid} download complete...')


if __name__=='__main__':

    s_time= time.time()

    url = 'https://www.pearvideo.com/category_8'

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.93 Safari/537.36'
    }

    request_dict = {
        'headers': headers,
    }

    response = requests_get(url=url,**request_dict)
    response.encoding = 'utf-8'
    response_text = response.text

    parser = etree.HTMLParser(encoding='utf-8')
    tree = etree.HTML(response_text,parser=parser)
    video_tag_list = tree.xpath('//div[@class="category-top"]//div[@class="vervideo-bd"]')

    video_list = []

    for video_tag in video_tag_list:
        video_name = video_tag.xpath('.//div[@class="vervideo-title"]/text()')[0].strip() + '.mp4'
        video_id = video_tag.xpath('.//a/@href')[0]
        video_link = 'https://www.pearvideo.com/' + video_id
        video_real_url = retrieve_real_mp4_url(video_link)
        video_list.append((video_name,video_real_url))

    print(video_list)

    '''
    for循环串行
    '''
    # for each in video_list:
    #     download_video(each)

    p = Pool()
    '''
    使用apply_async的进程池
    '''
    # for each in video_list:
    #     p.apply_async(download_video,(each,))
    # p.close()
    # p.join()

    '''
    使用map的进程池
    '''
    p.map(download_video, video_list)

    print('over!!!')
    
    e_time = time.time()
    print('{} seconds cost...'.format(int(e_time - s_time)))