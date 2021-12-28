import logging
from numpy.core.arrayprint import IntegerFormat
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
还需要安装 xlsxwriter 和 openpyxl
'''

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.45 Safari/537.36'}

#below lists store TI info will be added to excel
ATC_NAME_LIST = []
FAIL_STEP_LIST = []
ERROR_INFO_LIST = []
FR_ID_LIST = []
FR_TYPE_LIST =[]
JOB_NAME_LIST= []
LAST_UPDATE_LIST = []


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
    print('login sls response:', response.status_code)

    return session

def get_batch_ti_page(session,batch_name):
    '''
    根据输入的batch name获取这个batch的TI结果
    只获取最后一次跑的batch结果
    '''
    url_search_batch = 'https://smartlab-service.int.net.nokia.com/server_processing/'

    data = {
        'draw': '1',
        'start': '0',
        'length': '10',
        'order_clumn': '0',
        'order': 'asc',
        'search': batch_name,
        'job': '',
        'product': '',
        'release': '',
        'build': '',
        'status': 'C',
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
    print('get all batch result response: ', response.status_code)

    batch_result_dict = response.json()['data'][0]

    print(batch_result_dict)

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
    print('detail ti page response: ', response.status_code)

    #获取所有的ti
    response_text = response.text.replace('null','" "')
    ti_list = eval(response_text)['data']
    print('all ti number: ', len(ti_list))
    # print(ti_list[0])
    # print(ti_list[0].keys())

    return job_num, ti_list

def update_ti_info(session, ti_list):
    '''
    脚本会打开本地一个记录已知TI的excel，根据case name，fail step 和 error message进行匹配
    此函数会更新这个excel文件并return一个需要自动填写的ti列表
    '''

    excel_name = 'auto_ti_%s.xlsx' % username
    sheet_name = 'bug list'
    ti_list_to_submit = []

    if os.path.exists(excel_name):
        '''
        如果excel文件存在，更新并填写已知TI
        '''
        df = pd.read_excel(excel_name,sheet_name=sheet_name,engine='openpyxl')
        df.fillna(value='')

        for ti in ti_list:
            '''
            先判断一个TI是否已经被分析过(看fr id 和 fr type是否有值)
                如果是已知TI，匹配case名，失败步骤和error info，
                    如果匹配到了，更新FR_ID,FR_Type, Job_Name和Last_Update
                    如果匹配不到，把此TI添加到excel末尾
                如果TI还未被分析过，匹配case名，失败步骤和error info
                    如果匹配到了，记录下此TI，需要使用post请求填写的
                    如果匹配不到，跳过
            '''
            atc_name = ti['ATCName']
            fail_step = ti['failStep']
            error_info = ti['errorInfo']
            fr_id = ti['frId']['value']
            fr_type = ti['frClassify']
            job_name = ti['jobName']
            atc_id = ti['id']

            match_flag = any( (df['ATC_Name'] == atc_name) & (df['Fail_Step'] == fail_step) & (df['Error_Info'] == error_info))
            #已填TI
            if fr_id and fr_type:
                #查找excel里是否有满足添加的行（能match上的TI），有的话更新之，没有的话，添加之
                if match_flag:
                    '''
                    这里还是有问题，应该更新满足上述条件的row
                    '''
                    print('Filled TI: ',atc_name, ' found in excel!')
                    index_id = df.loc[(df['ATC_Name'] == atc_name) & (df['Fail_Step'] == fail_step) & (df['Error_Info'] == error_info),:].index.tolist()[0]
                    print(index_id)
                    df.loc[index_id,'FR_ID'] = fr_id
                    df.loc[index_id,'FR_Type'] = fr_type
                    df.loc[index_id,'Job_Name'] = job_name
                    df.loc[index_id,'Last_Update'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                else:
                    print('Filled TI: ',atc_name, 'not found in excel!')
                    _add_ti_to_df_list(ti)
            #未填TI，在excel中查找，如果能match就自动填上，match不到就跳过
            else:
                if match_flag:
                    print('Unfilled TI: ',atc_name, ' found in excel!')
                    #如果在excel中match到，记录下此TI，需要自动提交
                    index_id = df.loc[(df['ATC_Name'] == atc_name) & (df['Fail_Step'] == fail_step) & (df['Error_Info'] == error_info),:].index.tolist()[0]
                    fr_type = df.loc[index_id,'FR_Type']
                    fr_id = df.loc[index_id,'FR_ID']
                    ti_author = ti['user']
                    submit_ti = {"id":atc_id,"frId":fr_id,"frClassify":fr_type,"frNewOrOld":"Old","frDesc":"","shortname":ti_author}
                    ti_list_to_submit.append(submit_ti)
                else:
                    # print('Unfilled TI: ',atc_name, 'not found in excel!')
                    pass
        
        #往原来的df尾部添加数据
        d = {
            'ATC_Name': ATC_NAME_LIST,
            'Fail_Step': FAIL_STEP_LIST,
            'Error_Info': ERROR_INFO_LIST,
            'FR_ID': FR_ID_LIST,
            'FR_Type': FR_TYPE_LIST,
            'Job_Name': JOB_NAME_LIST,
            'Last_Update': LAST_UPDATE_LIST
        }

        df2 = pd.DataFrame(data=d)
        df = df.append(df2,ignore_index=True)
        # print(df)

        #更新本地的excel文件
        _write_df_data_to_excel(df,excel_name=excel_name,sheet_name=sheet_name)

        return ti_list_to_submit

    else:
        '''
        如果excel不存在，创建这个文件，并把本次的所有已知TI填进去
        '''
        for ti in ti_list:
            _add_ti_to_df_list(ti)

        d = {
            'ATC_Name': ATC_NAME_LIST,
            'Fail_Step': FAIL_STEP_LIST,
            'Error_Info': ERROR_INFO_LIST,
            'FR_ID': FR_ID_LIST,
            'FR_Type': FR_TYPE_LIST,
            'Job_Name': JOB_NAME_LIST,
            'Last_Update': LAST_UPDATE_LIST
        }

        df = pd.DataFrame(data=d)
        _write_df_data_to_excel(df,excel_name=excel_name,sheet_name=sheet_name)

        return None

def _add_ti_to_df_list(ti):
    '''
    把已经分析过的TI内容填进用于生成df的各个list中
    '''
    global ATC_NAME_LIST, FAIL_STEP_LIST, ERROR_INFO_LIST, FR_ID_LIST, FR_TYPE_LIST, JOB_NAME_LIST,LAST_UPDATE_LIST
    if ti['frId']['value'] and ti['frClassify']:
        ATC_NAME_LIST.append(ti['ATCName'])
        FAIL_STEP_LIST.append(ti['failStep'])
        ERROR_INFO_LIST.append(ti['errorInfo'])
        FR_ID_LIST.append(ti['frId']['value'])
        FR_TYPE_LIST.append(ti['frClassify'])
        JOB_NAME_LIST.append(ti['jobName'])
        current_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        LAST_UPDATE_LIST.append(current_time)

def _write_df_data_to_excel(df,excel_name='auto_ti.xlsx',sheet_name='bug list'):
    writer = pd.ExcelWriter(excel_name,engine='xlsxwriter')
    df.to_excel(writer,sheet_name=sheet_name,index=False)

    workbook  = writer.book
    worksheet = writer.sheets[sheet_name]

    #设置格式
    format1 = workbook.add_format({'text_wrap': True,'border': 1})
    worksheet.set_column('A:A', 25, format1)
    worksheet.set_column('B:B', 40, format1)
    worksheet.set_column('C:C', 70, format1)
    worksheet.set_column('D:E', 12, format1)
    worksheet.set_column('F:F', 30, format1)
    worksheet.set_column('G:G', 20, format1)

    writer.save()

def auto_submit_ti(batch_name,job_num,ti_list,user):
    '''
    根据ti_list中的内容自动填写ti
    '''
    url_submit = 'https://smartlab-service.int.net.nokia.com/api/frSubmit'

    data = {
        "username":user,
        "jobName":batch_name,
        "jobNum":job_num,
        "groupID":"",
        "tiSummary":"___",
        "syncTIA": ti_list
    }

    #提交的是json数据，需要转换一下
    data = json.dumps(data)
    response = session_post(session,url=url_submit,headers=HEADERS,data=data,timeout=5,verify=False)
    print('submit ti response: ', response.status_code)


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

    job_num, ti_list = get_batch_ti_page(session, batch_name)

    ti_list_to_submit = update_ti_info(session, ti_list)
    print("known TI to submit:\n", ti_list_to_submit)

    if ti_list_to_submit:
        auto_submit_ti(batch_name,job_num,ti_list_to_submit,username)

    print("over!!!")
