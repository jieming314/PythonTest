import requests
import os
from custom_requests import requests_post

'''
爬取kfc所有上海餐厅的地址
'''

if __name__=='__main__':

    url = 'http://www.kfc.com.cn/kfccda/ashx/GetStoreList.ashx'

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.93 Safari/537.36'
    }

    data = {
        'cname': '上海',
        'pid': '',
        'pageIndex': '1',
        'pageSize': '10'
    }

    param = {
        'op': 'cname'
    }

    response = requests_post(url=url, headers=headers, data=data, params=param,timeout=5) #第一次post请求，主要用来获取餐厅数量
    kfc_stores = response.text
    kfc_stores = kfc_stores.replace('null','" "') #把字典中的null替换为空字符串，否正eval会报错
    kfc_store_dict = eval(kfc_stores)
    #print(kfc_store_dict['Table'])
    rows = kfc_store_dict['Table'][0]['rowcount'] #获取餐厅数量

    data['pageSize'] = str(rows)
    response2 = requests_post(url=url, headers=headers, data=data, params=param,timeout=5)
    kfc_stores = response2.text
    kfc_stores = kfc_stores.replace('null','" "')
    kfc_store_dict = eval(kfc_stores)
    kfc_store_list = kfc_store_dict['Table1']
    store_name_list = []
    write_list = []

    with open('./kfc_stores.txt','w', encoding='utf-8') as fp:
        for each in kfc_store_list:
            store_name = each['storeName']
            if store_name not in store_name_list:
                store_name_list.append(store_name)
                store_address = each['addressDetail']
                write_list.append(f'店面: {store_name}, 地址: {store_address}\n')
        store_num = len(store_name_list)
        write_list.insert(0, f'There are {store_num} stores in Shanghai\n')
        fp.writelines(write_list)

    print('over!!!')