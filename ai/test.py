# from pydoc import doc
# from sqlite3 import paramstyle
# from stat import ST_UID
# from xml.dom.minidom import DocumentFragment
# from setuptools import setup
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)  #抑制InsecureRequestWarning 打印
import requests
import time,os,re,shutil,wget
from multiprocessing import Pool
import pandas as pd
from lxml import etree
from gensim import corpora, models, similarities
from collections import defaultdict


#define some global variables
HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.45 Safari/537.36'}
LOG_DIR = 'AI_LOG'    #store case logs
COMP_DIR = 'AI_COMP'    #sotre ai components
ALL_TI_LIST = [] #used by _callback() to store all ti entries retrieved from SLS
DOCUMENTS = list() # document list to store corpus

#create directory for downloaded logs and generated corpus of machine learning
if not os.path.exists(LOG_DIR):
        os.mkdir(LOG_DIR)

if not os.path.exists(COMP_DIR):
        os.mkdir(COMP_DIR)

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
    response = session.post(url=url_login_test,headers=HEADERS,data=data,timeout=30,verify=False)
    print(response.status_code)
    login_detail_dict = response.json()  # 返回一个字典
    login_detail_dict.pop('auth_status')
    login_detail_dict.pop('auth_level')
    login_detail_dict.pop('seq_nbr')
    login_detail_dict.pop('result')

    url_login = 'https://smartlab-service.int.net.nokia.com/ajax/login_session'
    data = {
        'level': 'trusted',
        'timezone': 'Asia/Shanghai',
    }
    data.update(login_detail_dict)
    data['short_name'] = login_detail_dict['username']
    # print(data)
    # 发送第二个post请求，用来登录
    response = session.post(url=url_login,headers=HEADERS,data=data,timeout=30,verify=False)
    print('login sls response:', response.status_code)

    return session

def retrieve_history_ti(session, ti_type_list=['SW', 'ATC', 'ENV','SW-ONT'], ti_nums=20):
    '''
    从sls上获取history ti entries, 输出一个excel表格
    ti_nums 是每类TI的总数
    '''
    search_window = 20
    search_round = int(ti_nums/search_window)
    with Pool() as p:
        for ti_type in ti_type_list:
            if search_round == 0:
                search_round = 1  # at least search once
            for i in range(search_round):
                p.apply_async(_retrieve_ti_history_from_sls_mp,(session,i,search_window,ti_type),callback=_mycallback)
        p.close()
        p.join()

    output_file = _export_history_ti_list_to_excel(ALL_TI_LIST)

    return output_file

def retrieve_history_ti_with_release(session,release_list,ti_type_list=['SW', 'ATC', 'ENV','SW-ONT'], ti_nums_per_release=100):
    '''
    和retrieve_history_ti(), 携带一个release参数，是个list，获取落在release list内的history ti
    合并结果输出一个excel
    '''
    search_window = 50
    search_round = int(ti_nums_per_release/search_window)
    if release_list:
        with Pool() as p:
            for release_id in release_list:
                for ti_type in ti_type_list:
                    if search_round == 0:
                        search_round = 1  # at least search once
                    for i in range(search_round):
                        p.apply_async(_retrieve_ti_history_from_sls_mp,(session,i,search_window,ti_type,release_id),callback=_mycallback)
            p.close()
            p.join()
    else:
        print('release list is empty, pls give valid release id list')
    
    output_file = _export_history_ti_list_to_excel(ALL_TI_LIST)
    return output_file
 

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

