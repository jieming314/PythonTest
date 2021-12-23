import requests
import json
import os
from custom_requests import requests_post

'''
爬取国药监局(http://scxk.nmpa.gov.cn:81/xk)化妆品生产许可平台上注册的企业信息
'''


if __name__=='__main__':

    url = 'http://scxk.nmpa.gov.cn:81/xk/itownet/portalAction.do'

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.93 Safari/537.36'
    }

    data = {
        'on': 'true',
        'page': '1',
        'pageSize': '15',
        'productName': '',
        'conditionType': '1',
        'applyname': '',
        'applysn': ''
    }

    param = {
        'method': 'getXkzsList'
    }

    #企业信息是通过ajax请求得到的, 这里只爬取了第一个页面上的15个
    response = requests_post(url=url, headers=headers, data=data, params=param,timeout=5)
    response_json = response.json()    #这里返回一个字典
    makeup_ent_gen_list = response_json['list']
    makeup_ent_id_list = [each['ID'] for each in makeup_ent_gen_list]

    param = {
        'method': 'getXkzsById'
    }

    make_ent_detail_list = []
    for each in makeup_ent_id_list:
        data2 = {
            'id': each
        }

        response = requests_post(url=url,data=data2,headers=headers,params=param,timeout=5).json()
        make_ent_detail_list.append(response)

    with open('./makeup_ents.json','w') as fp:
        json.dump(make_ent_detail_list,fp,ensure_ascii=False,indent=4)  #这里加上ensure_ascii=False,indent=4

    print('over!!!')
