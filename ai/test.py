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
LOG_DIR = 'AI_LOG'    #store case logs, ml execl files
COMP_DIR = 'AI_COMP'    #store ml components
ALL_TI_LIST = [] #used by _mycallback_history_ti() to store all ti entries retrieved from SLS
DOCUMENTS = list() # document list to store corpus
FIBER_ISAM_JOB_LIST = []
FIBER_MOSWA_JOB_LIST = []   # fiber moswa job list
RELEASE_MAPPING_DICT = {'22.03': '6.6'}
ROBOT_LOG_URL_DICT = {} #store job index and its robot url path
BUILD_KNOWN_TI_LIST = [] # used by _mycallback_build() to store known ti of a build, for validation usage
TI_DOCUMENTS_LIST = [] #used by _mycallback_ti_documents()


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
    response = session.post(url=url_login_test,headers=HEADERS,data=data,timeout=600,verify=False)
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
    response = session.post(url=url_login,headers=HEADERS,data=data,timeout=600,verify=False)
    print('login sls response:', response.status_code)

    return session

def retrieve_history_ti_by_release(session,release_id,ti_nums_per_type=10,ti_type_list=['SW','ATC','ENV','SW-ONT']):
    '''
    在一个release内, 根据FIBER_MOSWA_JOB_LIST 和 FIBER_ISAM_JOB_LIST 获取每个job 的历史ti,默认情况下,每类ti 每个job 获取10个
    合并结果输出一个excel, 用于后续的ml
    release_id sample: '22.03', don't give legacy one like 6.6
    '''
    search_window = 10
    search_round = int(ti_nums_per_type/search_window)
    _get_job_names_from_file()
    print('start retrieve history ti by release')
    with Pool() as p:
        for job_name in FIBER_MOSWA_JOB_LIST:
            if search_round == 0:
                search_round = 1  # at least search once
            for ti_type in ti_type_list:
                for i in range(search_round):
                    p.apply_async(_retrieve_ti_history_from_sls,(session,i,search_window,ti_type,release_id,job_name,''),callback=_mycallback_history_ti)
        # for job_name in FIBER_ISAM_JOB_LIST:
        #     release_id = RELEASE_MAPPING_DICT[release_id]  # convert to legacy release id for isam batch    
        #     if search_round == 0:
        #         search_round = 1  # at least search once
        #     for ti_type in ti_type_list:
        #         for i in range(search_round):
        #             p.apply_async(_retrieve_ti_history_from_sls,(session,i,search_window,ti_type,release_id,job_name),callback=_mycallback)
        p.close()
        p.join()

    output_file = _export_history_ti_list_to_excel(ALL_TI_LIST)
    print('retrieve history ti finished...')
    return output_file

def _get_job_names_from_file(file_name='MOSWA_JOB_NAME.txt'):
    '''
    根据MOSWA_JOB_NAME.txt 获取所有Fiber Moswa job name
    return a list
    '''
    global FIBER_MOSWA_JOB_LIST
    if os.path.exists(file_name):
        with open(file_name,'r',encoding='UTF-8') as fp:
            FIBER_MOSWA_JOB_LIST = fp.readlines()
        FIBER_MOSWA_JOB_LIST = [each.rstrip('\n') for each in FIBER_MOSWA_JOB_LIST]
    else:
        print(f'cannot find moswa job name list file: {file_name}')
    # print(len(FIBER_MOSWA_JOB_LIST))

