import requests
import os

def requests_get(**kw):
    #公司pc连接外网需要代理
    if 'USER' in os.environ and os.environ['USER'] == 'jmzhang':
        response = requests.get(**kw)
    else:
        response = requests.get(proxies={'https': '10.158.100.9:8080','http': '10.158.100.9:8080'},**kw)
    return response

def requests_post(**kw):
    #公司pc连接外网需要代理
    if 'USER' in os.environ and os.environ['USER'] == 'jmzhang':
        response = requests.post(**kw)
    else:
        response = requests.post(proxies={'https': '10.158.100.9:8080','http': '10.158.100.9:8080'},**kw)
    return response


if __name__ == '__main__':

    url = 'https://fn.int.net.nokia.com/tools/dslam_public/bm/cgi-bin/MaskMe.cgi'


    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.45 Safari/537.36'}

    param = {
        'action': 'get',
        'type': 'atc_status'
    }

    response = requests.get(url,headers=headers,params=param,timeout=5,verify=False)

    res_json = response.json()

    print(type(res_json))       # return a list
    print(res_json[0].keys())
    # print(res_json)


    