def _mycallback(x):
    '''
    通过回调函数把进程池获取到的bug汇总到一个list里
    '''
    # print('mycallback is called with {}'.format(x))
    ALL_TI_LIST.extend(x)

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
    bug_status_list = []
    release_id_list = []
    batch_name_list = []
    domain_name_list = []

    for ti in ti_list:
        ti_id_list.append(ti['id'])
        atc_name_list.append(ti['ATCName'])
        job_name_list.append(ti['parentPlatform'])
        job_number_list.append(ti['jobNum'])
        ti_type_list.append(ti['TIType'])
        bug_id_list.append(ti['frId'])
        bug_status_list.append(ti['frStatus'])
        release_id_list.append(ti['releaseID'])
        batch_name_list.append(ti['batchName'])
        domain_name_list.append(ti['domainName'])

    d = {
    'TI_ID': ti_id_list,
    'JOB_NAME': job_name_list,
    'JOB_NUM': job_number_list,
    'ATC_NAME': atc_name_list,
    'TI_TYPE': ti_type_list,
    'BUG_ID': bug_id_list,
    'BUG_STATUS': bug_status_list,
    'RELEASE_ID': release_id_list,
    'BATCH_NAME': batch_name_list,
    'DOMAIN_NAME': domain_name_list
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
    worksheet.set_column('E:G', 10, format1)
    worksheet.set_column('G:H', 12, format1)
    worksheet.set_column('I:I', 30, format1)
    worksheet.set_column('J:J', 15, format1)
    writer.save()

    #move file to LOG path
    shutil.move(file_name,os.path.join(LOG_DIR,file_name))
    return file_name

def generate_input_excel_for_ml(session, input_file):
    '''
    根据input file 生成 ml 的input excel
    Column names:
    JobName_JobNum_CaseName, TI_Type, Bud_ID, Robot_Log, Traffic_Log, Trace_Debug
    '''

    df = pd.read_excel(os.path.join(LOG_DIR,input_file),engine='openpyxl')
    df.dropna(subset=['JOB_NAME','JOB_NUM','ATC_NAME','TI_TYPE','BUG_ID','BUG_STATUS','RELEASE_ID'],inplace=True)
    df.fillna('',inplace=True)
    df.drop_duplicates(subset=['JOB_NAME','JOB_NUM','ATC_NAME'],inplace=True)
    df.reset_index()
    
    ti_name_list = []
    ti_type_list =[]
    bug_id_list = []
    robot_log_list = []
    traffic_log_list =[]
    trace_debug_list = []
    robot_log_url_dict = {} #map job info to robot output dir url

    for index, row in df.iterrows():
        job_name = row['JOB_NAME']
        job_num = str(row['JOB_NUM'])
        atc_name = row['ATC_NAME']
        ti_type = row['TI_TYPE']
        bug_id = row['BUG_ID']
        batch_name = row['BATCH_NAME']
        domain_name = row['DOMAIN_NAME']
        traffic_steps = []

        #only create url path once
        job_index = job_name+ '_' + job_num + '_' + batch_name+ '_'  + domain_name
        if job_index not in robot_log_url_dict:
            robot_log_url = _create_robot_url_of_ti(session,job_name,job_num,batch_name,domain_name)
            robot_log_url_dict[job_index] = robot_log_url
        else:
            robot_log_url = robot_log_url_dict[job_index]

        #if ti is setup or teardown, skip for the time being
        if atc_name.startswith('teardown:') or atc_name.startswith('setup:'):
            ti_name = job_name + '_' + job_num + '_' + atc_name
            ti_name_list.append(ti_name)
            ti_type_list.append(ti_type)
            bug_id_list.append(bug_id)
            robot_log_list.append('None')
            traffic_log_list.append('None')
            continue

        if robot_log_url:
            print('#'*30)
            print(job_index + ':' + ' '*4 + atc_name)
            xml_file = _download_robot_xml_file(robot_log_url, job_name, job_num, batch_name, domain_name)
            if xml_file:
                tmp_steps1 = _retrieve_atc_parent_setup_step_from_log(xml_file, atc_name)
                tmp_steps2 = _retrieve_atc_step_from_log(xml_file, atc_name)
                if tmp_steps2:
                    complete_case_steps = tmp_steps1 + tmp_steps2
                    atc_file_name = job_index + '_' + atc_name+'_ROBOT_MESSAGES.txt'
                    with open(os.path.join(LOG_DIR,atc_file_name),'w',encoding='UTF-8') as fp:
                        fp.writelines(complete_case_steps)
                    robot_log_list.append(atc_file_name)
                else:
                    robot_log_list.append('None')
            else:
                robot_log_list.append('None')
            traffic_log_name = _download_atc_traffic_file(session,robot_log_url,job_name, job_num, batch_name, domain_name,atc_name)
            if traffic_log_name:
                traffic_steps = _retrieve_traffic_step_from_log(job_name, job_num, batch_name, domain_name,traffic_log_name)
                traffic_file_name = job_index + '_' + atc_name + '_TRAFFIC_MESSAGES.txt'
                with open(os.path.join(LOG_DIR,traffic_file_name),'w',encoding='UTF-8') as fp:
                    fp.writelines(traffic_steps)
                traffic_log_list.append(traffic_file_name)
            else:
                traffic_log_list.append('None')

        ti_name = job_name + '_' + job_num + '_' + atc_name
        ti_name_list.append(ti_name)
        ti_type_list.append(ti_type)
        bug_id_list.append(bug_id)

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
    worksheet.set_column('A:A', 50, format1)
    worksheet.set_column('B:C', 10, format1)
    worksheet.set_column('D:E', 55, format1)
    writer.save()
    print('excel for ml completed...')

    shutil.move(file_name,os.path.join(LOG_DIR,file_name))

    return file_name

def _create_robot_url_of_ti(session,job_name,job_num,batch_name,domain_name):
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

def _download_robot_xml_file(url,job_name,job_num,batch_name,domain_name):
    '''
    下载ti所在的output.xml
    '''

    robot_out_path = url + 'ROBOT'
    target_file = robot_out_path + '/output.xml'
    output_file_name = job_name + '_' + job_num + '_' + batch_name + '_' + domain_name + '_output.xml'

    # print(robot_out_path)
    # print(output_file_name)
    print(f'target robot output xml is {target_file}')

    if os.path.exists(os.path.join(LOG_DIR,output_file_name)):
        print('target robot output xml alread exist, skip downloading')
    else:
        print('start downloading target robot output xml ...')
        try:
            tmp_file_name = wget.download(target_file)
            print('\ndownloading output xml completed')
            shutil.move(tmp_file_name,os.path.join(LOG_DIR,output_file_name))
        except Exception as inst:
            print('download output xml failed, due to %s' % inst)
            return None

    return output_file_name

def _download_atc_traffic_file(session,url,job_name,job_num,batch_name,domain_name,case_name):
    '''
    下载ti对应的traffic log 以及所有的parent suite的traffic log
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
    parser = etree.HTMLParser(encoding='utf-8')
    tree = etree.HTML(content,parser=parser)
    log_name_list = tree.xpath('//a/text()')
    #print(log_name_list)

    #匹配case 的 traffic log
    match_pattern = r'</td><td><a href="(.*%s\.html)">' % case_name.upper()
    p = re.compile(match_pattern)
    m = p.search(content)
    if m:
        traffic_log_name = m.group(1).replace('%20',' ')     #convert '%20' to space character
    else:
        print('cannot match correspoinding traffic log for case %s' % case_name.upper())
        return None

    test_id_list = traffic_log_name.split('.')[0:-1]
    #print(test_id_list)

    for num, id in enumerate(test_id_list):
        if num == 0:
            test_id = id
        else:
            test_id = test_id + '.' + id
        traffic_log_name = test_id + '.html'
        traffic_log_url = traffic_log_path + '/' + traffic_log_name
        final_log_name = job_name + '_' + job_num + '_' + batch_name + '_' + domain_name + '_' + traffic_log_name
        if os.path.exists(os.path.join(LOG_DIR,final_log_name)):
            print(f'target traffic log {traffic_log_name} alread exist, skip downloading')
        elif traffic_log_name in log_name_list:
            print(f'start to download traffic log {traffic_log_name}')
            try:
                tmp_file_name = wget.download(traffic_log_url)
                shutil.move(tmp_file_name,os.path.join(LOG_DIR,final_log_name))
            except Exception as inst:
                print('download traffic log failed, due to %s' % inst)
                return None

    print('\ndownload all traffic log completed')

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
    print('retrieve %s steps from file %s' % (atc_name, file_name))
    test_messages = []
    try:
        parser = etree.HTMLParser(encoding='utf-8')
        tree = etree.parse(os.path.join(LOG_DIR,file_name),parser=parser)
        test_tag = tree.xpath(f'//test[@name="{atc_name}"]')[0]
        test_kw_tags = test_tag.xpath('.//kw')  #all kw tag under this test
    except Exception as inst:
        print('cannot fetch keyword tags due to %s, fail to retrieve atc steps' % inst)
        return test_messages

    for kw_tag in test_kw_tags:
        kw_name = kw_tag.xpath('./@name')[0]
        #print(kw_name)
        kw_args = kw_tag.xpath('./arguments//text()')
        if kw_args:
            kw_args = [each for each in kw_args if each != '\r\n']
            kw_args = [each for each in kw_args if each != '\n']
            #print(kw_args)
            test_messages.append(kw_name + ' '*4 + " ".join(kw_args) + '\n')    # add kw name + args
        else:
            test_messages.append(kw_name + '\n')
        kw_msg_tags = kw_tag.xpath('./msg')
        for kw_msg_tag in kw_msg_tags:
            tmp_msg = kw_msg_tag.xpath('./text()')
            if tmp_msg:
                tmp_msg = tmp_msg[0] + '\n'
            #print('tmp msg is %s' % tmp_msg)
            test_messages.append(tmp_msg)
    
    #print(len(test_messages))
    print('retrieve atc steps completed')
    test_messages = [each for each in test_messages if each]
    return test_messages

def _retrieve_atc_parent_setup_step_from_log(file_name,atc_name):
    '''
    从output.xml中获取atc parent suite的setup
    返回一个list
    '''
    setup_messages = []
    print('retrieve parent steps for case %s' % atc_name)
    try:
        parser = etree.HTMLParser(encoding='utf-8')
        tree = etree.parse(os.path.join(LOG_DIR,file_name),parser=parser)
        test_tag = tree.xpath(f'//test[@name="{atc_name}"]')[0]
        test_id = test_tag.xpath('./@id')[0]
        print(f'retrieve atc parent steps for case {atc_name}')
        test_id_list = test_id.split('-')[0:-1]
    except Exception as inst:
        print('cannot fetch test id due to %s, fail to retrieve parent steps' % inst)
        return setup_messages

    for num, id in enumerate(test_id_list):
        if num == 0:
            test_id = id
        else:
            test_id = test_id + '-' + id
        suite_tag = tree.xpath(f'//suite[@id="{test_id}"]')[0]
        suite_name = suite_tag.xpath('./@name')[0]
        #print(suite_tag)
        #print(suite_name)
        suite_setup_kw_tags = suite_tag.xpath('./kw[@type="setup"]')  #当前这个suite 直接的setup keyword(第一层)
        for suite_setup_kw_tag in suite_setup_kw_tags:
            suite_setup_kw_name = suite_setup_kw_tag.xpath('./@name')[0]
            #print(f'suite setup kw name: {suite_setup_kw_name}')

            #retrieve this setup kw arguments
            suite_setup_kw_args = suite_setup_kw_tag.xpath('./arguments//text()')
            if suite_setup_kw_args:
                suite_setup_kw_args = [each for each in suite_setup_kw_args if each != '\r\n']
                suite_setup_kw_args = [each for each in suite_setup_kw_args if each != '\n']
                # print(suite_setup_kw_args)
                setup_messages.append(suite_setup_kw_name + ' '*4 + " ".join(suite_setup_kw_args) + '\n')    # add kw name + args
            else:
                setup_messages.append(suite_setup_kw_name + '\n')

            suite_setup_child_kw_tags = suite_setup_kw_tag.xpath('.//kw') #get all child kws under this first level setup kw
            for suite_setup_child_kw_tag in suite_setup_child_kw_tags:
                suite_setup_child_kw_name = suite_setup_child_kw_tag.xpath('./@name')[0]
                #print(suite_setup_child_kw_name)
                suite_setup_child_kw_args = suite_setup_child_kw_tag.xpath('./arguments//text()')
                if suite_setup_child_kw_args:
                    suite_setup_child_kw_args = [each for each in suite_setup_child_kw_args if each != '\r\n']
                    suite_setup_child_kw_args = [each for each in suite_setup_child_kw_args if each != '\n']
                    # print(suite_setup_child_kw_args)
                    setup_messages.append(suite_setup_child_kw_name + ' '*4 + " ".join(suite_setup_child_kw_args) + '\n')    # add kw name + args
                else:
                    setup_messages.append(suite_setup_child_kw_name + '\n')
                suite_setup_child_kw_msg_tags = suite_setup_child_kw_tag.xpath('./msg')
                for suite_setup_child_kw_msg_tag in suite_setup_child_kw_msg_tags:
                    tmp_msg = suite_setup_child_kw_msg_tag.xpath('./text()')
                    if tmp_msg:
                        tmp_msg = tmp_msg[0] + '\n'
                    setup_messages.append(tmp_msg)

    #print(len(setup_messages))
    print('retrieve parent steps completed')
    #remove empty list element
    setup_messages = [each for each in setup_messages if each]
    return setup_messages

def _retrieve_traffic_step_from_log(job_name,job_num,batch_name,domain_name,traffic_log_name):
    '''
    搜索和case相关的所有traffic log, 并按先后顺序取出文本
    返回一个列表
    '''
    test_name_list = traffic_log_name.split('.')[0:-1]
    traffic_messages = []
    for num, each in enumerate(test_name_list):
        if num == 0:
            test_name = each
        else:
            test_name += '.' + each
        traffic_log_name = test_name + '.html'
        final_log_name = job_name + '_' + job_num + '_' + batch_name + '_' + domain_name + '_' + traffic_log_name
        if os.path.exists(os.path.join(LOG_DIR,final_log_name)):
            print(f'start retrieve steps from {final_log_name}')
            parser = etree.HTMLParser(encoding='utf-8')
            tree = etree.parse(os.path.join(LOG_DIR,final_log_name),parser=parser)
            log_messages = tree.xpath('//text()')
            traffic_messages.extend(log_messages)

    print(len(traffic_messages))

    return traffic_messages

def build_ml_model(file_name):
    '''
    根据输入的excel创建和训练ML模型
    '''
    excel_file = os.path.join(LOG_DIR,file_name)
    if not os.path.exists(excel_file):
        print(f'cannot find {file_name} under {LOG_DIR}, pls check...')
        return

    df = pd.read_excel(excel_file,engine='openpyxl')
    df = df.drop(df[df['ROBOT_LOG'] == 'None'].index) #remove ROBOT_LOG column为None的行
    for index, row in df.iterrows():
        robot_messages_file = row['ROBOT_LOG']
        traffic_messages_file = row['TRAFFIC_LOG']
        robot_texts = _retrieve_text_in_message_file(robot_messages_file)
        traffic_texts = _retrieve_text_in_message_file(traffic_messages_file)
        case_texts = robot_texts + traffic_texts
        DOCUMENTS.append(case_texts)
    
    stoplist = ['i', 'me', 'my', 'myself', 'we', 'our', 'ours', 'ourselves', 'you', 'your', 'yours', 'yourself', 'yourselves', 'he', 'him', 'his',
                'himself', 'she', 'her', 'hers', 'herself', 'it', 'its', 'itself', 'they', 'them', 'their', 'theirs', 'themselves', 'what', 'which', 
                'who', 'whom', 'this', 'that', 'these', 'those', 'am', 'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'having',
                'do', 'does', 'did', 'doing', 'a', 'an', 'the', 'and', 'but', 'if', 'or', 'because', 'as', 'until', 'while', 'of', 'at', 'by', 'for',
                'with', 'about', 'against', 'between', 'into', 'through', 'during', 'before', 'after', 'above', 'below', 'to', 'from', 'up', 'down',
                'in', 'out', 'on', 'off', 'over', 'under', 'again', 'further', 'then', 'once', 'here', 'there', 'when', 'where', 'why', 'how', 'all', 'any',
                'both', 'each', 'few', 'more', 'most', 'other', 'some', 'such', 'no', 'nor', 'not', 'only', 'own', 'same', 'so', 'than', 'too', 'very', 's',
                't', 'can', 'will', 'just', 'don', 'should', 'now']

    #remove stop word
    texts = [[word for word in document if word.lower() not in stoplist] for document in DOCUMENTS]
    
    #remove tokens below or above some TF level
    frequency = defaultdict(int)
    for text in texts:
        for token in text:
            frequency[token] += 1
    texts = [[token for token in text if frequency[token] >1] for text in texts]

    # Build dictionary bag
    no_below_number=2
    no_above_rate=0.7
    dictionary = corpora.Dictionary(texts)
    dictionary.filter_extremes(no_below=no_below_number,no_above=no_above_rate,keep_n=600000)
    dictionary.compactify()
    dictionary.save_as_text(os.path.join(COMP_DIR,'auto_ti.dict'))

    # Build Corpus
    corpus = [dictionary.doc2bow(text) for text in texts]
    # Save Corpus to disk
    corpora.MmCorpus.serialize(os.path.join(COMP_DIR,'auto_ti_corpus.mm'), corpus)

    # Build LSI mode based on TFIDF vector
    tfidf = models.TfidfModel(corpus)
    tfidf.save(os.path.join(COMP_DIR,'auto_ti_tfidf.ti'))
    corpus_tfidf = tfidf[corpus]

    numtopics=500
    lsi = models.LsiModel(corpus_tfidf, id2word=dictionary, num_topics=numtopics)
    lsi.save(os.path.join(COMP_DIR,'auto_ti_lis_mode.mo'))
    lsi.print_topics(numtopics)

    # Build index with LSI index
    index = similarities.MatrixSimilarity(lsi[corpus])
    index.save(os.path.join(COMP_DIR,'auto_ti_lsi_index.ind'))

    print('LSI mode building complete')

def _retrieve_text_in_message_file(file_name):
    '''
    把file 中的文本转换为word list
    '''
    document_texts = []
    if file_name != 'None':
        with open(os.path.join(LOG_DIR,file_name),'r') as fp:
            content = fp.readlines()
    else:
        return document_texts

    for each in content:
        each = each.replace('\t',' ')
        each = each.replace('\n',' ')
        each = each.replace('\r\n',' ')
        each = each.replace('\r',' ')
        each = each.replace('&nbsp',' ')
        document_texts.extend(each.split(' '))
    
    document_texts = [each for each in document_texts if each]
    #print(document_texts)
    return document_texts

def validate_ti_reference(session,job_name,job_num,batch_name,domain_name,ml_excel):
    '''
    验证一个job new ti reference的准确性
    '''
    atc_result_list = _retrieve_known_ti(session,job_name,job_num,batch_name,domain_name)
    robot_log_url = _create_robot_url_of_ti(session,job_name,job_num,batch_name,domain_name)
    job_index = job_name+ '_' + job_num + '_' + batch_name+ '_'  + domain_name

    #read ml excel to refer bug type
    df = pd.read_excel(os.path.join(LOG_DIR,ml_excel),engine='openpyxl')
    history_ti_dict = df.T.to_dict('list')
    print(f'Start to auto analyze new TI for job: {job_index}')
    
    match_num = 0.0
    total_num = len(atc_result_list)

    if robot_log_url:
        for each in atc_result_list:
            atc_name = each[0]
            atc_bug_type = each[1]
            file_list_to_reference = []
            print('#'*30)
            print(job_index + ':' + ' '*4 + atc_name)
            xml_file = _download_robot_xml_file(robot_log_url, job_name, job_num, batch_name, domain_name)
            if xml_file:
                tmp_steps1 = _retrieve_atc_parent_setup_step_from_log(xml_file, atc_name)
                tmp_steps2 = _retrieve_atc_step_from_log(xml_file, atc_name)
                if tmp_steps2:
                    complete_case_steps = tmp_steps1 + tmp_steps2
                    atc_file_name = job_index + '_' + atc_name+'_ROBOT_MESSAGES.txt'
                    with open(os.path.join(LOG_DIR,atc_file_name),'w',encoding='UTF-8') as fp:
                        fp.writelines(complete_case_steps)
                    file_list_to_reference.append(atc_file_name)
                    traffic_log_name = _download_atc_traffic_file(session,robot_log_url,job_name, job_num, batch_name, domain_name,atc_name)
                    if traffic_log_name:
                        traffic_steps = _retrieve_traffic_step_from_log(job_name, job_num, batch_name, domain_name,traffic_log_name)
                        traffic_file_name = job_index + '_' + atc_name + '_TRAFFIC_MESSAGES.txt'
                        with open(os.path.join(LOG_DIR,traffic_file_name),'w',encoding='UTF-8') as fp:
                            fp.writelines(traffic_steps)
                        file_list_to_reference.append(traffic_file_name)

            sims_list = _ti_reference(file_list_to_reference)
            if sims_list:
                ref_ti_type = _reference_method_1(sims_list, history_ti_dict)
                if atc_bug_type == ref_ti_type:
                    match_num += 1
                    print(f'actual ti type: {atc_bug_type}, recomended ti type: {ref_ti_type}, MATCH')
                else:
                    print(f'actual ti type: {atc_bug_type}, recomended ti type: {ref_ti_type}, NOT MATCH')
            else:
                print(f'cannot recommend ti type for {atc_name} due to no query document')
    else:
        print(f'cannot find robot url for {job_index}')

    print('analyzed totally %d TIs, matched %d TIs' % (int(total_num), int(match_num)))
    print('reference accurucy is %f' % (match_num/total_num,))

def _retrieve_known_ti(session,job_name,job_num,batch_name,domain_name):
    '''
    根据job_name,job_num,batch_name,domain_name 获取已知的ti，用来验证模型的准确性
    返回(atc name, bug type) tuple 的 一个list
    '''
    web_url = 'https://smartlab-service.int.net.nokia.com/atcReport'
    job_num = str(job_num)
    params = {
        'job_name': job_name,
        'job_num': job_num,
        'job_coverage': batch_name,
        'groupID': '',
        'Domain': domain_name,
        'username': ''
    }

    response = session.get(web_url,params=params,headers=HEADERS,timeout=30,verify=False)
    response_text = response.text.replace('null','" "')
    ti_list = eval(response_text)['data']

    atc_result_list = []
    for each in ti_list:
        if each['frClassify'] in ['ATC','SW','ENV','SW-ONT'] and each['frId']['value']:
            atc_name = each['ATCName']
            bug_type = each['frClassify']
            #skip setup and teardown ti for the time being
            if atc_name.startswith('teardown:') or atc_name.startswith('setup:'):
                continue
            t = (atc_name, bug_type)
            atc_result_list.append(t)

    return atc_result_list

def _retrieve_new_ti(session,job_name,job_num,batch_name,domain_name):
    '''
    根据job_name,job_num,batch_name,domain_name 获取未分析的ti
    返回一个atc name list
    '''

    web_url = 'https://smartlab-service.int.net.nokia.com/atcReport'
    job_num = str(job_num)
    params = {
        'job_name': job_name,
        'job_num': job_num,
        'job_coverage': batch_name,
        'groupID': '',
        'Domain': domain_name,
        'username': ''
    }

    response = session.get(web_url,params=params,headers=HEADERS,timeout=30,verify=False)
    response_text = response.text.replace('null','" "')
    ti_list = eval(response_text)['data']

    atc_name_list = []
    for each in ti_list:
        if each['frNewOrOld'] == 'Old' and each['frClassify'] and each['frId']['value']:
            continue    #known ti, skip
        else:
            atc_name = each['ATCName']
            atc_name_list.append(atc_name)
    
    #print(atc_name_list)
    return atc_name_list

def _ti_reference(query0,qtype='FileList'):
    '''
    根据query0文本的相似度匹配
    qtype默认是Filelist, query0 为一个文件名列表; 否则 query0 为文本列表
    输出匹配度最高的前5个元素，例如：
    [(10, 1.0), (9, 0.7924244), (7, 0.65759844), (17, 0.57193935), (18, 0.5716857), (13, 0.46947253)]
    '''
    #load ai model
    print('Load AI Analysis Model')
    dictionary=corpora.Dictionary.load_from_text(os.path.join(COMP_DIR,'auto_ti.dict'))
    lsi=models.LsiModel.load(os.path.join(COMP_DIR,'auto_ti_lis_mode.mo'))
    index=similarities.MatrixSimilarity.load(os.path.join(COMP_DIR,'auto_ti_lsi_index.ind'))

    query=[]    #word list
    if qtype == 'FileList':
        for each in query0:
            file_path =  os.path.join(LOG_DIR, each)
            if os.path.exists(file_path):
                with open(file_path,'r') as fp:
                    content = fp.readlines()
                for line in content:
                    line = line.replace('\t',' ')
                    line = line.replace('\n',' ')
                    line = line.replace('\r\n',' ')
                    line = line.replace('\r',' ')
                    line = line.replace('&nbsp',' ')
                    query.extend(line.split(' '))
                query = [x for x in query if x]
            else:
                print(f'cannot find {file_path}')
                query.extend([])
    else:
        query=str(query0).strip() #未测试

    if query:
        query_bow = dictionary.doc2bow(query)
        query_lsi = lsi[query_bow]
        sims = index[query_lsi]
        sort_sims = sorted(enumerate(sims), key=lambda x: x[1], reverse=True)
    else:
        print('no input document to query')
        return []

    return sort_sims

def _reference_method_1(sims_list,history_ti_dict):
    '''
    method 1: 直接推荐相似度最高的history ti 的 bug type
    '''
    print('ti reference method 1')

    sims_list = sims_list[:5] # 取前5个
    print('most 5 similar index: %s' % str(sims_list))
    ti_type_list = []
    for each in sims_list:
        index = each[0]
        ti_name = history_ti_dict[index][0]
        ti_type = history_ti_dict[index][1]
        bug_id = history_ti_dict[index][2]
        t = (ti_name,ti_type,bug_id)
        ti_type_list.append(t)
    print('most 5 similar ti: %s' % str(ti_type_list))
    print('reference method 1 recommended: %s' % str(ti_type_list[0]))

    dict_index = sims_list[0][0]
    return history_ti_dict[dict_index][1]

if __name__ == '__main__':
    
    start_time = time.time()

    #for debug
    username = 'jieminbz'
    password = 'Jim#2346'

    session = login_sls(username, password)

    tmp_excel = retrieve_history_ti_with_release(session,release_list=['22.03','6.6'], ti_nums_per_release=200)
    # tmp_excel = generate_input_excel_for_ml(session,tmp_excel)
    # build_ml_model(tmp_excel)

    # validate_ti_reference(session,'SHA_NFXSE_FANTH_P2P_FELTC_WEEKLY_01','583','SLS_BATCH_1','','ti_list_for_ml_20220407.xlsx')

    print("cost %d seconds" % int(time.time() - start_time))

