import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)  #抑制InsecureRequestWarning 打印
import requests
import time
from multiprocessing import Pool
import os
import pandas as pd
from lxml import etree
from pprint import pprint


HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.45 Safari/537.36'}

def login_sls(username, password):
    '''
    登录sls
    '''

    url_login_test = 'https://smartlab-service.int.net.nokia.com/api/logintest'

    data = {
        'username': username,
        'password': password,
    }

    session = requests.Session()

    #发送第一个post请求，得到user 详细信息
    response = session.post(url=url_login_test,headers=HEADERS,data=data,timeout=5,verify=False)
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
    response = session.post(url=url_login,headers=HEADERS,data=data,timeout=5,verify=False)
    print('login sls response:', response.status_code)

    return session

def retrieve_ti_history_from_sls_mp(session,draw,search_window,ti_type):
    '''
    用于进程池获取ti list
    '''
    pid = os.getpid()
    print(f'start child process {pid}')

    url_bug_history = 'https://smartlab-service.int.net.nokia.com/ajaxATCStatisticInfo'
    start_index = draw*search_window
    data = {
        'draw': str(draw),
        'start': str(start_index),
        'length': str(search_window),
        'order_clumn': '0',
        'order': 'asc',
        'search': '',
        'releaseID': '',
        'buildID': '',
        'purpose2': '',
        'jobName': '',
        'ATCName': '',
        'runOnObjName': '',
        'frClassify': ti_type,
        'pt': '',
    }

    ti_list = []

    response = session.post(url=url_bug_history,headers=HEADERS,data=data,timeout=90,verify=False)
    ti_list = response.json()['data']
    print(len(ti_list))
    #print(ti_list)

    print(f'stop child process {pid}')
    return ti_list

all_ti_list = []
def mycallback(x):
    '''
    通过回调函数把进程池获取到的bug汇总到一个list里
    '''
    # print('mycallback is called with {}'.format(x))
    all_ti_list.extend(x)

def export_ti_list_to_excel(ti_list):
    '''
    把bug list输出到excel
    '''
    ti_id_list = []
    atc_name_list = []
    job_name_list = []
    job_number_list = []
    ti_type_list = []
    bug_id_list = []

    for ti in ti_list:
        ti_id_list.append(ti['id'])
        atc_name_list.append(ti['ATCName'])
        job_name_list.append(ti['parentPlatform'])
        job_number_list.append(ti['jobNum'])
        ti_type_list.append(ti['TIType'])
        bug_id_list.append(ti['frId'])

    d = {
    'Ti_Id': ti_id_list,
    'Atc_Name': atc_name_list,
    'Job_Name': job_name_list,
    'Job_Num': job_number_list,
    'TI_Type': ti_type_list,
    'Bug_Id': bug_id_list
    }

    df = pd.DataFrame(data=d)

    #use xlsxwriter to write xlsx
    sheet_name = 'TI List'
    writer = pd.ExcelWriter('ti_list.xlsx',engine='xlsxwriter')
    df.to_excel(writer,index=False,sheet_name=sheet_name)

    workbook  = writer.book
    worksheet = writer.sheets[sheet_name]
    format1 = workbook.add_format({'text_wrap': True,'border': 1})
    worksheet.set_column('A:A', 10, format1)
    worksheet.set_column('B:C', 50, format1)
    worksheet.set_column('D:F', 15, format1)
    writer.save()

def _create_url_from_job_info():
    '''
    根据ti的job name 和 job number 生成log所在的url
    '''

    pass

def download_atc_log_file(session,url,job_name,job_num):
    '''
    下载atc对应的output.xml
    '''

    print(f'url is {url}')
    file_name = f'{job_name}_{job_num}_output.xml'

    if os.path.exists(file_name):
        pass
    else:
        response = session.get(url,headers=HEADERS,timeout=600,verify=False)
        content = response.text
        with open(file_name,'w',encoding='utf-8') as fp:
            fp.write(content)
    
    return file_name

