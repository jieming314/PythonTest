from sqlite3 import paramstyle
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)  #抑制InsecureRequestWarning 打印
import requests
import time
from multiprocessing import Pool
import os
import pandas as pd
from lxml import etree
from pprint import pprint
import re
import pandas as pd
import shutil


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

def _retrieve_ti_history_from_sls_mp(session,draw,search_window,ti_type,release_id=''):
    '''
    用于进程池获取ti list
    ti_type: SW or ATC or ENV
    release_id: '22.03'
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
        'releaseID': release_id,
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
def _mycallback(x):
    '''
    通过回调函数把进程池获取到的bug汇总到一个list里
    '''
    # print('mycallback is called with {}'.format(x))
    all_ti_list.extend(x)

parent_dir ='ML_LOG'
def _export_history_ti_list_to_excel(ti_list):
    '''
    把从sls得到的history bug list输出到excel
    Column names:
    TI_ID, ATC_NAME, JOB_NAME, JOB_NUM, TI_TYPE, BUG_ID, BATCH_NAME, DOMAIN_NAME
    '''
    ti_id_list = []
    atc_name_list = []
    job_name_list = []
    job_number_list = []
    ti_type_list = []
    bug_id_list = []
    release_id_list = []
    batch_name_list = []

    for ti in ti_list:
        ti_id_list.append(ti['id'])
        atc_name_list.append(ti['ATCName'])
        job_name_list.append(ti['parentPlatform'])
        job_number_list.append(ti['jobNum'])
        ti_type_list.append(ti['TIType'])
        bug_id_list.append(ti['frId'])
        release_id_list.append(ti['releaseID'])
        batch_name_list.append(ti['batchName'])

    d = {
    'TI_ID': ti_id_list,
    'JOB_NAME': job_name_list,
    'JOB_NUM': job_number_list,
    'ATC_NAME': atc_name_list,
    'TI_TYPE': ti_type_list,
    'BUG_ID': bug_id_list,
    'RELEASE_ID': release_id_list,
    'BATCH_NAME': batch_name_list
    }

    df = pd.DataFrame(data=d)

    #use xlsxwriter to write xlsx
    file_name = 'history_ti_list_{}.xlsx'.format(time.strftime('%Y%m%d'))
    sheet_name = 'TI List'
    writer = pd.ExcelWriter(file_name, engine='xlsxwriter')
    df.to_excel(writer,index=False,sheet_name=sheet_name)

    workbook  = writer.book
    worksheet = writer.sheets[sheet_name]
    format1 = workbook.add_format({'text_wrap': True,'border': 1,'align': 'left'})
    worksheet.set_column('A:A', 10, format1)
    worksheet.set_column('B:B', 45, format1)
    worksheet.set_column('C:C', 10, format1)
    worksheet.set_column('D:D', 45, format1)
    worksheet.set_column('E:F', 10, format1)
    worksheet.set_column('G:G', 12, format1)
    worksheet.set_column('H:H', 35, format1)
    writer.save()

    #move file to LOG path
    if not os.path.exists(parent_dir):
        os.mkdir(parent_dir)
    shutil.move(file_name,os.path.join(parent_dir,file_name))

    return file_name

def retrieve_history_ti(session, ti_type_list=['SW', 'ATC', 'ENV'], ti_nums=20, release=''):
    '''
    从sls上获取history ti entries, 输出一个excel表格
    ti_nums 是每类TI的总数
    '''

    search_window = 20
    search_round = int(ti_nums/search_window)
    with Pool() as p:
        for ti_type in ti_type_list:
            for i in range(search_round):
                p.apply_async(_retrieve_ti_history_from_sls_mp,(session,i,search_window,ti_type),callback=_mycallback)
        p.close()
        p.join()

    output_file = _export_history_ti_list_to_excel(all_ti_list)

    return output_file

def generate_input_excel_for_ml(session, input_file):
    '''
    根据input file 生成 ml 的input excel
    Column names:
    JobName_JobNum_CaseName, TI_Type, Bud_ID, Robot_Log, Traffic_Log, Trace_Debug
    '''

    # df = pd.read_excel(input_file,engine='openpyxl')
    df = pd.read_excel(os.path.join(parent_dir,input_file),engine='openpyxl')
    df.dropna(subset=['JOB_NAME','JOB_NUM','ATC_NAME','TI_TYPE','BUG_ID'],inplace=True)
    df.drop_duplicates(subset=['JOB_NAME','JOB_NUM','ATC_NAME'],inplace=True)
    df.reset_index()
    
    ti_name_list = []
    ti_type_list =[]
    bug_id_list = []
    robot_log_list = []
    traffic_log_list =[]
    trace_debug_list = []

    for index, row in df.iterrows():
        job_name = row['JOB_NAME']
        job_num = str(row['JOB_NUM'])
        atc_name = row['ATC_NAME']
        ti_type = row['TI_TYPE']
        bug_id = row['BUG_ID']
        batch_name = row['BATCH_NAME']
        domain_name = row['DOMAIN_NAME']
        case_steps = []
        traffic_steps = []

        robot_log_url = _create_robot_url_of_ti(session,job_name,job_num,batch_name,domain_name)
        if robot_log_url:
            xml_file = _download_robot_xml_file(session, robot_log_url, job_name, job_num, batch_name, domain_name)
            if xml_file:
                case_steps = _retrieve_atc_step_from_log(xml_file, atc_name)
            traffic_log = _download_atc_traffic_file(session, robot_log_url, atc_name)
            if traffic_log:
                traffic_steps = _retrieve_traffic_step_from_log(traffic_log)

        ti_name = job_name + '_' + job_num + '_' + atc_name
        ti_name_list.append(ti_name)
        ti_type_list.append(ti_type)
        bug_id_list.append(bug_id)
        robot_log_list.append(case_steps)
        traffic_log_list.append(traffic_steps)

    d = {
    'TI_NAME': ti_name_list,
    'TI_TYPE': ti_type_list,
    'BUG_ID': bug_id_list,
    'ROBOT_LOG': robot_log_list,
    'TRAFFIC_LOG': traffic_log_list
    }

    new_df = pd.DataFrame(data=d)
    print('new df shape is %s' % str(new_df.shape))
    print('generate excel for ml...')

    #use xlsxwriter to write xlsx
    file_name = 'ti_list_for_ml_{}.xlsx'.format(time.strftime('%Y%m%d'))
    sheet_name = 'TI List'
    writer = pd.ExcelWriter(file_name, engine='xlsxwriter')
    new_df.to_excel(writer,index=False,sheet_name=sheet_name)

    workbook  = writer.book
    worksheet = writer.sheets[sheet_name]
    format1 = workbook.add_format({'text_wrap': True,'border': 1,'align': 'left'})
    worksheet.set_column('A:A', 40, format1)
    worksheet.set_column('B:C', 10, format1)
    worksheet.set_column('D:E', 100, format1)
    writer.save()
    print('excel for ml completed...')

    if not os.path.exists(parent_dir):
        os.mkdir(parent_dir)
    shutil.move(file_name,os.path.join(parent_dir,file_name))

    return file_name

def _create_robot_url_of_ti(session,job_name,job_num,batch_name='',domain_name=''):
    '''
    根据job name, job num, batch name, domain name 生成ROBOT路径(url)
    '''

    url_job_result = 'https://smartlab-service.int.net.nokia.com/ResultDetails/'
    log_url = ''

    data = {
        'jobName': job_name,
        'jobNum': str(job_num),
    }

    job_result_list = []
    response = session.post(url=url_job_result,headers=HEADERS,data=data,timeout=90,verify=False)
    job_result_list = response.json()['data']

    #print(job_result_list)

    for job_result in job_result_list:
        job_domain_name = job_result.get('Coverage', '')
        job_batch_name =  job_result.get('batchName', '')
        if job_domain_name == domain_name and job_batch_name == batch_name:
            log_url = job_result['Logs']
            break
    else:
        print(f'cannot find log path for job:{job_name}, num:{job_num}, domain_name:{domain_name}, batch_name:{batch_name}')
    
    #print('log url is %s' % log_url)
    return log_url

def _download_robot_xml_file(session,url,job_name,job_num,batch_name='',domain_name=''):
    '''
    下载ti所在的output.xml
    '''

    robot_out_path = url + 'ROBOT'
    output_file_name = job_name + '_' + job_num + '_' + batch_name + '_' + domain_name + '_output.xml'
    target_file = robot_out_path + '/output.xml'

    # print(robot_out_path)
    # print(output_file_name)
    print(f'target robot output xml is {target_file}')

    if os.path.exists(os.path.join(parent_dir,output_file_name)):
        print('target robot output xml alread exist, skip downloading')
    else:
        print('start downloading target robot output xml ...')
        try:
            response = session.get(target_file,headers=HEADERS,timeout=600,verify=False)
            content = response.text
            with open(output_file_name,'w',encoding='utf-8') as fp:
                fp.write(content)
            print('downloading output xml completed')
            if not os.path.exists(parent_dir):
                os.mkdir(parent_dir)
            shutil.move(output_file_name,os.path.join(parent_dir,output_file_name))
        except Exception as inst:
            print('download output xml failed, due to %s' % inst)
            return None

    return output_file_name

def _download_atc_traffic_file(session,url,case_name):
    '''
    下载ti对应的traffic log
    '''
    robot_out_path = url + 'ROBOT'
    response = session.get(robot_out_path,headers=HEADERS,timeout=30,verify=False)
    content = response.text

    #匹配traffic log所在的目录名称
    traffic_dir_name = ''
    p = re.compile(r'</td><td><a href="(TRAFFIC-[A-Z][a-z]{2}[0-9]{8})/">')
    m = p.search(content)
    if m:
        traffic_dir_name = m.group(1)
    else:
        print('cannot find traffic dir')
        return None

    traffic_log_path = robot_out_path + '/' + traffic_dir_name
    response = session.get(traffic_log_path,headers=HEADERS,timeout=30,verify=False)
    content = response.text

    #匹配case 的 traffic log
    match_pattern = r'</td><td><a href="(.*%s\.html)">' % case_name.upper()
    p = re.compile(match_pattern)
    m = p.search(content)
    if m:
        traffic_log_name = m.group(1)
    else:
        print('cannot match correspoinding traffic log for case %s' % case_name.upper())
        return None

    traffic_log_url = traffic_log_path + '/' + traffic_log_name
    if os.path.exists(os.path.join(parent_dir,traffic_log_url)):
        print('target traffic log alread exist, skip downloading')
    else:
        print(f'start to download traffic log {traffic_log_url}')
        try:
            response = session.get(traffic_log_url,headers=HEADERS,timeout=300,verify=False)
            content = response.text
            with open(traffic_log_name,'w',encoding='utf-8') as fp:
                fp.write(content)
            print('download traffic log completed')
            if not os.path.exists(parent_dir):
                os.mkdir(parent_dir)
            shutil.move(traffic_log_name,os.path.join(parent_dir,traffic_log_name))
        except Exception as inst:
                print('download traffic log failed, due to %s' % inst)
                return None

    return traffic_log_name

def _download_atc_trace_debug_file():
    '''
    下载trace debug 文件(文件是batch 级别的，还需要后续处理)
    '''
    pass

def _retrieve_atc_step_from_log(file_name,atc_name):
    '''
    从output.xml中获取atc的执行步骤
    返回一个list
    '''
    print('start to retrieve %s steps from file %s' % (atc_name, file_name) )

    parser = etree.HTMLParser(encoding='utf-8')
    tree = etree.parse(os.path.join(parent_dir,file_name),parser=parser)
    case_messages = tree.xpath('//test[@name="{}"]//text()'.format(atc_name))

    # print(len(case_messages))
    case_messages = [message for message in case_messages if message != '\n']
    case_messages = [message for message in case_messages if message != '\r\n']

    #pprint(list(enumerate(case_messages)))
    print(len(case_messages))

    return case_messages

def _retrieve_traffic_step_from_log(file_name):
    '''
    从detailed traffic log中取文本
    返回一个列表
    '''
    print(f'file name is {file_name}')

    parser = etree.HTMLParser(encoding='utf-8')
    tree = etree.parse(os.path.join(parent_dir,file_name),parser=parser)
    traffic_messages = tree.xpath('//text()')

    # print(len(case_messages))
    traffic_messages = [message for message in traffic_messages if message != '\n']
    traffic_messages = [message for message in traffic_messages if message != '\r\n']

    #pprint(list(enumerate(case_messages)))
    print(len(traffic_messages))

    return traffic_messages






def convert_step_messages_into_words(step_messages):
    '''
    把step messages 变化成 words
    step messages 是一个列表，里面的元素可能是一句长句，例如 configure vlan id ${VLAN['crb_vid']} ipv4-mcast-ctrl
    此函数把长句拆分成words, ['configure', 'vlan', 'id', "${VLAN['crb_vid']}", 'ipv4-mcast-ctrl']
    '''
    res_list = []

    for message in step_messages:
        message = message.replace(r'\t',' ')
        message = message.replace(r',', '')
        message = message.replace(r'\n',' ')
        message = message.replace(r'\r\n',' ')
        message = message.replace(r'&nbsp',' ')
        word_list = message.split()
        res_list.extend(word_list)

    print(len(res_list))
    return res_list

if __name__ == '__main__':
    
    start_time = time.time()

    #for debug
    username = 'jieminbz'
    password = 'Jim#2345'
    batch_name = 'LSFX_NFXSD_FANTF_FWLTB_ONU_IOP_EONU_STAND_01'

    session = login_sls(username, password)

    #tmp_excel = retrieve_history_ti(session)

    generate_input_excel_for_ml(session,'history_ti_list_20220328.xlsx')

    # ti_type_list = ['ATC','SW','ENV']
    # search_window = 20
    # with Pool() as p:
    #     for ti_type in ti_type_list:
    #         for i in range(10):
    #             p.apply_async(retrieve_ti_history_from_sls_mp,(session,i,search_window,ti_type),callback=mycallback)
    #     p.close()
    #     p.join()
    
    # print(len(all_ti_list))

    # export_history_ti_list_to_excel(all_ti_list)

    #for debug only
    # url = _create_robot_url_of_ti(session, 'CHERLAB_RVXSA_RANTC_RPOWA_weekly_38.52', '167', 'RVXSA_RANTC_RPOWA_COPPER_MANAGEMENT_weekly', '')
    # _download_robot_xml_file(session, url, 'CHERLAB_RVXSA_RANTC_RPOWA_weekly_38.52', '167', 'RVXSA_RANTC_RPOWA_COPPER_MANAGEMENT_weekly', '')
    # _download_atc_traffic_file(session, url, 'ALARMMGMT_NCY_06')

    #debug end


    # #从excel中先挑前10个
    # df = pd.read_excel('ti_list.xlsx',engine='openpyxl')
    # case_name_list = [case_name for case_name in df.loc[0:10,'Atc_Name']]
    # # print(df.loc[0:10,'Atc_Name'])

    #for debug only
    # atc_output_name = 'CHERLAB_RVXSA_RANTC_RPOWA_weekly_38.52_167_RVXSA_RANTC_RPOWA_COPPER_MANAGEMENT_weekly__output.xml'
    # ti_name_list = ['ALARMMGMT_NCY_06','MGMT_NCY_BULK_ALARM_MEMORY_LEAK']
    # raw_corpus_file_name = 'raw_corpus_test.txt'
    # corpus_file_name = 'corpus_test.txt'
    # res1 = []
    # res2 = []
    # for ti_name in ti_name_list:
    #     case_steps = retrieve_atc_step_from_log(atc_output_name, ti_name)
    #     prcessed_case_steps = convert_step_messages_into_words(case_steps)
    #     for num, line in enumerate(case_steps):
    #         res1.append('^^^' + str(num) + ' : ' + line + '###\n')
    #     for num, line in enumerate(prcessed_case_steps):
    #         res2.append(str(num) + ' : ' + line + '\n')

    # with open(raw_corpus_file_name,'w',encoding='utf-8') as fp:
    #     fp.writelines(res1)

    # with open(corpus_file_name,'w',encoding='utf-8') as fp:
    #     fp.writelines(res2)
    
    # traffic_log_name = 'traffic_test.html'
    # raw_corpus_traffic_file_name = 'raw_corpus_traffic.txt'
    # corpus_traffic_file_name = 'corpus_traffic.txt'
    # res1 = []
    # res2 = []
    
    # traffic_steps = retrieve_traffic_step_from_log(traffic_log_name)
    # prcessed_case_steps = convert_step_messages_into_words(traffic_steps)
    # for num, line in enumerate(traffic_steps):
    #     res1.append('^^^' + str(num) + ' : ' + line + '###\n')
    # for num, line in enumerate(prcessed_case_steps):
    #     res2.append(str(num) + ' : ' + line + '\n')

    # with open(raw_corpus_traffic_file_name,'w',encoding='utf-8') as fp:
    #     fp.writelines(res1)

    # with open(corpus_traffic_file_name,'w',encoding='utf-8') as fp:
    #     fp.writelines(res2)

    #debug end here


    print("cost %d seconds" % int(time.time() - start_time))

