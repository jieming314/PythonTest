import logging
import requests
import os
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)  #抑制InsecureRequestWarning 打印
from custom_requests import session_post, session_get
import json
import pandas as pd
import datetime

'''
自动填写TI
'''

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.45 Safari/537.36'}

def login_sls(username, password):
    '''
    根据username和password登录sls, 返回一个session对象和包含user详细信息的字典
    '''
    url_login_test = 'https://smartlab-service.int.net.nokia.com/api/logintest'
    data = {
        'username': username,
        'password': password,
    }

    session = requests.Session()

    #发送第一个post请求，得到user 详细信息
    response = session_post(session,url=url_login_test,headers=HEADERS,data=data,timeout=5,verify=False)
    print(response.status_code)
    login_detail_dict = response.json()  # 返回一个字典
    login_detail_dict.pop('auth_status')
    login_detail_dict.pop('auth_level')
    login_detail_dict.pop('seq_nbr')
    login_detail_dict.pop('result')

    # print(response.json())
    # print(type(response.json()))

    url_login = 'https://smartlab-service.int.net.nokia.com/ajax/login_session'
    data = {
        'level': 'trusted',
        'timezone': 'Asia/Shanghai',
    }
    data.update(login_detail_dict)
    data['short_name'] = login_detail_dict['username']
    # print(data)
    # 发送第二个post请求，用来登录
    response = session_post(session,url=url_login,headers=HEADERS,data=data,timeout=5,verify=False)
    print(response.status_code)

    return session

def get_batch_ti_page(session,batch_name):
    '''
    根据输入的batch name获取这个batch的TI结果
    只获取最后一次跑的batch结果
    '''
    url_search_batch = 'https://smartlab-service.int.net.nokia.com/server_processing/'

    data = {
        'draw': '10',
        'start': '0',
        'length': '10',
        'order_clumn': '0',
        'order': 'asc',
        'search': batch_name,
        'job': '',
        'product': '',
        'release': '',
        'build': '',
        'status': '',
        'requestor': '',
        'mark': '',
        'jobNum': '',
        'target': '',
        'group': '',
        'purpose': '',
        'domain': '',
        'month': '',
        'testCS': ''
    }

    #获取第一个匹配batch name的batch 信息
    response = session_post(session,url=url_search_batch,headers=HEADERS,data=data,timeout=5,verify=False)
    print(response.status_code)

    batch_result_dict = response.json()['data'][0]
    job_num = batch_result_dict.get('jobNum')
    job_coverage = batch_result_dict.get('Coverage')
    job_buildID = batch_result_dict.get('BuildID')

    url_ti_page = 'https://smartlab-service.int.net.nokia.com/atcReport'
    params = {
        'job_name': batch_name,
        'job_num': job_num,
        'job_coverage': job_coverage,
        'buildID': job_buildID
    }

    #获取batch的TI 列表
    response = session_get(session,url=url_ti_page,headers=HEADERS,params=params,timeout=5,verify=False)
    print(response.status_code)

    #获取所有的ti
    ti_list = eval(response.text)['data']
    print(ti_list[0])
    # print(len(ti_list))
    # print(ti_list[0].keys())

    return ti_list