def retrieve_atc_step_info_from_log(file_name,atc_name):
    '''
    从output.xml中获取atc的执行步骤
    返回一个list
    '''
    print(f'file name is {file_name}')

    parser = etree.HTMLParser(encoding='utf-8')
    tree = etree.parse(file_name,parser=parser)
    case_messages = tree.xpath('//test[@name="{}"]//text()'.format(atc_name))

    # print(len(case_messages))
    case_messages = [message for message in case_messages if message != '\n']
    case_messages = [message for message in case_messages if message != '\r\n']

    #pprint(list(enumerate(case_messages)))
    print(len(case_messages))

    return case_messages

def retrieve_traffic_step_info_from_log(file_name):
    '''
    从detailed traffic log中取文本
    返回一个列表
    '''
    print(f'file name is {file_name}')

    parser = etree.HTMLParser(encoding='utf-8')
    tree = etree.parse(file_name,parser=parser)
    traffic_messages = tree.xpath('//text()')

    # print(len(case_messages))
    traffic_messages = [message for message in traffic_messages if message != '\n']
    traffic_messages = [message for message in traffic_messages if message != '\r\n']

    #pprint(list(enumerate(case_messages)))
    print(len(traffic_messages))

    return traffic_messages

if __name__ == '__main__':
    
    start_time = time.time()

    #for debug
    username = 'jieminbz'
    password = 'Jim#2345'
    batch_name = 'LSFX_NFXSD_FANTF_FWLTB_ONU_IOP_EONU_STAND_01'

    # session = login_sls(username, password)

    # ti_type_list = ['ATC','SW','ENV']
    # search_window = 20
    # with Pool() as p:
    #     for ti_type in ti_type_list:
    #         for i in range(10):
    #             p.apply_async(retrieve_ti_history_from_sls_mp,(session,i,search_window,ti_type),callback=mycallback)
    #     p.close()
    #     p.join()
    
    # print(len(all_ti_list))

    # export_ti_list_to_excel(all_ti_list)

    # output_xml_url = 'http://smartlab-service.int.net.nokia.com:9000/log/Fi-Hardening_and_CFT/2203.029/LSFX_NFXSE_FANTF_FGLTB_GPON_EONUAV_WEEKLY_02/SB_Logs_5B94-atxuser-Jan03051003_L2FWD/ROBOT/output.xml'

    # file_name = download_atc_log_file(session, output_xml_url, 'LSFX_NFXSE_FANTF_FGLTB_GPON_EONUAV_WEEKLY_02', '34')

    # #从excel中先挑前10个
    # df = pd.read_excel('ti_list.xlsx',engine='openpyxl')
    # case_name_list = [case_name for case_name in df.loc[0:10,'Atc_Name']]
    # # print(df.loc[0:10,'Atc_Name'])

    #for debug only
    #file_name = 'nglt-c_output.xml'
    file_name = 'traffic_test.html'
    case_name_list = ['MGMT_BP_COUNTER_01']
    res = []
    # with open('corpus.txt','w',encoding='utf-8') as fp:
    #     for case_name in case_name_list:
    #         #res.append(case_name + '\n' + str(retrieve_atc_step_info_from_log(file_name,case_name)) + '\n')
    #         case_steps = retrieve_atc_step_info_from_log(file_name,case_name)
    #         for num, line in enumerate(case_steps):
    #             res.append('^^^' + str(num) + ' : ' + line + '###\n')
    #     fp.writelines(res)
    
    with open('corpus_traffic.txt','w',encoding='utf-8') as fp:
        traffic_steps = retrieve_traffic_step_info_from_log(file_name)
        for num, line in enumerate(traffic_steps):
            res.append('^^^' + str(num) + ' : ' + line + '###\n')
        fp.writelines(res)

    #debug end here

    # res = []
    # with open('corpus.txt','w',encoding='utf-8') as fp:
    #     for case_name in case_name_list:
    #         res.append(case_name + '\n' + str(retrieve_atc_step_info_from_log(file_name,case_name)) + '\n')
    #     fp.writelines(res)

    # print(res)

    print("cost %d seconds" % int(time.time() - start_time))