def _retrieve_ti_history_from_sls(session,draw,search_window,ti_type='',release_id='',job_name='',build_id=''):
    '''
    用于进程池获取ti list
    draw: 依据请求次数从1递增
    search_window: 每次返回的ti 个数
    ti_type: SW or ATC or ENV or SW-ONT
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
        'buildID': build_id,
        'purpose2': '',
        'jobName': job_name,
        'ATCName': '',
        'runOnObjName': '',
        'frClassify': ti_type,
        'pt': '',
    }

    ti_list = []
    response = session.post(url=url_bug_history,headers=HEADERS,data=data,timeout=600,verify=False)
    ti_list = response.json()['data']
    print(len(ti_list))
    print(f'stop child process {pid}')
    return ti_list

def _mycallback_history_ti(x):
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
    build_id_list = []
    batch_name_list = []
    domain_name_list = []
    test_cs_id_list = []
    test_result_list= []

    for ti in ti_list:
        ti_id_list.append(ti['id'])
        atc_name_list.append(ti['ATCName'])
        job_name_list.append(ti['parentPlatform'])
        job_number_list.append(ti['jobNum'])
        ti_type_list.append(ti['TIType'])
        bug_id_list.append(ti['frId'])
        bug_status_list.append(ti['frStatus'])
        build_id_list.append(ti['buildID'])
        batch_name_list.append(ti['batchName'])
        domain_name_list.append(ti['domainName'])
        test_cs_id_list.append(ti['testCS'])
        test_result_list.append(ti['testResult'])

    d = {
    'TI_ID': ti_id_list,
    'JOB_NAME': job_name_list,
    'JOB_NUM': job_number_list,
    'ATC_NAME': atc_name_list,
    'BATCH_NAME': batch_name_list,
    'DOMAIN_NAME': domain_name_list,
    'BUILD_ID': build_id_list,
    'CS_ID': test_cs_id_list,
    'TEST_RESULT': test_result_list,
    'TI_TYPE': ti_type_list,
    'BUG_ID': bug_id_list,
    'BUG_STATUS': bug_status_list,
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
    worksheet.set_column('B:B', 40, format1)
    worksheet.set_column('C:C', 10, format1)
    worksheet.set_column('D:D', 45, format1)
    worksheet.set_column('E:E', 20, format1)
    worksheet.set_column('F:L', 12, format1)
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
    print('source entry num from input is %d' %len(df))
    df.dropna(subset=['JOB_NAME','JOB_NUM','ATC_NAME','BUILD_ID','CS_ID','TEST_RESULT','TI_TYPE','BUG_ID'],inplace=True)
    df.fillna('',inplace=True)
    df.drop_duplicates(subset=['JOB_NAME','JOB_NUM','ATC_NAME','BATCH_NAME','DOMAIN_NAME'],inplace=True)
    # df.drop_duplicates(subset=['JOB_NAME','ATC_NAME','TI_TYPE','BUG_ID'],inplace=True)
    df.reset_index()
    print('entry num after process is %d' %len(df))
    print('start to generate excel for ml...')

    #download all needed output.xml
    _download_robot_xml_file_mp(session,input_file=input_file)
    
    with Pool(6) as p:
        for index, row in df.iterrows():
            job_name = row['JOB_NAME']
            job_num = str(row['JOB_NUM'])
            atc_name = row['ATC_NAME']
            ti_type = row['TI_TYPE']
            bug_id = row['BUG_ID']
            batch_name = row['BATCH_NAME']
            domain_name = row['DOMAIN_NAME']
            job_index = job_name+ '_' + job_num + '_' + batch_name+ '_'  + domain_name
            robot_log_url = ROBOT_LOG_URL_DICT.get(job_index,'')
            p.apply_async(_generate_document_files_for_ti,(session,robot_log_url,job_name, job_num, batch_name, domain_name,atc_name, ti_type, bug_id),callback=_mycallback_ti_documents)
        p.close()
        p.join()

    # print(TI_DOCUMENTS_LIST)
    new_df = pd.DataFrame(TI_DOCUMENTS_LIST,columns=['TI_Name','TI_TYPE','BUG_ID','ROBOT_LOG','TRAFFIC_LOG'])
    print('new df shape is %s' % str(new_df.shape))
    new_df.drop(new_df[new_df['ROBOT_LOG'] == 'None'].index,inplace=True) #remove ROBOT_LOG columnÎªNoneµÄÐÐ
    new_df.reset_index()
    print('new df shape after drop is %s' % str(new_df.shape))
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

def _mycallback_ti_documents(x):
    TI_DOCUMENTS_LIST.append(x)

def _generate_document_files_for_ti(session,robot_log_url,job_name, job_num, batch_name, domain_name,atc_name, ti_type, bug_id):
    '''
    根据输入生成用于ml的各个ti的documents
    此函数被用于进程池，在generate_input_excel_for_ml() 被调用
    返回一个list, 内容对应TI_NAME, TI_TYPE, BUG_ID, ROBOT_LOG, TRAFFIC_LOG
    '''
    job_index = job_name+ '_' + job_num + '_' + batch_name+ '_'  + domain_name
    ti_name = job_index + '_' + atc_name
    xml_file = job_index + '_output.xml'
    res = []
    res.append(ti_name)
    res.append(ti_type)
    res.append(bug_id)

    print('*'*5 +job_index + ':' + ' '*4 + atc_name + '*'*5)
    if robot_log_url and os.path.exists(os.path.join(LOG_DIR,xml_file)):
        if atc_name.startswith('setup:'):
            atc_name = atc_name.lstrip('setup:')
            ti_name = ti_name.replace(':','_')
            tmp_steps = _retrieve_kw_step_from_log(xml_file,atc_name)
            if tmp_steps:
                atc_file_name = ti_name +'_ROBOT_MESSAGES.txt'
                with open(os.path.join(LOG_DIR,atc_file_name),'w',encoding='UTF-8') as fp:
                    fp.writelines(tmp_steps)
                res.append(atc_file_name)
                res.append('None')
            else:
                res.append('None')
                res.append('None')
        elif atc_name.startswith('teardown:'):
            atc_name = atc_name.lstrip('teardown:')
            ti_name = ti_name.replace(':','_')
            tmp_steps = _retrieve_kw_step_from_log(xml_file,atc_name,kw_type='teardown')
            if tmp_steps:
                atc_file_name = ti_name +'_ROBOT_MESSAGES.txt'
                with open(os.path.join(LOG_DIR,atc_file_name),'w',encoding='UTF-8') as fp:
                    fp.writelines(tmp_steps)
                res.append(atc_file_name)
                res.append('None')
            else:
                res.append('None')
                res.append('None')
        else:
            tmp_steps1 = _retrieve_atc_parent_setup_step_from_log(xml_file, atc_name)
            tmp_steps2 = _retrieve_atc_step_from_log(xml_file, atc_name)
            #use atc xml instead if fail to parse steps from output.xml
            if not tmp_steps2:
                xml_file = _download_atc_xml_file(robot_log_url,job_name, job_num, batch_name, domain_name,atc_name)
                tmp_steps2 = _retrieve_atc_step_from_log(xml_file, atc_name) 
            if tmp_steps1 or tmp_steps2:
                complete_case_steps = tmp_steps1 + tmp_steps2
                atc_file_name = ti_name +'_ROBOT_MESSAGES.txt'
                with open(os.path.join(LOG_DIR,atc_file_name),'w',encoding='UTF-8') as fp:
                    fp.writelines(complete_case_steps)
                res.append(atc_file_name)

                traffic_log_name = _download_atc_traffic_file(session,robot_log_url,job_name, job_num, batch_name, domain_name,atc_name)
                if traffic_log_name:
                    traffic_steps = _retrieve_traffic_step_from_log(job_name, job_num, batch_name, domain_name,traffic_log_name)
                    traffic_file_name = ti_name + '_TRAFFIC_MESSAGES.txt'
                    with open(os.path.join(LOG_DIR,traffic_file_name),'w',encoding='UTF-8') as fp:
                        fp.writelines(traffic_steps)
                    res.append(traffic_file_name)
                else:
                    res.append('None')
            else:
                res.append('None')
                res.append('None')
    else:
        print(f'cannot find ROBOT log url or required xml file does not exist for TI: {ti_name}')
        res.append('None')
        res.append('None')

    # print(res)
    print('*'*5 + job_index + ':' + ' '*4 + atc_name + ' complete...' + '*'*5)
    return res

def _create_robot_url_of_ti(session,job_name,job_num,batch_name,domain_name):
    '''
    根据job name, job num, batch name, domain name 生成ROBOT路径(url)并返回
    https://smartlab-service.int.net.nokia.com/Result/ 点开某个job
    '''

    url_job_result = 'https://smartlab-service.int.net.nokia.com/ResultDetails/'
    log_url = ''

    data = {
        'jobName': job_name,
        'jobNum': str(job_num),
    }

    job_result_list = []
    response = session.post(url=url_job_result,headers=HEADERS,data=data,timeout=600,verify=False)
    job_result_list = response.json()['data']
    job_result_list = sorted(job_result_list, key=lambda x: x["DT_RowId"],reverse=True)

    for job_result in job_result_list:
        job_domain_name = job_result.get('Coverage', '')
        job_batch_name =  job_result.get('batchName', '')
        if domain_name and job_domain_name == domain_name and job_batch_name == batch_name:
            log_url = job_result['Logs']
            break
        elif (not domain_name) and  job_batch_name == batch_name:
            # domain name is null from history ti page while eqauls batch name in job result page
            # in such case, ignore domain name
            log_url = job_result['Logs']
            break
    else:
        print(f'cannot find log path for job: {job_name}, num: {job_num}, domain_name: {domain_name}, batch_name: {batch_name}')

    #only create url path once
    job_index = job_name+ '_' + job_num + '_' + batch_name+ '_'  + domain_name
    if job_index not in ROBOT_LOG_URL_DICT:
        ROBOT_LOG_URL_DICT[job_index] = log_url

    #print('log url is %s' % log_url)
    return log_url

def _download_robot_xml_file(url,job_name,job_num,batch_name,domain_name):
    '''
    下载ti所在的output.xml
    被_download_robot_xml_file_mp()调用
    '''
    robot_out_path = url + 'ROBOT'
    target_file = robot_out_path + '/output.xml'
    output_file_name = job_name + '_' + job_num + '_' + batch_name + '_' + domain_name + '_output.xml'

    print(f'target robot output xml is {target_file}')

    if os.path.exists(os.path.join(LOG_DIR,output_file_name)):
        print(f'target robot output xml {target_file} alread exist, skip downloading')
    else:
        print(f'start download target robot output xml {target_file}')
        try:
            wget.download(target_file,out=os.path.join(LOG_DIR,output_file_name))
            print(f'\ndownload target robot output xml {target_file} completed')
        except Exception as inst:
            print('download target robot output xml %s failed, due to %s' % (target_file,inst))
            return None

    return output_file_name

def _download_robot_xml_file_mp(session,input_file=None,ti_list=None):
    '''
    使用进程池下载robot output.xml
    '''
    download_task_list  = [] # store download task list
    print('start to download all required robot xml files first...')

    if input_file:
        df = pd.read_excel(os.path.join(LOG_DIR,input_file),engine='openpyxl')
        df.dropna(subset=['JOB_NAME','JOB_NUM','ATC_NAME','BUILD_ID','CS_ID','TEST_RESULT','TI_TYPE','BUG_ID'],inplace=True)
        df.fillna('',inplace=True)
        df.drop_duplicates(subset=['JOB_NAME','JOB_NUM','BATCH_NAME','DOMAIN_NAME'],inplace=True)
        df.reset_index()

        for index, row in df.iterrows():
            job_name = row['JOB_NAME']
            job_num = str(row['JOB_NUM'])
            batch_name = row['BATCH_NAME']
            domain_name = row['DOMAIN_NAME']

            #only create url path once
            job_index = job_name+ '_' + job_num + '_' + batch_name+ '_'  + domain_name
            if job_index not in ROBOT_LOG_URL_DICT:
                robot_log_url = _create_robot_url_of_ti(session,job_name,job_num,batch_name,domain_name)
            else:
                robot_log_url = ROBOT_LOG_URL_DICT.get(job_index,'')
            if robot_log_url:
                print('add job %s to download task list' % job_index)
                t = (robot_log_url,job_name,job_num,batch_name,domain_name)
                download_task_list.append(t)

    elif ti_list:
        for each_ti in ti_list:
            job_name = each_ti['parentPlatform']
            job_num = str(each_ti['jobNum'])
            batch_name = each_ti['batchName']
            domain_name = each_ti['domainName']

            #only create url path once
            job_index = job_name+ '_' + job_num + '_' + batch_name+ '_'  + domain_name
            if job_index not in ROBOT_LOG_URL_DICT:
                robot_log_url = _create_robot_url_of_ti(session,job_name,job_num,batch_name,domain_name)
            else:
                robot_log_url = ROBOT_LOG_URL_DICT.get(job_index,'')
            if robot_log_url:
                print('add job %s to download task list' % job_index)
                t = (robot_log_url,job_name,job_num,batch_name,domain_name)
                download_task_list.append(t)

    #remove duplicate tasks
    s1 = set(download_task_list)
    print('xml file number to download is %d' % len(s1))

    with Pool() as p:
        for each in s1:
            p.apply_async(_download_robot_xml_file,(each[0],each[1],each[2],each[3],each[4]))
        p.close()
        p.join()

    print('download all output xml completed...')

def _download_atc_xml_file(url,job_name,job_num,batch_name,domain_name,case_name):
    '''
    如果从output.xml中获取step失败，则重新下载case所对应的xml，再尝试解析
    '''
    parent_path = url + 'ROBOT/robot-data/ATC/'
    output_file_name = job_name + '_' + job_num + '_' + batch_name + '_' + domain_name + '_' + f'{case_name}.xml'
    target_file = parent_path + f'{case_name}.xml'

    print(f'target atc xml file is {target_file}')
    if os.path.exists(os.path.join(LOG_DIR,output_file_name)):
        print(f'target atc xml {output_file_name} alread exist, skip downloading')
    else:
        try:
            print('start downloading target atc xml ...')
            wget.download(target_file,out=os.path.join(LOG_DIR,output_file_name))
            print('\ndownloading atc xml completed')
        except Exception as inst:
            print('download atc xml failed, due to %s' % inst)
            return None
    
    return output_file_name

def _download_atc_traffic_file(session,url,job_name,job_num,batch_name,domain_name,case_name):
    '''
    下载ti对应的traffic log 以及所有的parent suite的traffic log
    '''
    robot_out_path = url + 'ROBOT'
    response = session.get(robot_out_path,headers=HEADERS,timeout=600,verify=False)
    content = response.text

    #匹配traffic log所在的目录名称
    traffic_dir_name = ''
    p = re.compile(r'</td><td><a href="(TRAFFIC-[A-Z][a-z]{2}[0-9]{8})/">')
    m = p.search(content)
    if m:
        traffic_dir_name = m.group(1)
    else:
        print(f'cannot find traffic dir under {robot_out_path}')
        return None

    traffic_log_path = robot_out_path + '/' + traffic_dir_name
    response = session.get(traffic_log_path,headers=HEADERS,timeout=600,verify=False)
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
        output_file_name = job_name + '_' + job_num + '_' + batch_name + '_' + domain_name + '_' + traffic_log_name

        if traffic_log_name in log_name_list:
            if os.path.exists(os.path.join(LOG_DIR,output_file_name)):
                print(f'target atc xml {output_file_name} alread exist, skip downloading')
            else:
                print(f'start to download traffic log {traffic_log_name}')
                try:
                    wget.download(traffic_log_url,out=os.path.join(LOG_DIR,output_file_name))
                except Exception as inst:
                    print('download traffic log failed, due to %s' % inst)
                    return None

    print('\ndownload all traffic log completed')

    return traffic_log_name

def _download_atc_trace_debug_file(url):
    '''
    下载trace debug 文件(文件是batch 级别的，还需要后续处理)
    '''
    pass

def _retrieve_kw_step_from_log(file_name,kw_name,kw_type='setup'):
    '''
    从output.xml中获取setup/teardown kw 的步骤
    '''
    print(f'start to retrieve kw {kw_name} steps from file {file_name}')
    test_messages = []
    try:
        parser = etree.XMLParser(encoding='utf-8',huge_tree=True)
        tree = etree.parse(os.path.join(LOG_DIR,file_name),parser=parser)
        kw_tag = tree.xpath(f'//kw[@type="{kw_type}" and @name="{kw_name}"]')[0]
        kw_child_tags = kw_tag.xpath('.//kw')
    except Exception as inst:
        print('cannot fetch keyword tags due to %s, fail to retrieve kw steps' % inst)
        return test_messages
    
    for kw_tag in kw_child_tags:
        kw_name = kw_tag.xpath('./@name')[0]
        kw_args = kw_tag.xpath('./arguments//text()')
        if kw_args:
            kw_args = [each for each in kw_args if each != '\r\n']
            kw_args = [each for each in kw_args if each != '\n']
            test_messages.append(kw_name + ' '*4 + " ".join(kw_args) + '\n')
        else:
            test_messages.append(kw_name + '\n')
        kw_msg_tags = kw_tag.xpath('./msg')
        for kw_msg_tag in kw_msg_tags:
            tmp_msg = kw_msg_tag.xpath('./text()')
            if tmp_msg:
                tmp_msg = tmp_msg[0] + '\n'
            test_messages.append(tmp_msg)

    test_messages = [each for each in test_messages if each]
    print(len(test_messages))
    print(f'retrieve kw {kw_name} steps from file {file_name} complete')
    return test_messages

def _retrieve_atc_step_from_log(file_name,atc_name):
    '''
    从output.xml中获取atc的执行步骤
    返回一个list
    '''
    print(f'start to retrieve case {atc_name} steps from file {file_name}')
    test_messages = []
    try:
        parser = etree.XMLParser(encoding='utf-8',huge_tree=True)
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

    test_messages = [each for each in test_messages if each]
    print(len(test_messages))
    print(f'retrieve case {atc_name} steps from file {file_name} complete')
    return test_messages

def _retrieve_atc_parent_setup_step_from_log(file_name,atc_name):
    '''
    从output.xml中获取atc parent suite的setup
    返回一个list
    '''
    setup_messages = []
    print(f'start to retrieve case {atc_name} parent setup steps from file {file_name}')
    try:
        parser = etree.XMLParser(encoding='utf-8',huge_tree=True)
        tree = etree.parse(os.path.join(LOG_DIR,file_name),parser=parser)
        test_tag = tree.xpath(f'//test[@name="{atc_name}"]')[0]
        test_id = test_tag.xpath('./@id')[0]
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

    #remove empty list element
    setup_messages = [each for each in setup_messages if each]
    print(len(setup_messages))
    print(f'retrieve case {atc_name} parent setup steps from file {file_name} complete')
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
        tmp_log_name = job_name + '_' + job_num + '_' + batch_name + '_' + domain_name + '_' + traffic_log_name
        if os.path.exists(os.path.join(LOG_DIR,tmp_log_name)):
            print(f'start to retrieve traffic steps from {tmp_log_name}')
            parser = etree.HTMLParser(encoding='utf-8')
            tree = etree.parse(os.path.join(LOG_DIR,tmp_log_name),parser=parser)
            log_messages = tree.xpath('//text()')
            traffic_messages.extend(log_messages)
            print(f'retrieve traffic steps from {tmp_log_name} complete')

    print(len(traffic_messages))
    return traffic_messages

class Read_File(object):
    '''
    This class is used to read all the documents for machine learning
    return a python generator to save memory
    '''
    def __init__(self, input_file):
        self.input_file = os.path.join(LOG_DIR,input_file)
        self.file_list = []
        self.stop_word_list = ['i', 'me', 'my', 'myself', 'we', 'our', 'ours', 'ourselves', 'you', 'your', 'yours', 'yourself', 'yourselves', 'he', 'him', 'his',
            'himself', 'she', 'her', 'hers', 'herself', 'it', 'its', 'itself', 'they', 'them', 'their', 'theirs', 'themselves', 'what', 'which', 
            'who', 'whom', 'this', 'that', 'these', 'those', 'am', 'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'having',
            'do', 'does', 'did', 'doing', 'a', 'an', 'the', 'and', 'but', 'if', 'or', 'because', 'as', 'until', 'while', 'of', 'at', 'by', 'for',
            'with', 'about', 'against', 'between', 'into', 'through', 'during', 'before', 'after', 'above', 'below', 'to', 'from',
            'in', 'out', 'on', 'off', 'over', 'under', 'again', 'further', 'then', 'once', 'here', 'there', 'when', 'where', 'why', 'how', 'all', 'any',
            'both', 'each', 'few', 'more', 'most', 'other', 'some', 'such', 'no', 'nor', 'not', 'only', 'own', 'same', 'so', 'than', 'too', 'very',
            'can', 'will', 'just', 'don', 'now']
        if os.path.exists(self.input_file):
            df = pd.read_excel(self.input_file,engine='openpyxl')
            for index, row in df.iterrows():
                t= (row['ROBOT_LOG'], row['TRAFFIC_LOG'])
                self.file_list.append(t)
        else:
            print(f'{self.input_file} does not exist...')
        # print('file name list is %s' % str(self.file_list))
    
    def _text_process(self,text):
        '''
        line is a str, return a list
        '''
        text = text.replace('\t',' ')
        text = text.replace('\n',' ')
        text = text.replace('\r\n',' ')
        text = text.replace('\r',' ')
        text = text.replace('&nbsp',' ')
        return text

    def __iter__(self):
        for each in self.file_list:
            log_text = ''
            robot_log_file = os.path.join(LOG_DIR,each[0])
            if os.path.exists(robot_log_file):
                with open(robot_log_file, 'r', encoding='utf-8') as fp:
                    log_text = fp.read()
            if each[1] != 'None':
                traffic_log_file = os.path.join(LOG_DIR,each[1])
                if os.path.exists(traffic_log_file):
                    with open(traffic_log_file, 'r', encoding='utf-8') as fp:
                        log_text += fp.read()
            tmp_list = [x for x in self._text_process(log_text).split(' ') if x] # split the text into a list
            yield [x for x in tmp_list if x.lower() not in self.stop_word_list] #remove stop words

def _create_corpus(dictionary, file_texts):
    '''
    create corpus according to file_texts
    return a generator to save memory
    '''
    for each in file_texts:
        yield dictionary.doc2bow(each)

def build_ml_model(file_name):
    '''
    traing model according to input excel
    '''
    print('start to build LSI mode')
    excel_file = os.path.join(LOG_DIR,file_name)
    if not os.path.exists(excel_file):
        print(f'cannot find {file_name} under {LOG_DIR}, pls check...')
        return
    
    print('start to create dictionary and corpus')
    documents_text = Read_File(excel_file)
    no_below_number=2
    no_above_rate=0.7
    dictionary = corpora.Dictionary(documents_text)
    dictionary.filter_extremes(no_below=no_below_number,no_above=no_above_rate,keep_n=600000)
    dictionary.compactify()
    dictionary.save_as_text(os.path.join(COMP_DIR,'auto_ti.dict'))
    corpus = _create_corpus(dictionary, documents_text)
    corpus = list(corpus)
    corpora.MmCorpus.serialize(os.path.join(COMP_DIR,'auto_ti_corpus.mm'), corpus)

    print('start to train model')
    tfidf = models.TfidfModel(corpus)
    tfidf.save(os.path.join(COMP_DIR,'auto_ti_tfidf.ti'))
    corpus_tfidf = tfidf[corpus]

    numtopics=500
    lsi = models.LsiModel(corpus_tfidf, id2word=dictionary, num_topics=numtopics)
    lsi.save(os.path.join(COMP_DIR,'auto_ti_lis_mode.mo'))
    # lsi.print_topics(numtopics)

    # Build index with LSI index
    index = similarities.MatrixSimilarity(lsi[corpus])
    index.save(os.path.join(COMP_DIR,'auto_ti_lsi_index.ind'))

    print('LSI mode building complete')

def validate_ti_reference_by_job(session,job_name,job_num,batch_name,domain_name,ml_excel):
    '''
    验证一个job new ti reference的准确性
    '''
    atc_result_list = _retrieve_known_ti_by_job(session,job_name,job_num,batch_name,domain_name)
    robot_log_url = _create_robot_url_of_ti(session,job_name,job_num,batch_name,domain_name)
    job_index = job_name+ '_' + job_num + '_' + batch_name+ '_'  + domain_name

    #read ml excel to refer bug type
    df = pd.read_excel(os.path.join(LOG_DIR,ml_excel),engine='openpyxl')
    history_ti_dict = df.T.to_dict('list')
    print(f'Start to auto analyze new TI for job: {job_index}')
    
    match_num = 0.0
    ana_num = 0.0 # count analyzed ti number
    total_num = len(atc_result_list)

    if robot_log_url:
        xml_file = _download_robot_xml_file(robot_log_url, job_name, job_num, batch_name, domain_name)
        if xml_file:
            for each in atc_result_list:
                atc_name = each[0]
                ti_name = job_index + '_' + atc_name
                atc_bug_type = each[1]
                file_list_to_reference = []
                print('#'*30)
                print(job_index + ':' + ' '*4 + atc_name)

                if atc_name.startswith('setup:'):
                    atc_name = atc_name.lstrip('setup:')
                    ti_name = ti_name.replace(':','_')
                    tmp_steps = _retrieve_kw_step_from_log(xml_file,atc_name)
                    if tmp_steps:
                        atc_file_name = ti_name +'_ROBOT_MESSAGES.txt'
                        with open(os.path.join(LOG_DIR,atc_file_name),'w',encoding='UTF-8') as fp:
                            fp.writelines(tmp_steps)
                        file_list_to_reference.append(atc_file_name).append(atc_file_name)
                elif atc_name.startswith('teardown:'):
                    atc_name = atc_name.lstrip('teardown:')
                    ti_name = ti_name.replace(':','_')
                    tmp_steps = _retrieve_kw_step_from_log(xml_file,atc_name,kw_type='teardown')
                    if tmp_steps:
                        atc_file_name = ti_name +'_ROBOT_MESSAGES.txt'
                        with open(os.path.join(LOG_DIR,atc_file_name),'w',encoding='UTF-8') as fp:
                            fp.writelines(tmp_steps)
                        file_list_to_reference.append(atc_file_name)
                else:
                    tmp_steps1 = _retrieve_atc_parent_setup_step_from_log(xml_file, atc_name)
                    tmp_steps2 = _retrieve_atc_step_from_log(xml_file, atc_name)
                    if not tmp_steps2:
                        xml_file = _download_atc_xml_file(robot_log_url,job_name, job_num, batch_name, domain_name,atc_name)
                        tmp_steps2 = _retrieve_atc_step_from_log(xml_file, atc_name) 
                    if tmp_steps1 or tmp_steps2:
                        complete_case_steps = tmp_steps1 + tmp_steps2
                        atc_file_name = ti_name +'_ROBOT_MESSAGES.txt'
                        with open(os.path.join(LOG_DIR,atc_file_name),'w',encoding='UTF-8') as fp:
                            fp.writelines(complete_case_steps)
                        file_list_to_reference.append(atc_file_name)

                        traffic_log_name = _download_atc_traffic_file(session,robot_log_url,job_name, job_num, batch_name, domain_name,atc_name)
                        if traffic_log_name:
                            traffic_steps = _retrieve_traffic_step_from_log(job_name, job_num, batch_name, domain_name,traffic_log_name)
                            traffic_file_name = ti_name + '_TRAFFIC_MESSAGES.txt'
                            with open(os.path.join(LOG_DIR,traffic_file_name),'w',encoding='UTF-8') as fp:
                                fp.writelines(traffic_steps)
                            file_list_to_reference.append(traffic_file_name)
                
                sims_list = _sims_compare(file_list_to_reference)
                if sims_list:
                    ana_num +=1
                    ref_ti_type = _reference_method_2(sims_list, history_ti_dict)
                    if atc_bug_type == ref_ti_type:
                        match_num += 1
                        print(f'actual ti type: {atc_bug_type}, recomended ti type: {ref_ti_type}, MATCH')
                    else:
                        print(f'actual ti type: {atc_bug_type}, recomended ti type: {ref_ti_type}, NOT MATCH')
                else:
                    print(f'cannot recommend ti type for {atc_name} due to no query document')
        else:
            print(f'fail to download robot xml file for {job_index}')
    else:
        print(f'cannot find robot url for {job_index}')

    print('total TI number: %d, analyzed %d TIs, matched %d TIs' % (total_num, int(ana_num), int(match_num)))
    print('reference accurucy is %f' % (match_num/ana_num,))

def _retrieve_known_ti_by_job(session,job_name,job_num,batch_name,domain_name):
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

    response = session.get(web_url,params=params,headers=HEADERS,timeout=600,verify=False)
    response_text = response.text.replace('null','" "')
    ti_list = eval(response_text)['data']

    atc_result_list = []
    for each in ti_list:
        if each['frClassify'] in ['ATC','SW','ENV','SW-ONT'] and each['frId']['value']:
            atc_name = each['ATCName']
            bug_type = each['frClassify']
            t = (atc_name, bug_type)
            atc_result_list.append(t)

    return atc_result_list

def validate_ti_reference_by_build(session,build_id,ml_excel):
    '''
    验证一个build 的 ti 预测结果
    '''
    _retrieve_known_ti_by_build(session,build_id)

    #read ml excel to refer bug type
    df = pd.read_excel(os.path.join(LOG_DIR,ml_excel),engine='openpyxl')
    history_ti_dict = df.T.to_dict('list')

    #download all needed output.xml
    _download_robot_xml_file_mp(session,ti_list=BUILD_KNOWN_TI_LIST)

    match_num = 0.0
    ana_num = 0.0 # count analyzed ti number
    total_num = len(BUILD_KNOWN_TI_LIST)

    #dict to pandas df
    ti_name_list = []
    ti_type_list =[] # recommended ti type
    match_list = []
    ref_bug_list = [] # referenced ti type
    ref_bug_status_list = []

    iter_count = 0
    for each_ti in BUILD_KNOWN_TI_LIST:
        job_name = each_ti['parentPlatform']
        job_num = str(each_ti['jobNum'])
        batch_name = each_ti['batchName']
        domain_name = each_ti['domainName']
        atc_name = each_ti['ATCName']
        atc_bug_type = each_ti['TIType']

        job_index = job_name+ '_' + job_num + '_' + batch_name+ '_'  + domain_name
        ti_name = job_index + '_' + atc_name
        robot_log_url = ROBOT_LOG_URL_DICT.get(job_index,'')
        xml_file = job_index + '_output.xml'

        iter_count +=1
        if robot_log_url and os.path.exists(os.path.join(LOG_DIR,xml_file)):
            print(f'{iter_count} of {total_num}')
            print('*'*5 +job_index + ':' + ' '*4 + atc_name + '*'*5)
            file_list_to_reference = []

            ti_name_list.append(ti_name)
            if atc_name.startswith('setup:'):
                atc_name = atc_name.lstrip('setup:')
                ti_name = ti_name.replace(':','_')
                tmp_steps = _retrieve_kw_step_from_log(xml_file,atc_name)
                if tmp_steps:
                    atc_file_name = ti_name +'_ROBOT_MESSAGES.txt'
                    with open(os.path.join(LOG_DIR,atc_file_name),'w',encoding='UTF-8') as fp:
                        fp.writelines(tmp_steps)
                    file_list_to_reference.append(atc_file_name)
            elif atc_name.startswith('teardown:'):
                atc_name = atc_name.lstrip('teardown:')
                ti_name = ti_name.replace(':','_')
                tmp_steps = _retrieve_kw_step_from_log(xml_file,atc_name,kw_type='teardown')
                if tmp_steps:
                    atc_file_name = ti_name +'_ROBOT_MESSAGES.txt'
                    with open(os.path.join(LOG_DIR,atc_file_name),'w',encoding='UTF-8') as fp:
                        fp.writelines(tmp_steps)
                    file_list_to_reference.append(atc_file_name)
            else:
                tmp_steps1 = _retrieve_atc_parent_setup_step_from_log(xml_file, atc_name)
                tmp_steps2 = _retrieve_atc_step_from_log(xml_file, atc_name)
                #use atc xml instead if fail to parse steps from output.xml
                if not tmp_steps2:
                    xml_file = _download_atc_xml_file(robot_log_url,job_name, job_num, batch_name, domain_name,atc_name)
                    tmp_steps2 = _retrieve_atc_step_from_log(xml_file, atc_name) 
                if tmp_steps1 or tmp_steps2:
                    complete_case_steps = tmp_steps1 + tmp_steps2
                    atc_file_name = ti_name +'_ROBOT_MESSAGES.txt'
                    with open(os.path.join(LOG_DIR,atc_file_name),'w',encoding='UTF-8') as fp:
                        fp.writelines(complete_case_steps)
                    file_list_to_reference.append(atc_file_name)

                    traffic_log_name = _download_atc_traffic_file(session,robot_log_url,job_name, job_num, batch_name, domain_name,atc_name)
                    if traffic_log_name:
                        traffic_steps = _retrieve_traffic_step_from_log(job_name, job_num, batch_name, domain_name,traffic_log_name)
                        traffic_file_name = ti_name + '_TRAFFIC_MESSAGES.txt'
                        with open(os.path.join(LOG_DIR,traffic_file_name),'w',encoding='UTF-8') as fp:
                            fp.writelines(traffic_steps)
                        file_list_to_reference.append(traffic_file_name)
            
            sims_list = _sims_compare(file_list_to_reference)
            if sims_list:
                ana_num +=1
                rec_ti_type = _reference_method_2(sims_list, history_ti_dict)
                ti_type_list.append(rec_ti_type)
                if atc_bug_type == rec_ti_type:
                    match_num += 1
                    match_list.append('1')
                    print(f'actual ti type: {atc_bug_type}, recomended ti type: {rec_ti_type}, MATCH')
                else:
                    match_list.append('0')
                    print(f'actual ti type: {atc_bug_type}, recomended ti type: {rec_ti_type}, NOT MATCH')
            else:
                match_list.append('None')
                print(f'cannot recommend ti type for {atc_name} due to no query document')

        else:
            print(f'cannot find ROBOT log url or required xml file does not exist for TI: {ti_name}')
    
    print('total TI number: %d, analyzed %d TIs, matched %d TIs' % (total_num, int(ana_num), int(match_num)))
    print('reference accurucy is %f' % (match_num/ana_num,))
    
    #export result to Excel
    d = {
    'TI_NAME': ti_name_list,
    'TI_TYPE': ti_type_list,
    'MATCH': match_list,
    }

    new_df = pd.DataFrame(data=d)
    print('new df shape is %s' % str(new_df.shape))

    #use xlsxwriter to write xlsx
    file_name = 'validate_ti_build_result_{}.xlsx'.format(time.strftime('%Y%m%d'))
    sheet_name = 'Result'
    writer = pd.ExcelWriter(file_name, engine='xlsxwriter')
    new_df.to_excel(writer,index=False,sheet_name=sheet_name)

    workbook  = writer.book
    worksheet = writer.sheets[sheet_name]
    format1 = workbook.add_format({'text_wrap': True,'border': 1,'align': 'left'})
    worksheet.set_column('A:A', 50, format1)
    worksheet.set_column('B:C', 10, format1)
    writer.save()
    print('excel for ti validation completed...')

    shutil.move(file_name,os.path.join(LOG_DIR,file_name))

def validate_ti_reference_by_build_bak(session,build_id,ml_excel):
    '''
    验证一个build 的 ti 预测结果
    废弃
    '''
    _retrieve_known_ti_by_build(session,build_id)

    match_num = 0.0
    ana_num = 0.0 # count analyzed ti number
    total_num = len(BUILD_KNOWN_TI_LIST)

    #read ml excel to refer bug type
    df = pd.read_excel(os.path.join(LOG_DIR,ml_excel),engine='openpyxl')
    history_ti_dict = df.T.to_dict('list')

    #download all needed output.xml
    _download_robot_xml_file_mp(session,ti_list=BUILD_KNOWN_TI_LIST)

    #dict to pandas df
    ti_name_list = []
    ti_type_list =[] # recommended ti type
    match_list = []
    ref_bug_list = [] # referenced ti type
    ref_bug_status_list = []

    iter_count = 0
    for each_ti in BUILD_KNOWN_TI_LIST:
        job_name = each_ti['parentPlatform']
        job_num = str(each_ti['jobNum'])
        batch_name = each_ti['batchName']
        domain_name = each_ti['domainName']
        atc_name = each_ti['ATCName']
        atc_bug_type = each_ti['TIType']

        #skip setup and teardown ti for the time being
        if atc_name.startswith('teardown:') or atc_name.startswith('setup:'):
            continue

        job_index = job_name+ '_' + job_num + '_' + batch_name+ '_'  + domain_name
        ti_name = job_name + '_' + job_num + '_' + atc_name
        robot_log_url = ROBOT_LOG_URL_DICT.get(job_index,'')
        print('#'*30)
        iter_count +=1
        print(f'{iter_count} of {total_num}')

        if robot_log_url:
            file_list_to_reference = []
            print(job_index + ':' + ' '*4 + atc_name)
            xml_file = job_name + '_' + job_num + '_' + batch_name + '_' + domain_name + '_output.xml'
            if os.path.exists(os.path.join(LOG_DIR,xml_file)):
                ti_name_list.append(ti_name)
                tmp_steps1 = _retrieve_atc_parent_setup_step_from_log(xml_file, atc_name)
                tmp_steps2 = _retrieve_atc_step_from_log(xml_file, atc_name)
                #use atc xml instead if fail to parse steps from output.xml
                if not tmp_steps2:
                    xml_file = _download_atc_xml_file(robot_log_url,atc_name)
                    tmp_steps2 = _retrieve_atc_step_from_log(xml_file, atc_name) 
                if tmp_steps1 or tmp_steps2:
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

            sims_list = _sims_compare(file_list_to_reference)
            if sims_list:
                ana_num +=1
                ref_ti_type = _reference_method_2(sims_list, history_ti_dict)
                ti_type_list.append(ref_ti_type)
                if atc_bug_type == ref_ti_type:
                    match_num += 1
                    match_list.append('1')
                    print(f'actual ti type: {atc_bug_type}, recomended ti type: {ref_ti_type}, MATCH')
                else:
                    match_list.append('0')
                    print(f'actual ti type: {atc_bug_type}, recomended ti type: {ref_ti_type}, NOT MATCH')
            else:
                ti_type_list.append('None')
                match_list.append('None')
                print(f'cannot recommend ti type for {atc_name} due to no query document')
        else:
            print(f'cannot find robot url for {job_index}')

    print('analyzed totally %d TIs, matched %d TIs' % (int(ana_num), int(match_num)))
    print('reference accurucy is %f' % (match_num/ana_num,))

    #export result to Excel
    d = {
    'TI_NAME': ti_name_list,
    'TI_TYPE': ti_type_list,
    'MATCH': match_list,
    }

    new_df = pd.DataFrame(data=d)
    print('new df shape is %s' % str(new_df.shape))

    #use xlsxwriter to write xlsx
    file_name = 'validate_ti_build_result_{}.xlsx'.format(time.strftime('%Y%m%d'))
    sheet_name = 'Result'
    writer = pd.ExcelWriter(file_name, engine='xlsxwriter')
    new_df.to_excel(writer,index=False,sheet_name=sheet_name)

    workbook  = writer.book
    worksheet = writer.sheets[sheet_name]
    format1 = workbook.add_format({'text_wrap': True,'border': 1,'align': 'left'})
    worksheet.set_column('A:A', 50, format1)
    worksheet.set_column('B:C', 10, format1)
    writer.save()
    print('excel for ti validation completed...')

    shutil.move(file_name,os.path.join(LOG_DIR,file_name))

def _mycallback_build(x):
    BUILD_KNOWN_TI_LIST.extend(x)

def _retrieve_known_ti_by_build(session,build_id,ti_type_list=['SW','ATC','ENV','SW-ONT']):
    '''
    根据build id 获取当前这个build的所有TI结果
    返回(atc name, bug type) tuple 的 一个list
    '''
    search_window = 10
    _get_job_names_from_file('MOSWA_JOB_NAME_VAL.txt')
    print('start retrieve known ti according to build id')
    with Pool() as p:
        for job_name in FIBER_MOSWA_JOB_LIST:
            for ti_type in ti_type_list:
                p.apply_async(_retrieve_ti_history_from_sls,(session,1,search_window,ti_type,'',job_name,build_id),callback=_mycallback_build)
        p.close()
        p.join()

    print('retrieve known ti finished...')
    # print(BUILD_KNOWN_TI_LIST)
    print(len(BUILD_KNOWN_TI_LIST))

def _sims_compare(query0,qtype='FileList'):
    '''
    根据query0文本的相似度匹配
    qtype默认是Filelist, query0 为一个文件名列表; 否则 query0 为文本列表
    输出匹配度最高的前20个元素，例如：
    [(10, 1.0), (9, 0.7924244), (7, 0.65759844), (17, 0.57193935), (18, 0.5716857), (13, 0.46947253)...]
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

    return sort_sims[:20]

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

