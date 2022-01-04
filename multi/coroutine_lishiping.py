'''
使用异步io爬取梨视频科技页面的热门的3个视频
'''

import asyncio
import aiohttp, aiofiles
import os
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)  #抑制InsecureRequestWarning 打印
import time
from lxml import etree
import random
import re
from custom_requests import requests_get

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
    p = re.compile(r'https://(.*)/(\d+?)-(.*)')
    s = r'https://\g<1>/cont-' + video_id + r'-\g<3>'   #这里使用了反向引用，每个分组对应\g<分组id>
    video_link = p.sub(s,fake_video_link)

    return video_link

async def download_video(**video_dict):

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.93 Safari/537.36',
    }

    video_name = video_dict['name']
    url = video_dict['url']

    print(f'video name is {video_name}')
    print(f'video url is {url}')

    async with aiohttp.ClientSession() as session:
        if 'USERNAME' in os.environ and os.environ['USERNAME'] == 'jmzhang':
            async with session.get(url,headers=headers) as response:
                mp4_content = await response.read()
        else:
            async with session.get(url,headers=headers,proxy='http://10.158.100.9:8080') as response:
                mp4_content = await response.read()

    async with aiofiles.open(video_name,'wb') as fp:
        await fp.write(mp4_content)
    
    print(f'{video_name} download complete...')

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

        video_dict = {
            'name': video_name,
            'url': video_real_url
        }

        video_list.append(video_dict)

    print(video_list)

    #异步协程方式下载mp4文件
    loop = asyncio.get_event_loop()
    tasks = []
    for video_dict in video_list:
        c = download_video(**video_dict)
        task = loop.create_task(c)
        tasks.append(task)

    loop.run_until_complete(asyncio.wait(tasks))
    loop.close()

    print('over!!!')
    
    e_time = time.time()
    print('{} seconds cost...'.format(int(e_time - s_time)))