def auto_ti(session, ti_list):
    '''
    填写已知TI
    脚本会打开本地一个记录已知TI的excel，根据case name，fail step 和 error message进行匹配
    如果匹配成功，则自动填写TI
    '''
    
    excel_name = 'auto_ti.xlsx'
    sheet_name = 'bug list'

    if os.path.exists(excel_name):
        '''
        如果excel文件存在，更新并填写已知TI
        '''
        df = pd.read_excel(excel_name,sheet_name=sheet_name)

        for ti in ti_list:
            #已经填好的TI，尝试更新excel
            #如果找到相同的case名，失败步骤和error info，更新之；如果找不到，添加到末尾
            if ti['frId']['value'] and ti['frClassify']:
                atc_name = ti['ATCName']
                fail_step = ti['failStep']
                error_info = ti['errorInfo']
                if df.query('ATC_Name == atc_name and Fail_Step == fail_step and Error_Info == error_info'):
                    pass
                else:
                    pass


                df.loc[df.ATC_Name == atc_name,'Fail_Step'] = ti['failStep']
            #未填TI，在excel中查找，如果能match就自动填上
            else:
                pass



    else:
        '''
        如果excel不存在，创建这个文件，并把本次的所有已知TI填进去
        '''
        atc_name_list = []
        fail_step_list = []
        error_info_list = []
        fr_id_list = []
        fr_type_list =[]
        job_name_list = []
        last_update_list = []

        for ti in ti_list:
            if ti['frId']['value'] and ti['frClassify']:
                atc_name_list.append(ti['ATCName'])
                fail_step_list.append(ti['failStep'])
                error_info_list.append(ti['errorInfo'])
                fr_id_list.append(ti['frId']['value'])
                fr_type_list.append(ti['frClassify'])
                job_name_list.append(ti['jobName'])
                current_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                last_update_list.append(current_time)

        d = {
            'ATC_Name': atc_name_list,
            'Fail_Step': fail_step_list,
            'Error_Info': error_info_list,
            'FR_ID': fr_id_list,
            'FR_Type': fr_type_list,
            'Job_Name': job_name_list,
            'Last_Update': last_update_list
        }

        df = pd.DataFrame(data=d)
        writer = pd.ExcelWriter(excel_name,engine='xlsxwriter')
        df.to_excel(writer,index=False,sheet_name=sheet_name)

        workbook  = writer.book
        worksheet = writer.sheets[sheet_name]

        format1 = workbook.add_format({'text_wrap': True,'border': 1})

        worksheet.set_column('A:A', 25, format1)
        worksheet.set_column('B:B', 40, format1)
        worksheet.set_column('C:C', 70, format1)
        worksheet.set_column('D:E', 12, format1)
        worksheet.set_column('F:F', 30, format1)
        worksheet.set_column('G:G', 20, format1)

        writer.save()


if __name__ == '__main__':

    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.45 Safari/537.36'}
    # username = input('please input your csl:')
    # password = input('please input your password:')
    # batch_name = input('please input batch name:')

    #for debug
    username = 'jieminbz'
    password = 'Jim#2345'
    batch_name = 'LSFX_NFXSD_FANTF_FWLTB_ONU_IOP_EONU_STAND_01'

    session = login_sls(username, password)

    ti_list = get_batch_ti_page(session, batch_name)

    auto_ti(session, ti_list)

    # #get ti page
    # url_ti = 'https://smartlab-service.int.net.nokia.com/atcReport'
    # params = {
    #     'job_name': 'LSFX_NFXSD_FANTF_FWLTB_ONU_IOP_EONU_STAND_01',
    #     'job_num': '5',
    #     'job_coverage': 'Weekly',
    #     'groupID': '',
    #     'username': 'jieminbz',
    #     '_': '1640311330966',
    # }

    # response = session_get(session,url=url_ti,headers=HEADERS,params=params,timeout=5,verify=False)
    # print(response.status_code)

    # #获取所有的ti
    # ti_list = eval(response.text)['data']
    # # print(ti_list)
    # print(len(ti_list))
    # print(ti_list[0].keys())

    #填写一个ti
    url_submit = 'https://smartlab-service.int.net.nokia.com/api/frSubmit'

    TI_1 = {"id":"34434816","frId":"BBN-45705","frClassify":"ATC","frNewOrOld":"New","frDesc":"","shortname":"jieminbz"}
    TI_2 = {"id":"34434817","frId":"BBN-45705","frClassify":"ATC","frNewOrOld":"New","frDesc":"","shortname":"jieminbz"}
    TI_list = []
    TI_list.append(TI_1)
    TI_list.append(TI_2)

    data = {
        "username":"jieminbz",
        "jobName":"LSFX_NFXSD_FANTF_FWLTB_ONU_IOP_EONU_STAND_01",
        "jobNum":"5",
        "groupID":"",
        "tiSummary":"___",
        "syncTIA": TI_list
    }

    #提交的是json数据，需要转换一下
    data = json.dumps(data)
    response = session_post(session,url=url_submit,headers=HEADERS,data=data,timeout=5,verify=False)
    print(response.status_code)

    print("over!!!")