def _reference_method_2(sims_list,history_ti_dict):
    '''
    method 2: 取相似度最高的5个, 然后计算每类TI的得分
    '''
    print('ti reference method 2')

    sims_list = sims_list[:5] # 取前5个
    print('most 5 similar index: %s' % str(sims_list))
    ti_type_list = []
    ti_type_score_dict = {}
    for each in sims_list:
        index = each[0]
        score = each[1]
        ti_name = history_ti_dict[index][0]
        ti_type = history_ti_dict[index][1]
        bug_id = history_ti_dict[index][2]
        t = (ti_name,ti_type,bug_id)
        ti_type_list.append(t)
        if ti_type in ti_type_score_dict:
            ti_type_score_dict[ti_type] += score
        else:
            ti_type_score_dict[ti_type] = score
    
    sorted_score_list = sorted(ti_type_score_dict.items(), key = lambda x : x[1], reverse=True)
    res = sorted_score_list[0][0]
    print('most 5 similar ti: %s' % str(ti_type_list))
    print('ti type score list: %s' % str(sorted_score_list))
    print('reference method 2 recommended: %s' % res)

    return res

if __name__ == '__main__':

    from optparse import OptionParser
    import sys

    parser = OptionParser()
    parser.add_option("-t","--validtionType", dest="type",default='job', help="validate by job or build")
    parser.add_option("-i","--inputParameters", dest="params",default='', help="input validate parameters")
    parser.add_option("-u","--username", dest="username",default='', help="CSL")
    parser.add_option("-p","--passwd", dest="passwd",default='', help="Password")

    (options, args) = parser.parse_args(sys.argv[1:])
    username = options.username
    passwd = options.passwd
    ValidationType = options.type.strip()
    params = options.params.strip()
    validOptions = [ValidationType,params,username,passwd]

    start_time = time.time()
    if all(validOptions):
        print('validate model...')
        session = login_sls(username, passwd)
        if ValidationType == 'job':
            params_list = params.split(' ')
            job_name = params_list[0]
            job_num = params_list[1]
            batch_name = params_list[2]
            domain_name = params_list[3]
            validate_ti_reference_by_job(session,job_name,job_num,batch_name,domain_name,'ti_list_for_ml_20220427_baseline.xlsx')
        elif ValidationType == 'build':
            build_id = params.split(' ')[0]
            validate_ti_reference_by_build(session,build_id,'ti_list_for_ml_20220427_baseline.xlsx')
        else:
            print('error, please input correct parameters')
    else:
        print('training model phase...')
        # import logging
        # logging.basicConfig(format='%(asctime)s : %(levelname)s : %(message)s', level=logging.DEBUG)
        # session = login_sls(username, passwd)
        # tmp_excel = retrieve_history_ti_by_release(session,'22.03')    # 10 history entries per job per ti type
        # tmp_excel = generate_input_excel_for_ml(session,'history_ti_list_20220425.xlsx')
        # build_ml_model(tmp_excel)
        # validate_ti_reference_by_job(session,'LSFX_NFXSE_FANTF_FGLTB_GPON_EONUAV_WEEKLY_02','75','SLS_BATCH_1','L2FWD','ti_list_for_ml_20220427_baseline.xlsx')
        # validate_ti_reference_by_build(session,'2206.225','ti_list_for_ml_20220427_baseline.xlsx')
    print("cost %d seconds" % int(time.time() - start_time))



