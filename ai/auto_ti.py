import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)  #抑制InsecureRequestWarning 打印
from urllib.error import HTTPError
import time,os,re,shutil,wget,zipfile
from multiprocessing import Pool
import pandas as pd
from lxml import etree
from gensim import corpora, models, similarities
from jira import JIRA
import pymysql

#define some global variables
HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.45 Safari/537.36'}
LOG_DIR = 'AI_LOG'    #store case logs, ml execl files
COMP_DIR = 'AI_COMP'    #store ml components
ROBOT_LOG_URL_DICT = {} #store robot url path of a job index
ROBOT_JOB_RESULT_DICT = {} #store job result of a build or release
TI_DOCUMENTS_LIST = [] #used by _mycallback_ti_documents() to store ti info for ml excel
COMM_STOP_WORD_LIST = ['i', 'me', 'my', 'myself', 'we', 'our', 'ours', 'ourselves', 'you', "you're", "you've", "you'll", "you'd", 'your',
    'yours', 'yourself', 'yourselves', 'he', 'him', 'his', 'himself', 'she', "she's", 'her', 'hers', 'herself', 'it', "it's",
    'its', 'itself', 'they', 'them', 'their', 'theirs', 'themselves', 'what', 'which', 'who', 'whom', 'this', 'that', "that'll",
    'these', 'those', 'have', 'has', 'had', 'having',
    'doing', 'a', 'an', 'the', 'and', 'but', 'if', 'or', 'because', 'as', 'until', 'while', 'of', 'at', 'by', 'for', 'with', 'about',
    'against', 'into', 'through', 'during', 'before', 'after', 'to', 'from',
    'again', 'further', 'then', 'here', 'there', 'when', 'where', 'why', 'how',
    'both', 'each', 'few', 'more', 'most', 'other', 'some', 'such', 'nor', 'own', 'so', 'than', 'too',
    'very', 'can', 'will', 'just', 'don', 'now', 'd', 'll', 'm', 'o', 're', 've', 'y', 'ain',
    'aren', "aren't", 'couldn',
    'ma', 'mightn', "mightn't", 'shan', "shan't"]
CUST_STOP_WORD_LIST = ['span','color', 'xmlns','get','filter','rpc-reply','rpc','name','interface','interfaces-state','device-manager',
    'device', 'alarms', 'alarm-list', 'device-specific-data']

#create directory for downloaded logs and generated corpus of machine learning
if not os.path.exists(LOG_DIR):
    os.mkdir(LOG_DIR)

if not os.path.exists(COMP_DIR):
    os.mkdir(COMP_DIR)

def retrieve_history_ti_from_db(build_id='',release_id='',fetch_num=10000,keep_num=1000):
    '''
    retrieve histrory ti entries from SLS database according to its build id or release id
    return a list
    fetch_num: number of fetched TI from SLS database in SQL query
    keep_num: number of TI returned by this method
    '''
    history_ti_list = []
    moswa_job_list = _get_job_names_from_file()

    print('start to retrieve history ti from db...')
    # Connect to the database
    connection = pymysql.connect(host='135.249.27.193',
        user='smtlab',
        password='smtlab123',
        database='robot2')

    with connection:
        with connection.cursor() as cursor:
            if release_id:
                sql = "SELECT id,jobName,jobNum,ATCName,batchName,DomainName,buildID,testCS,testResult,frId,frClassify \
                    FROM testATCResults WHERE testResult = 'FAIL' and frClassify in ('SW','ATC') and releaseID = '%s'\
                    ORDER by id DESC LIMIT 0,%s" % (release_id, fetch_num)
            elif build_id:
                sql = "SELECT id,jobName,jobNum,ATCName,batchName,DomainName,buildID,testCS,testResult,frId,frClassify \
                    FROM testATCResults WHERE testResult = 'FAIL'  and frClassify in ('SW','ATC') and buildID = '%s'\
                    ORDER by id DESC LIMIT 0,%s" % (build_id, fetch_num)
            else:
                print('Error, please input one either "build_id" or "release_id"')
                return None
            try:
                cursor.execute(sql)
                history_ti_list = cursor.fetchall()
            except Exception as inst:
                print('Error, fail to fetch data from DB due to %s' % inst)
                return None

    history_ti_list = [each for each in history_ti_list if each[1] in moswa_job_list]   #remove entries not in moswa batch job
    history_ti_list = history_ti_list[:keep_num]    #only return keep_num entries
    print(len(history_ti_list))
    output_file = _export_history_ti_list_to_excel(history_ti_list)
    print('retrieve history ti from db finished...')
    return output_file

def _get_job_names_from_file(file_name='MOSWA_JOB_NAME.txt'):
    '''
    return the job names in file_name
    return a list
    '''
    job_list = []
    if os.path.exists(file_name):
        with open(file_name,'r',encoding='UTF-8') as fp:
            job_list = fp.readlines()
        job_list = [each.rstrip('\n') for each in job_list]
    else:
        print(f'cannot find moswa job name list file: {file_name}')
    return job_list

def _export_history_ti_list_to_excel(ti_list):
    '''
    export the ti_list into Excel
    called by retrieve_history_ti_from_db() and retrieve_history_ti_by_build_list()
    '''
    bug_info_dict = {} # store bug's fix version, status, affects_version and labels value, key is bug id
    jira_inst = JIRA('https://jiradc2.ext.net.nokia.com/', auth=('jieminbz', 'Jim#2346'))
    new_ti_list = []

    for ti_entry in ti_list:
        ti_entry = [x for x in ti_entry]
        bug_id = ti_entry[9]
        # ti_id,job_name,job_num,atc_name,batch_name,domain_name,build_id,test_cs,test_result,bug_id,ti_type = ti
        if bug_id and bug_id not in bug_info_dict:
            bug_info_dict[bug_id] = []
            try:
                issue = jira_inst.issue(bug_id)
                fix_version = issue.fields.fixVersions[0].name
                bug_status = issue.fields.status.name
                bug_type = issue.fields.issuetype.name
                affects_version = issue.fields.versions[0].name
                labels = issue.fields.labels    # return is a list
                labels = ','.join(labels).upper()
            except:
                bug_info_dict[bug_id] = ['','','','']
                ti_entry += [''] * 4
            else:
                if bug_type.lower() in ['bug', 'sub-task']:
                    bug_info_dict[bug_id] = [fix_version, bug_status, affects_version, labels]
                    ti_entry.append(fix_version)
                    ti_entry.append(bug_status)
                    ti_entry.append(affects_version)
                    ti_entry.append(labels)
                else:
                    bug_info_dict[bug_id] = ['','','','']
                    ti_entry += [''] * 4
        elif bug_id:
            ti_entry += bug_info_dict[bug_id]
        else:
            ti_entry += [''] * 4

        new_ti_list.append(ti_entry)

    df = pd.DataFrame(new_ti_list,
        columns=['TI_ID','JOB_NAME','JOB_NUM','ATC_NAME','BATCH_NAME','DOMAIN_NAME','BUILD_ID','CS_ID','TEST_RESULT',
            'BUG_ID','TI_TYPE','FIX_VERSION','BUG_STATUS','AFFECTS_VERSION','LABELS'])

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
    worksheet.set_column('F:N', 12, format1)
    worksheet.set_column('O:O', 20, format1)
    writer.save()

    #move file to LOG path
    shutil.move(file_name,os.path.join(LOG_DIR,file_name))
    return file_name

def generate_input_excel_for_ml(input_file):
    '''
    export the excel file for AI model training
    '''
    df = pd.read_excel(os.path.join(LOG_DIR,input_file),engine='openpyxl')
    print('source entry num from input is %d' %len(df))
    df.dropna(subset=['JOB_NAME','JOB_NUM','ATC_NAME','BUILD_ID','CS_ID','TEST_RESULT','FIX_VERSION','BUG_ID','BUG_STATUS'],inplace=True)
    df.fillna('',inplace=True)
    df.sort_values(by=['TI_ID'],inplace=True)
    #remove the duplicated TIs which map the same bug in one job
    df.drop_duplicates(subset=['JOB_NAME','JOB_NUM','BATCH_NAME','DOMAIN_NAME','BUG_ID'],inplace=True)
    df.reset_index(drop=True,inplace=True)
    print('entry num after process is %d' %len(df))
    print('start to generate excel for ml...')

    #download all needed output.xml
    _download_robot_xml_file_mp(input_file=input_file)

    with Pool(4) as p:
        for index, row in df.iterrows():
            ti_id = row['TI_ID']
            job_name = row['JOB_NAME']
            job_num = str(row['JOB_NUM'])
            atc_name = row['ATC_NAME']
            fix_version = row['FIX_VERSION']
            bug_id = row['BUG_ID']
            bug_status = row['BUG_STATUS']
            batch_name = row['BATCH_NAME']
            domain_name = row['DOMAIN_NAME']
            job_index = job_name+ '_' + job_num + '_' + batch_name+ '_'  + domain_name
            robot_log_url = ROBOT_LOG_URL_DICT.get(job_index,'')
            p.apply_async(_generate_document_files_for_ti,(robot_log_url,ti_id, job_name, job_num, batch_name, domain_name,atc_name, fix_version, bug_id, bug_status),callback=_mycallback_ti_documents)
        p.close()
        p.join()

    new_df = pd.DataFrame(TI_DOCUMENTS_LIST,columns=['TI_ID','JOB_NAME', 'JOB_NUM', 'BATCH_NAME', 'DOMAIN_NAME', 'ATC_NAME','BUG_ID','FIX_VERSION','BUG_STATUS','ROBOT_LOG'])
    new_df.drop(new_df[new_df['ROBOT_LOG'] == 'None'].index,inplace=True) #remove ROBOT_LOG columnÎ is None
    new_df.sort_values(by=['TI_ID'],ascending=False,inplace=True)
    new_df.reset_index(drop=True,inplace=True)
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
    worksheet.set_column('A:A', 10, format1)
    worksheet.set_column('B:B', 40, format1)
    worksheet.set_column('C:E', 10, format1)
    worksheet.set_column('F:F', 45, format1)
    worksheet.set_column('G:I', 15, format1)
    worksheet.set_column('J:J', 55, format1)
    writer.save()
    print('excel for ml completed...')

    shutil.move(file_name,os.path.join(LOG_DIR,file_name))
    return file_name

def _get_robot_url_of_ti(job_name,job_num,batch_name,domain_name,release_id='',build_id=''):
    '''
    return the robot url path according to job_name, job_num, batch_name, domain_name and build_id/release_id
    global DICT ROBOT_LOG_URL_DICT is also updated to store the url path based on job index which can be used
    by other methods
    '''
    global ROBOT_LOG_URL_DICT, ROBOT_JOB_RESULT_DICT

    if release_id and (release_id not in ROBOT_JOB_RESULT_DICT):
        # Connect to the database
        connection = pymysql.connect(host='135.249.27.193',
            user='smtlab',
            password='smtlab123',
            database='robot2')

        with connection:
            with connection.cursor() as cursor:
                build_id_like = release_id.replace('.','')
                sql = f"SELECT id,jobName,jobNum,batchName,Coverage,Logs FROM testJobResults WHERE buildID like '%{build_id_like}.%' ORDER by id DESC"
                try:
                    cursor.execute(sql)
                    fetch_result = cursor.fetchall()
                    if len(fetch_result) < 1:
                        print(f'fetch zero entries for job: {job_name}, num: {job_num}, domain_name: {domain_name}, batch_name: {batch_name}, release_id: {release_id}')
                    ROBOT_JOB_RESULT_DICT[release_id] = fetch_result
                except Exception as inst:
                    print('Error, fail to fetch data from DB due to %s' % inst)
                    ROBOT_JOB_RESULT_DICT[release_id] = []

    elif build_id and (build_id not in ROBOT_JOB_RESULT_DICT) :
        connection = pymysql.connect(host='135.249.27.193',
            user='smtlab',
            password='smtlab123',
            database='robot2')

        with connection:
            with connection.cursor() as cursor:
                sql = f"SELECT id,jobName,jobNum,batchName,Coverage,Logs FROM testJobResults WHERE buildID = '{build_id}' ORDER by id DESC"
                try:
                    cursor.execute(sql)
                    fetch_result = cursor.fetchall()
                    if len(fetch_result) < 1:
                        print(f'fetch zero entries for job: {job_name}, num: {job_num}, domain_name: {domain_name}, batch_name: {batch_name}, build_id: {build_id}')
                    ROBOT_JOB_RESULT_DICT[build_id] = fetch_result
                except Exception as inst:
                    print('Error, fail to fetch data from DB due to %s' % inst)
                    ROBOT_JOB_RESULT_DICT[build_id] = []
    elif (not build_id) and (not release_id):
        print('Error, please input one either "build_id" or "release_id"')
        return None

    job_index = job_name+ '_' + job_num + '_' + batch_name+ '_'  + domain_name
    if job_index in ROBOT_LOG_URL_DICT:
        return ROBOT_LOG_URL_DICT[job_index]
    elif build_id:
        for each in ROBOT_JOB_RESULT_DICT[build_id]:
            if job_name == each[1] and job_num == str(each[2]) and batch_name == each[3] and domain_name == each[4]:
                robot_url = each[5]
                ROBOT_LOG_URL_DICT[job_index] = robot_url
                break
        else:
            print(f'cannot find robot url for job: {job_name}, num: {job_num}, domain_name: {domain_name}, batch_name: {batch_name}')
            return None
    elif release_id:
        for each in ROBOT_JOB_RESULT_DICT[release_id]:
            if job_name == each[1] and job_num == str(each[2]) and batch_name == each[3] and domain_name == each[4]:
                robot_url = each[5]
                ROBOT_LOG_URL_DICT[job_index] = robot_url
                break
        else:
            print(f'cannot find robot url for job: {job_name}, num: {job_num}, domain_name: {domain_name}, batch_name: {batch_name}')
            return None

    return robot_url

def _download_robot_xml_file(url,job_name,job_num,batch_name,domain_name):
    '''
    download the output.xml of a job
    be called by _download_robot_xml_file_mp()
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
            tmp_target_file = target_file.replace('output.xml','output_xml.zip')
            tmp_zip_file = output_file_name.replace('output.xml','output_xml.zip')
            wget.download(tmp_target_file,out=tmp_zip_file)
        except HTTPError:
            try:
                tmp_target_file = target_file.replace('output.xml','output.zip')
                tmp_zip_file = output_file_name.replace('output.xml','output.zip')
                wget.download(tmp_target_file,out=tmp_zip_file)
            except HTTPError:
                try:
                    wget.download(target_file,out=os.path.join(LOG_DIR,output_file_name))
                    print(f'\ndownload target file {target_file} completed')
                    return output_file_name
                except Exception as inst:
                    print('download target file %s failed, due to %s' % (target_file,inst))
                    return None
        
        print(f'\ndownload target file {tmp_target_file} completed')
        # with ZipFile('output.zip', 'r') as zipObj:
        #     zipObj.extractall(path=LOG_DIR)
        with zipfile.ZipFile(tmp_zip_file) as z:
            for zip_file in z.namelist():
                with z.open(zip_file) as zf, open(os.path.join(LOG_DIR,output_file_name), 'wb') as f:
                    shutil.copyfileobj(zf, f)
        print(f'unzip target file {tmp_target_file} completed')
        os.remove(tmp_zip_file)

    return output_file_name

def _download_robot_xml_file_mp(input_file=None,ti_list=None):
    '''
    use process pool to download robot output.xml concurrently
    '''
    download_task_list  = [] # store download task list
    print('start to download all required robot xml files first...')

    if input_file:
        df = pd.read_excel(os.path.join(LOG_DIR,input_file),engine='openpyxl')
        df.dropna(subset=['JOB_NAME','JOB_NUM','ATC_NAME','BUILD_ID','CS_ID','TEST_RESULT','FIX_VERSION','BUG_ID','BUG_STATUS'],inplace=True)
        df.reset_index(drop=True,inplace=True)
        df.fillna('',inplace=True)
        df.drop_duplicates(subset=['JOB_NAME','JOB_NUM','BATCH_NAME','DOMAIN_NAME'],inplace=True)
        df.reset_index(drop=True,inplace=True)

        for index, row in df.iterrows():
            job_name = row['JOB_NAME']
            job_num = str(row['JOB_NUM'])
            batch_name = row['BATCH_NAME']
            domain_name = row['DOMAIN_NAME']
            build_id = str(row['BUILD_ID'])[:8]

            #only create url path once
            job_index = job_name + '_' + job_num + '_' + batch_name + '_'  + domain_name
            robot_log_url = _get_robot_url_of_ti(job_name,job_num,batch_name,domain_name,build_id=build_id)
            if robot_log_url:
                print('add job %s to download task list' % job_index)
                t = (robot_log_url,job_name,job_num,batch_name,domain_name)
                download_task_list.append(t)

    elif ti_list:
        for each_ti in ti_list:
            job_name = each_ti[0]
            job_num = str(each_ti[1])
            batch_name = each_ti[2]
            domain_name = each_ti[3]
            build_id = str(each_ti[4])

            #only create url path once
            job_index = job_name + '_' + job_num + '_' + batch_name + '_'  + domain_name
            robot_log_url = _get_robot_url_of_ti(job_name,job_num,batch_name,domain_name,build_id=build_id)
            if robot_log_url:
                print('add job %s to download task list' % job_index)
                t = (robot_log_url,job_name,job_num,batch_name,domain_name)
                download_task_list.append(t)

    #remove duplicate tasks
    s1 = set(download_task_list)
    print('xml file number to download is %d' % len(s1))

    with Pool(4) as p:
        for each in s1:
            p.apply_async(_download_robot_xml_file,(each[0],each[1],each[2],each[3],each[4]))
        p.close()
        p.join()

    print('download all output xml completed...')

def _download_atc_xml_file(url,job_name,job_num,batch_name,domain_name,case_name):
    '''
    download case's xml file
    this operation only happens when fail to parse step from output.xml, use this xml instead
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

def _retrieve_failed_step_from_xml_bak(file_name,atc_name='',kw_name='',kw_type='setup'):
    '''
    retrieve the failed text from xml file
    file_name: output.xml or atc xml file
    atc_name: failed atc name
    kw_name: failed kw name, only be used with parameter 'kw_type'
    kw_type: 'setup' or 'teardown', only be used with parameter 'kw_name'
    '''
    test_messages = []
    failed_kw_tags = [] #失败的第一级kw

    if any([atc_name,kw_name]):
        pass
    else:
        print(f'cannot retrieve fail step, please input either "atc_name" or "kw_name"')
        return test_messages

    try:
        parser = etree.XMLParser(encoding='utf-8',huge_tree=True)
        tree = etree.parse(os.path.join(LOG_DIR,file_name),parser=parser)
        if atc_name:
            print(f'start to retrieve failed step of case {atc_name}')
            xpath = f'//test[@name="{atc_name}"]'
        else:
            print(f'start to retrieve failed step of kw {kw_name}')
            xpath = f'//kw[@type="{kw_type}" and @name="{kw_name}"]'
        main_tag = tree.xpath(xpath)[0]
        kw_tags = main_tag.xpath('./kw')    #test下第一级kw
    except Exception as inst:
        print(f'cannot fetch kw tags for {atc_name} {kw_name} due to {inst}')
        return test_messages

    for each in kw_tags:
        try:
            kw_name = each.xpath('./@name')[0]
            kw_result = each.xpath('./status/@status')[0]
            if kw_result != 'PASS':
                failed_kw_tags.append(each)
        except Exception as inst:
            print(f'fail to fetch failed kw tags for {atc_name} due to {inst}')

    p = re.compile(r'Test timeout [0-9]+ hours active. [0-9]+\.[0-9]+ seconds left\.')  # remove the first debug message of kw
    for kw_tag in failed_kw_tags:
        #first level kw name + args
        kw_name = kw_tag.xpath('./@name')[0]
        kw_name = kw_name.replace(' ', '_')
        # print(f'kw name is {kw_name}')
        kw_args = kw_tag.xpath('./arguments//text()')
        # print(kw_args)
        if kw_args:
            kw_args = [each for each in kw_args if each != '\r\n']
            kw_args = [each for each in kw_args if each != '\n']
            #print(kw_args)
            test_messages.append(kw_name + ' '*4 + " ".join(kw_args) + '\n')    # add kw name + args
        else:
            test_messages.append(kw_name + '\n')
        kw_msg_tags = kw_tag.xpath('./msg')
        for kw_msg_tag in kw_msg_tags:
            try:
                tmp_msg = kw_msg_tag.xpath('./text()')[0]
                if tmp_msg and not(p.search(tmp_msg)):
                    test_messages.append(tmp_msg + '\n')
            except:
                pass

        child_kw_tags = kw_tag.xpath('.//kw')
        for child_kw in child_kw_tags:
            child_kw_name = child_kw.xpath('./@name')[0]
            child_kw_name = child_kw_name.replace(' ', '_')
            child_kw_arg = child_kw.xpath('./arguments//text()')
            if child_kw_arg:
                child_kw_arg = [each for each in child_kw_arg if each != '\r\n']
                child_kw_arg = [each for each in child_kw_arg if each != '\n']
                test_messages.append(child_kw_name + ' '*4 + " ".join(child_kw_arg) + '\n')
            else:
                test_messages.append(child_kw_name + '\n')
            child_kw_msg_tags = child_kw.xpath('./msg')
            for child_kw_msg_tag in child_kw_msg_tags:
                try:
                    tmp_msg = child_kw_msg_tag.xpath('./text()')[0]
                    if tmp_msg and not(p.search(tmp_msg)):
                        test_messages.append(tmp_msg + '\n')
                except:
                    pass

    test_messages = [each for each in test_messages if each]

    print(len(test_messages))
    print(f'retrieve failed step complete')
    return test_messages

def _retrieve_failed_step_from_xml(file_name,atc_name='',kw_name='',kw_type='setup'):
    '''
    retrieve the failed text from xml file, return a string
    file_name: output.xml or atc xml file
    atc_name: failed atc name
    kw_name: failed kw name, only be used with parameter 'kw_type'
    kw_type: 'setup' or 'teardown', only be used with parameter 'kw_name'
    '''
    test_messages = []

    if any([atc_name,kw_name]):
        pass
    else:
        print(f'cannot retrieve fail step, please input either "atc_name" or "kw_name"')
        return test_messages

    try:
        parser = etree.XMLParser(encoding='utf-8',huge_tree=True)
        tree = etree.parse(os.path.join(LOG_DIR,file_name),parser=parser)
        if atc_name:
            print(f'start to retrieve failed step of case {atc_name}')
            xpath = f'//test[@name="{atc_name}"]'
        else:
            print(f'start to retrieve failed step of kw {kw_name}')
            xpath = f'//kw[@type="{kw_type}" and @name="{kw_name}"]'
        main_tag = tree.xpath(xpath)[0]
    except Exception as inst:
        print(f'cannot fetch kw tags for {atc_name} {kw_name} due to {inst}')
        return test_messages

    if atc_name:
        try:
            status_tag = main_tag.xpath('./status')[0]
            test_messages = status_tag.xpath('./text()')[0]
        except:
            pass
    else:
        failed_kw_tags = []
        # failed_kw_names = []
        kw_tags = main_tag.xpath('.//kw')
        for each in kw_tags:
            try:
                kw_name = each.xpath('./@name')[0]
                kw_result = each.xpath('./status/@status')[0]
                if kw_result != 'PASS':
                    failed_kw_tags.append(each)
                    # failed_kw_names.append(kw_name)
            except Exception as inst:
                print(f'fail to fetch failed kw tags for {atc_name} due to {inst}')

        # print(failed_kw_names)
        p = re.compile(r'Keyword timeout [0-9]+ minutes active. [0-9]+\.[0-9]+ seconds left\.')  # remove the first debug message of kw
        for kw_tag in failed_kw_tags:
            msg_tags = kw_tag.xpath('./msg')
            for msg_tag in msg_tags:
                try:
                    tmp_msg = msg_tag.xpath('./text()')[0]
                    if tmp_msg and not(p.search(tmp_msg)):
                        test_messages.append(tmp_msg + '\n')
                except:
                    pass
        test_messages = ' '.join(test_messages)

    # test_messages = [each for each in test_messages if each]
    print(len(test_messages))
    print(f'retrieve failed step complete')
    return test_messages

def _retrieve_failed_parent_step_from_xml(file_name,atc_name):
    '''
    获取case 失败的parent setup step
    废弃
    '''
    test_messages = []
    failed_kw_tags = []
    print(f'start to retrieve failed setup step of case {atc_name}')
    try:
        parser = etree.XMLParser(encoding='utf-8',huge_tree=True)
        tree = etree.parse(os.path.join(LOG_DIR,file_name),parser=parser)
        test_tag = tree.xpath(f'//test[@name="{atc_name}"]')[0]
        test_id = test_tag.xpath('./@id')[0]
        test_id_list = test_id.split('-')
    except Exception as inst:
        print('cannot fetch test id for %s due to %s, fail to retrieve parent setup steps' % (atc_name,inst))
        return test_messages

    p = re.compile(r'Test timeout [0-9]+ hours active. [0-9]+\.[0-9]+ seconds left\.')  # remove the first debug message of kw
    for i in range(1,len(test_id_list)):
        test_id = '-'.join(test_id_list[:-i])
        suite_tag = tree.xpath(f'//suite[@id="{test_id}"]')[0]
        suite_setup_kw_tags = suite_tag.xpath('./kw[@type="setup"]')  #当前这个suite 直接的setup keyword(第一层)

        for each in suite_setup_kw_tags:
            kw_result = each.xpath('./status/@status')[0]
            if kw_result != 'PASS':
                failed_kw_tags.append(each)

        if failed_kw_tags:
            for kw_tag in failed_kw_tags:
                #first level kw name + args
                kw_name = kw_tag.xpath('./@name')[0]
                kw_name = kw_name.replace(' ', '_')
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
                    try:
                        tmp_msg = kw_msg_tag.xpath('./text()')[0]
                        if tmp_msg and not(p.search(tmp_msg)):
                            test_messages.append(tmp_msg + '\n')
                    except:
                        pass

                #child kw + args + msg
                child_kw_tags = kw_tag.xpath('.//kw')
                for child_kw in child_kw_tags:
                    child_kw_name = child_kw.xpath('./@name')[0]
                    child_kw_name = child_kw_name.replace(' ', '_')
                    child_kw_arg = child_kw.xpath('./arguments//text()')
                    if child_kw_arg:
                        child_kw_arg = [each for each in child_kw_arg if each != '\r\n']
                        child_kw_arg = [each for each in child_kw_arg if each != '\n']
                        test_messages.append(child_kw_name + ' '*4 + " ".join(child_kw_arg) + '\n')
                    else:
                        test_messages.append(child_kw_name + '\n')
                    child_kw_msg_tags = child_kw.xpath('./msg')
                    for child_kw_msg_tag in child_kw_msg_tags:
                        try:
                            tmp_msg = child_kw_msg_tag.xpath('./text()')[0]
                            if tmp_msg and not(p.search(tmp_msg)):
                                test_messages.append(tmp_msg + '\n')
                        except:
                            pass
            break

    print(len(test_messages))
    print(f'retrieve failed setup step of complete')
    return test_messages

def _mycallback_ti_documents(x):
    TI_DOCUMENTS_LIST.append(x)

def _generate_document_files_for_ti(robot_log_url,ti_id, job_name, job_num, batch_name, domain_name, atc_name, fix_version, bug_id, bug_status):
    '''
    generate atc/kw text files contain error messages/steps
    return a list: TI_ID, JOB_NAME, JOB_NUM, BATCH_NAME, DOMAIN_NAME, ATC_NAME, BUG_ID, FIX_VERSION, BUG_STATUS, ROBOT_LOG, 
    will be used by generate_input_excel_for_ml()
    '''
    job_index = job_name+ '_' + job_num + '_' + batch_name+ '_'  + domain_name
    ti_name = job_index + '_' + atc_name
    xml_file = job_index + '_output.xml'
    # res = []
    res = [ti_id, job_name, job_num, batch_name,domain_name, atc_name, bug_id, fix_version, bug_status]
    # res.append(ti_name)
    # res.append(bug_id)
    # res.append(fix_version)
    # res.append(bug_status)

    print('*'*5 +job_index + ':' + ' '*4 + atc_name + '*'*5)
    if robot_log_url and os.path.exists(os.path.join(LOG_DIR,xml_file)):
        if atc_name.startswith('setup:'):
            atc_name = atc_name.lstrip('setup:')
            ti_name = ti_name.replace(':','_')
            tmp_steps = _retrieve_failed_step_from_xml(xml_file,kw_name=atc_name)
            if tmp_steps:
                atc_file_name = ti_name +'_ROBOT_MESSAGES.txt'
                with open(os.path.join(LOG_DIR,atc_file_name),'w',encoding='UTF-8') as fp:
                    fp.write(tmp_steps)
                res.append(atc_file_name)
            else:
                res.append('None')
        elif atc_name.startswith('teardown:'):
            atc_name = atc_name.lstrip('teardown:')
            ti_name = ti_name.replace(':','_')
            tmp_steps = _retrieve_failed_step_from_xml(xml_file,kw_name=atc_name,kw_type='teardown')
            if tmp_steps:
                atc_file_name = ti_name +'_ROBOT_MESSAGES.txt'
                with open(os.path.join(LOG_DIR,atc_file_name),'w',encoding='UTF-8') as fp:
                    fp.write(tmp_steps)
                res.append(atc_file_name)
            else:
                res.append('None')
        else:
            tmp_steps = _retrieve_failed_step_from_xml(xml_file, atc_name)
            #use atc xml instead of output.xml if fail to parse steps
            if not tmp_steps:
                atc_xml_file = _download_atc_xml_file(robot_log_url,job_name, job_num, batch_name, domain_name,atc_name)
                tmp_steps = _retrieve_failed_step_from_xml(atc_xml_file, atc_name) 
            #if still return empty, it is probably a NOT RUN case due to parent setup failure, so retrieve failed setup steps
            # if not tmp_steps:
            #     tmp_steps = _retrieve_failed_parent_step_from_xml(xml_file, atc_name) 
            if tmp_steps:
                atc_file_name = ti_name +'_ROBOT_MESSAGES.txt'
                with open(os.path.join(LOG_DIR,atc_file_name),'w',encoding='UTF-8') as fp:
                    fp.write(tmp_steps)
                res.append(atc_file_name)
            else:
                res.append('None')
    else:
        print(f'cannot find ROBOT log url or required xml file does not exist for TI: {ti_name}')
        res.append('None')

    # print(res)
    print('*'*5 + job_index + ':' + ' '*4 + atc_name + ' complete...' + '*'*5)
    return res

class Read_File(object):
    '''
    This class is used to read all the documents for machine learning
    return a python generator to save memory
    '''
    def __init__(self, input_file):
        self.input_file = input_file
        self.file_list = []
        self.stop_word_list = COMM_STOP_WORD_LIST + CUST_STOP_WORD_LIST

        if os.path.exists(self.input_file):
            df = pd.read_excel(self.input_file,engine='openpyxl')
            for index, row in df.iterrows():
                # t= (row['ROBOT_LOG'], row['TRAFFIC_LOG'])
                t= (row['ROBOT_LOG'],)
                self.file_list.append(t)
        else:
            print(f'{self.input_file} does not exist...')
        # print('file name list is %s' % str(self.file_list))
    
    def _text_process(self,text):
        '''
        input 'text' is a string
        '''
        text = text.lower()
        text = text.replace('\t',' ')
        text = text.replace('\n',' ')
        text = text.replace('\r\n',' ')
        text = text.replace('\r',' ')
        text = text.replace('&nbsp',' ')
        text = text.replace(',',' ')
        text = text.replace('|',' ')
        text = text.replace("'u",' ')
        text = text.replace('"',' ')
        text = text.replace("'",' ')
        text = text.replace('{',' ')
        text = text.replace('}',' ')
        text = text.replace(':',' ')
        text = text.replace('$',' ')
        text = text.replace('&',' ')
        text = text.replace('(',' ')
        text = text.replace(')',' ')
        text = text.replace('>',' ')
        text = text.replace('<',' ')
        text = text.replace('/',' ')
        text = text.replace('!',' ')
        text = text.replace('#',' ')
        text = text.replace('=',' ')
        text = text.replace('-',' ')
        text = text.replace('*',' ')
        text = text.replace('[',' ')
        text = text.replace(']',' ')
        text = text.replace(';',' ')
        text = text.replace('..',' ')
        text = text.replace('...',' ')
        text = text.replace('....',' ')
        text = text.replace('.....',' ')
        text = text.replace('......',' ')
        return text

    def __iter__(self):
        for each in self.file_list:
            log_text = ''
            robot_log_file = os.path.join(LOG_DIR,each[0])
            if os.path.exists(robot_log_file):
                with open(robot_log_file, 'r', encoding='utf-8') as fp:
                    log_text = fp.read()
            tmp_list = [x for x in self._text_process(log_text).split(' ') if x] # split the combined text into a list
            tmp_list = [x for x in tmp_list if x not in self.stop_word_list]         #remove stop words
            tmp_list = [x for x in tmp_list if re.search(r'[a-z]', x)]        #remove words does not contain any letters
            tmp_list = [x for x in tmp_list if not re.search(r'^0x[a-f0-9]+', x)]   #remove hex string
            tmp_list = [x.rstrip('.') for x in tmp_list]

            yield tmp_list

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
    no_above_rate=0.8
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

def validate_ti_reference_by_job(job_name,job_num,batch_name,domain_name,build_id,ml_excel):
    print('Load AI Analysis Model')
    ai_dictionary=corpora.Dictionary.load_from_text(os.path.join(COMP_DIR,'auto_ti.dict'))
    ai_lsi=models.LsiModel.load(os.path.join(COMP_DIR,'auto_ti_lis_mode.mo'))
    ai_index=similarities.MatrixSimilarity.load(os.path.join(COMP_DIR,'auto_ti_lsi_index.ind'))

    atc_result_list = _retrieve_history_ti_by_job(job_name,job_num,batch_name,domain_name,build_id)
    robot_log_url = _get_robot_url_of_ti(job_name,job_num,batch_name,domain_name,build_id=build_id)
    xml_file = _download_robot_xml_file(robot_log_url,job_name,job_num,batch_name,domain_name)

    #read ml excel to refer bug type
    df = pd.read_excel(os.path.join(LOG_DIR,ml_excel),engine='openpyxl')
    df.fillna('',inplace=True)
    history_ti_dict = df.T.to_dict('list')
    job_index = job_name+ '_' + job_num + '_' + batch_name+ '_'  + domain_name
    print(f'Start to auto analyze new TI for job: {job_index}')
    
    match_num = 0.0
    ana_num = 0.0 # count analyzed ti number
    total_num = len(atc_result_list)

    #dict to pandas df
    ti_name_list = []
    ti_type_list =[] # recommended ti type
    match_list = []
    ref_bug_list = [] # referenced ti type

    if robot_log_url and os.path.exists(os.path.join(LOG_DIR,xml_file)):
        for each in atc_result_list:
            atc_name = each[0]
            ti_name = job_index + '_' + atc_name
            atc_bug_type = each[1]
            file_list_to_reference = []
            print('#'*30)
            print(job_index + ':' + ' '*4 + atc_name)

            ti_name_list.append(ti_name)
            if atc_name.startswith('setup:'):
                atc_name = atc_name.lstrip('setup:')
                ti_name = ti_name.replace(':','_')
                tmp_steps = _retrieve_failed_step_from_xml(xml_file,kw_name=atc_name)
                if tmp_steps:
                    atc_file_name = ti_name +'_ROBOT_MESSAGES.txt'
                    with open(os.path.join(LOG_DIR,atc_file_name),'w',encoding='UTF-8') as fp:
                        fp.writelines(tmp_steps)
                    file_list_to_reference.append(atc_file_name)
            elif atc_name.startswith('teardown:'):
                atc_name = atc_name.lstrip('teardown:')
                ti_name = ti_name.replace(':','_')
                tmp_steps = _retrieve_failed_step_from_xml(xml_file,kw_name=atc_name,kw_type='teardown')
                if tmp_steps:
                    atc_file_name = ti_name +'_ROBOT_MESSAGES.txt'
                    with open(os.path.join(LOG_DIR,atc_file_name),'w',encoding='UTF-8') as fp:
                        fp.writelines(tmp_steps)
                    file_list_to_reference.append(atc_file_name)
            else:
                tmp_steps = _retrieve_failed_step_from_xml(xml_file, atc_name)
                #use atc xml instead of output.xml if fail to parse steps
                if not tmp_steps:
                    atc_xml_file = _download_atc_xml_file(robot_log_url,job_name, job_num, batch_name, domain_name,atc_name)
                    tmp_steps = _retrieve_failed_step_from_xml(atc_xml_file, atc_name) 
                #if still return empty, it is probably a NOT RUN case due to parent setup failure, so retrieve failed setup steps
                if not tmp_steps:
                    tmp_steps = _retrieve_failed_parent_step_from_xml(xml_file, atc_name) 
                if tmp_steps:
                    atc_file_name = ti_name +'_ROBOT_MESSAGES.txt'
                    with open(os.path.join(LOG_DIR,atc_file_name),'w',encoding='UTF-8') as fp:
                        fp.writelines(tmp_steps)
                    file_list_to_reference.append(atc_file_name)

            sims_list = _sims_compare(ai_dictionary,ai_lsi,ai_index,file_list_to_reference)
            if sims_list:
                rec_ti_type, ref_ti_list = _reference_method_2(sims_list, history_ti_dict)
                if rec_ti_type:
                    ana_num +=1
                    ti_type_list.append(rec_ti_type)
                    ref_bug_list.append(ref_ti_list)
                    if atc_bug_type == rec_ti_type:
                        match_num += 1
                        match_list.append('1')
                        print(f'actual ti type: {atc_bug_type}, recomended ti type: {rec_ti_type}, MATCH')
                    else:
                        match_list.append('0')
                        print(f'actual ti type: {atc_bug_type}, recomended ti type: {rec_ti_type}, NOT MATCH')
                else:
                    ti_type_list.append('None')
                    ref_bug_list.append(ref_ti_list)
                    match_list.append('None')
                    print(f'cannot recommend ti type for {atc_name} due to too low similarities')
            else:
                ti_type_list.append('None')
                ref_bug_list.append('None')
                match_list.append('None')
                print(f'cannot recommend ti type for {atc_name} due to no query document')

    else:
        print(f'cannot find ROBOT log url or required xml file does not exist for TI')
    
    print('total TI number: %d, analyzed %d TIs, matched %d TIs' % (total_num, int(ana_num), int(match_num)))
    print('reference accuracy is %f' % (match_num/ana_num,))

    #export result to Excel
    d = {
    'TI_NAME': ti_name_list,
    'TI_TYPE': ti_type_list,
    'MATCH': match_list,
    'RFE_TI': ref_bug_list
    }

    new_df = pd.DataFrame(data=d)
    print('new df shape is %s' % str(new_df.shape))

    #use xlsxwriter to write xlsx
    file_name = f'validate_ti_build_result_{job_index}.xlsx'
    sheet_name = 'Result'
    writer = pd.ExcelWriter(file_name, engine='xlsxwriter')
    new_df.to_excel(writer,index=False,sheet_name=sheet_name)

    workbook  = writer.book
    worksheet = writer.sheets[sheet_name]
    format1 = workbook.add_format({'text_wrap': True,'border': 1,'align': 'left'})
    worksheet.set_column('A:A', 60, format1)
    worksheet.set_column('B:C', 10, format1)
    worksheet.set_column('D:D', 120, format1)
    writer.save()
    print('excel for ti validation completed...')

    shutil.move(file_name,os.path.join(LOG_DIR,file_name))

def _retrieve_history_ti_by_job(job_name,job_num,batch_name,domain_name,build_id):
    history_ti_list = []
    if all([job_name,job_num,build_id]):
        pass
    else:
        print('input args error, please give correct job_name, job_num and build_id')
        return history_ti_list

    print('start to retrieve history ti by job...')
    # Connect to the database
    connection = pymysql.connect(host='135.249.27.193',
        user='smtlab',
        password='smtlab123',
        database='robot2')

    with connection:
        with connection.cursor() as cursor:
            sql = "SELECT ATCName,frClassify FROM testATCResults \
                  WHERE testResult != 'PASS' and jobName = '%s' and jobNum = %s and batchName = '%s' and DomainName = '%s' \
                  and buildID = %s and frClassify in ('SW','ATC','ENV','SW-ONT')" %(job_name,job_num,batch_name,domain_name,build_id)
            try:
                cursor.execute(sql)
                history_ti_list = cursor.fetchall()
            except Exception as inst:
                print('Error, fail to fetch data from DB due to %s' % inst)
                return None

    print(len(history_ti_list))
    return history_ti_list

def _retrieve_history_ti_by_build(build_id,keep_num=None,fetch_num=None,val_domain=None):
    '''
    retrieve history ti according to build id, if val_domain is given, only return TI of this domain
    be called by validate_ti_reference_by_build()
    '''
    print('start to retrieve history ti by build...')
    moswa_job_list = _get_job_names_from_file('MOSWA_JOB_NAME.txt')

    # Connect to the database
    connection = pymysql.connect(host='135.249.27.193',
        user='smtlab',
        password='smtlab123',
        database='robot2')

    with connection:
        with connection.cursor() as cursor:
            #buildId is required when dowmload output.xml
            if val_domain:
                sql = "SELECT jobName,jobNum,batchName,DomainName,buildID,ATCName,frId,errorInfo,id FROM testATCResults \
                    WHERE testResult = 'FAIL' and buildID = %s and frClassify in ('SW','ATC') \
                    and domainName = '%s' ORDER by id DESC " % (build_id, val_domain)
            else:
                sql = "SELECT jobName,jobNum,batchName,DomainName,buildID,ATCName,frId,errorInfo,id FROM testATCResults \
                    WHERE testResult = 'FAIL' and buildID = %s and frClassify in ('SW','ATC') \
                    ORDER by id DESC " % build_id
            if fetch_num:
                sql += ' LIMIT 0,%s' % fetch_num
            try:
                cursor.execute(sql)
                history_ti_list = cursor.fetchall()
            except Exception as inst:
                print('Error, fail to fetch data from DB due to %s' % inst)
                return None

    print(len(history_ti_list))
    history_ti_list = [each for each in history_ti_list if each[0] in moswa_job_list]   #remove entries not in moswa batch job
    print(len(history_ti_list))
    if keep_num:
        history_ti_list = history_ti_list[:keep_num]
    print(len(history_ti_list))
    return history_ti_list

def validate_ti_reference_by_build(build_id,ml_excel,val_num=None,fetch_num=None,val_domain=None):
    #load ai model
    print('Load AI Analysis Model')
    ai_dictionary=corpora.Dictionary.load_from_text(os.path.join(COMP_DIR,'auto_ti.dict'))
    ai_lsi=models.LsiModel.load(os.path.join(COMP_DIR,'auto_ti_lis_mode.mo'))
    ai_index=similarities.MatrixSimilarity.load(os.path.join(COMP_DIR,'auto_ti_lsi_index.ind'))

    jira_inst = JIRA('https://jiradc2.ext.net.nokia.com/', auth=('jieminbz', 'Jim#2346'))
    atc_result_list = _retrieve_history_ti_by_build(build_id=build_id,keep_num=val_num,fetch_num=fetch_num,val_domain=val_domain)

    #read ml excel to refer bug type
    df = pd.read_excel(os.path.join(LOG_DIR,ml_excel),engine='openpyxl')
    df.fillna('',inplace=True)
    history_ti_dict = df.T.to_dict('list')

    #download all needed output.xml
    _download_robot_xml_file_mp(ti_list=atc_result_list)

    '''
    convert atc_result_list to df and remove duplicated rows by bug_id
    atc_result_list : jobName,jobNum,batchName,DomainName,buildID,ATCName,frId,errorInfo,id 
    '''
    df = pd.DataFrame(atc_result_list,columns=['job_name','job_num','batch_name','domain_name','build_id','atc_name','bug_id','error_info','ti_id'])
    df.sort_values(by=['ti_id'],inplace=True)
    df.drop_duplicates(subset=['job_name','job_num','batch_name','domain_name','bug_id'],inplace=True)
    df.reset_index(drop=True,inplace=True)
    print('TI entries after remove duplcated ones is %s' % len(df))

    match_num = 0.0
    ana_num = 0.0 # count analyzed ti number
    total_num = len(df)

    #dict to pandas df
    ti_name_list = []
    ti_type_list =[] # recommended ti type
    actual_bug_id_list = []
    actual_ti_type_list = []
    ti_error_info_list = []
    match_list = []
    ref_bug_list = [] # referenced ti type

    iter_count = 0
    # for each_ti in atc_result_list:
    for index, row in df.iterrows():
        job_name = row['job_name']
        job_num = str(row['job_num'])
        batch_name = row['batch_name']
        domain_name = row['domain_name']
        atc_name = row['atc_name']
        bug_id = row['bug_id']
        error_info = row['error_info']

        job_index = job_name+ '_' + job_num + '_' + batch_name+ '_'  + domain_name
        ti_name = job_index + '_' + atc_name
        print('*'*5 +job_index + ':' + ' '*4 + atc_name + '*'*5)
        iter_count +=1
        print(f'{iter_count} of {total_num}')

        #get ti bug type from Jira
        try:
            issue = jira_inst.issue(bug_id)
            fix_version = issue.fields.fixVersions[0].name
            actual_bug_type = _return_ti_type_by_fix_version(fix_version)
            # reset bug type according to below rules
            affects_version = issue.fields.versions[0].name
            labels = issue.fields.labels
            labels = ','.join(labels).upper()
            if fix_version.upper() == 'LSRATC' and affects_version.upper() != 'LSRATC':
                actual_bug_type = 'SW'
            # if labels.upper() in ['ATC_RCRDROP_IMPACT', 'ATC_SWIMPACT']:
            #     actual_bug_type = 'SW'
        except:
            print(f'fail to get actual ti type of {bug_id}')
            continue

        print(f'bug_id is {bug_id},fix_version is {fix_version}, actual bug type is {actual_bug_type}')

        robot_log_url = ROBOT_LOG_URL_DICT.get(job_index,'')
        xml_file = job_index + '_output.xml'

        if robot_log_url and os.path.exists(os.path.join(LOG_DIR,xml_file)):
            file_list_to_reference = []
            ti_name_list.append(ti_name)
            actual_bug_id_list.append(bug_id)
            actual_ti_type_list.append(actual_bug_type)
            ti_error_info_list.append(error_info)
            if atc_name.startswith('setup:'):
                atc_name = atc_name.lstrip('setup:')
                ti_name = ti_name.replace(':','_')
                tmp_steps = _retrieve_failed_step_from_xml(xml_file,kw_name=atc_name)
                if tmp_steps:
                    atc_file_name = ti_name +'_ROBOT_MESSAGES.txt'
                    with open(os.path.join(LOG_DIR,atc_file_name),'w',encoding='UTF-8') as fp:
                        fp.writelines(tmp_steps)
                    file_list_to_reference.append(atc_file_name)
            elif atc_name.startswith('teardown:'):
                atc_name = atc_name.lstrip('teardown:')
                ti_name = ti_name.replace(':','_')
                tmp_steps = _retrieve_failed_step_from_xml(xml_file,kw_name=atc_name,kw_type='teardown')
                if tmp_steps:
                    atc_file_name = ti_name +'_ROBOT_MESSAGES.txt'
                    with open(os.path.join(LOG_DIR,atc_file_name),'w',encoding='UTF-8') as fp:
                        fp.writelines(tmp_steps)
                    file_list_to_reference.append(atc_file_name)
            else:
                tmp_steps = _retrieve_failed_step_from_xml(xml_file, atc_name)
                #use atc xml instead of output.xml if fail to parse steps
                if not tmp_steps:
                    atc_xml_file = _download_atc_xml_file(robot_log_url,job_name, job_num, batch_name, domain_name,atc_name)
                    tmp_steps = _retrieve_failed_step_from_xml(atc_xml_file, atc_name) 
                #if still return empty, it is probably a NOT RUN case due to parent setup failure, so retrieve failed setup steps
                # if not tmp_steps:
                #     tmp_steps = _retrieve_failed_parent_step_from_xml(xml_file, atc_name) 
                if tmp_steps:
                    atc_file_name = ti_name +'_ROBOT_MESSAGES.txt'
                    with open(os.path.join(LOG_DIR,atc_file_name),'w',encoding='UTF-8') as fp:
                        fp.writelines(tmp_steps)
                    file_list_to_reference.append(atc_file_name)
            
            sims_list = _sims_compare(ai_dictionary,ai_lsi,ai_index,file_list_to_reference)
            if sims_list:
                # rec_ti_type, ref_ti_list = _reference_method_2(sims_list, history_ti_dict)
                rec_ti_type, ref_ti_list = _reference_method_3(sims_list, history_ti_dict,job_name, domain_name, atc_name)
                if rec_ti_type:
                    ana_num +=1
                    ti_type_list.append(rec_ti_type)
                    ref_bug_list.append(ref_ti_list)
                    if actual_bug_type == rec_ti_type:
                        match_num += 1
                        match_list.append('1')
                        print(f'actual ti type: {actual_bug_type}, recomended ti type: {rec_ti_type}, MATCH')
                    else:
                        match_list.append('0')
                        print(f'actual ti type: {actual_bug_type}, recomended ti type: {rec_ti_type}, NOT MATCH')
                else:
                    ti_type_list.append('None')
                    ref_bug_list.append(ref_ti_list)
                    match_list.append('None')
                    print(f'cannot recommend ti type for {atc_name} due to too low similarities')
            else:
                ti_type_list.append('None')
                ref_bug_list.append('None')
                match_list.append('None')
                print(f'cannot recommend ti type for {atc_name} due to no query document')

        else:
            print(f'cannot find ROBOT log url or required xml file does not exist for TI: {ti_name}')

    if total_num > 0 and ana_num > 0:
        print('total TI number: %d, analyzed %d TIs, matched %d TIs' % (total_num, int(ana_num), int(match_num)))
        print('reference accuracy is %f' % (match_num/ana_num,))
    else:
        print('total TI number: %d, analyzed %d TIs' % (total_num, int(ana_num)))
        print('no TI recommend')

    #export result to Excel
    d = {
    'TI_NAME': ti_name_list,
    'REC_TI_TYPE': ti_type_list,
    'ACT_BUG_ID': actual_bug_id_list,
    'ACT_TI_TYPE': actual_ti_type_list,
    'MATCH': match_list,
    'ERROR_INFO': ti_error_info_list,
    'RFE_TI': ref_bug_list
    }

    new_df = pd.DataFrame(data=d)
    print('new df shape is %s' % str(new_df.shape))

    #use xlsxwriter to write xlsx
    tmp_name = f'validate_ti_build_result_{build_id}'
    if val_domain:
        file_name = tmp_name + f'_{val_domain}.xlsx'
    else:
        file_name = tmp_name  + '.xlsx'
    sheet_name = 'Result'
    writer = pd.ExcelWriter(file_name, engine='xlsxwriter')
    new_df.to_excel(writer,index=False,sheet_name=sheet_name)

    workbook  = writer.book
    worksheet = writer.sheets[sheet_name]
    format1 = workbook.add_format({'text_wrap': True,'border': 1,'align': 'left'})
    worksheet.set_column('A:A', 50, format1)
    worksheet.set_column('B:E', 13, format1)
    worksheet.set_column('F:G', 85, format1)
    writer.save()
    print('excel for ti validation completed...')

    shutil.move(file_name,os.path.join(LOG_DIR,file_name))

def _sims_compare(dictionary_obj,lsi_obj,index_obj,query0,qtype='FileList'):
    '''
    calculate similarity according to query0 text
    qtype: indicate whether query0 is a file name list(default) or text list
    return a list which contains history ti index and sorted similarity, like
    [(10, 1.0), (9, 0.7924244), (7, 0.65759844), (17, 0.57193935), (18, 0.5716857), (13, 0.46947253)...]
    '''
    query=[]    #word list
    if qtype == 'FileList':
        for each in query0:
            file_path =  os.path.join(LOG_DIR, each)
            if os.path.exists(file_path):
                with open(file_path,'r') as fp:
                    content = fp.readlines()
                for line in content:
                    line = line.lower()
                    line = line.replace('\t',' ')
                    line = line.replace('\n',' ')
                    line = line.replace('\r\n',' ')
                    line = line.replace('\r',' ')
                    line = line.replace('&nbsp',' ')
                    line = line.replace(',',' ')
                    line = line.replace('|',' ')
                    line = line.replace("'u",' ')
                    line = line.replace('"',' ')
                    line = line.replace("'",' ')
                    line = line.replace('{',' ')
                    line = line.replace('}',' ')
                    line = line.replace(':',' ')
                    line = line.replace('$',' ')
                    line = line.replace('&',' ')
                    line = line.replace('(',' ')
                    line = line.replace(')',' ')
                    line = line.replace('>',' ')
                    line = line.replace('<',' ')
                    line = line.replace('/',' ')
                    line = line.replace('!',' ')
                    line = line.replace('#',' ')
                    line = line.replace('=',' ')
                    line = line.replace('-',' ')
                    line = line.replace('*',' ')
                    line = line.replace('[',' ')
                    line = line.replace(']',' ')
                    line = line.replace(';',' ')
                    line = line.replace('..',' ')
                    line = line.replace('...',' ')
                    line = line.replace('....',' ')
                    line = line.replace('.....',' ')
                    line = line.replace('......',' ')
                    tmp_list = [x for x in line.split(' ') if x]
                    tmp_list = [x for x in tmp_list if x not in COMM_STOP_WORD_LIST]
                    tmp_list = [x for x in tmp_list if x not in CUST_STOP_WORD_LIST]
                    tmp_list = [x for x in tmp_list if re.search(r'[a-z]', x)]        #remove words does not contain any letters
                    tmp_list = [x for x in tmp_list if not re.search(r'^0x[a-f0-9]+', x)]   #remove hext string
                    tmp_list = [x.strip('.') for x in tmp_list]
                    query.extend(tmp_list)
            else:
                print(f'cannot find {file_path}')
    elif qtype == 'Text':
        query0=str(query0).strip()
        query0 = query0.lower()
        query0 = query0.replace('\t',' ')
        query0 = query0.replace('\n',' ')
        query0 = query0.replace('\r\n',' ')
        query0 = query0.replace('\r',' ')
        query0 = query0.replace('&nbsp',' ')
        query0 = query0.replace(',',' ')
        query0 = query0.replace('|',' ')
        query0 = query0.replace("'u",' ')
        query0 = query0.replace('"',' ')
        query0 = query0.replace("'",' ')
        query0 = query0.replace('{',' ')
        query0 = query0.replace('}',' ')
        query0 = query0.replace(':',' ')
        query0 = query0.replace('$',' ')
        query0 = query0.replace('&',' ')
        query0 = query0.replace('(',' ')
        query0 = query0.replace(')',' ')
        query0 = query0.replace('>',' ')
        query0 = query0.replace('<',' ')
        query0 = query0.replace('/',' ')
        query0 = query0.replace('!',' ')
        query0 = query0.replace('#',' ')
        query0 = query0.replace('=',' ')
        query0 = query0.replace('-',' ')
        query0 = query0.replace('*',' ')
        query0 = query0.replace('[',' ')
        query0 = query0.replace(']',' ')
        query0 = query0.replace(';',' ')
        query0 = query0.replace('..',' ')
        query0 = query0.replace('...',' ')
        query0 = query0.replace('....',' ')
        query0 = query0.replace('.....',' ')
        query0 = query0.replace('......',' ')
        query = [x for x in query0.split(' ') if x]
        query = [x for x in query if x not in COMM_STOP_WORD_LIST]
        query = [x for x in query if x not in CUST_STOP_WORD_LIST]
        query = [x for x in query if re.search(r'[a-z]', x)]        #remove words does not contain any letters
        query = [x for x in query if not re.search(r'^0x[a-f0-9]+', x)]   #remove hext string
        query = [x.strip('.') for x in query]
    else:
        print("wrong qtype value, should be 'FileList' or 'Text'")

    if query:
        query_bow = dictionary_obj.doc2bow(query)
        query_lsi = lsi_obj[query_bow]
        sims = index_obj[query_lsi]
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

    ref_ti_list = []
    rec_ti_type = ''

    for each in sims_list:
        index = each[0]
        score = each[1]
        ti_name = history_ti_dict[index][0]
        bug_id = history_ti_dict[index][1]
        fix_version = history_ti_dict[index][2]
        bug_status = history_ti_dict[index][3]
        t = (ti_name,score,bug_id,fix_version,bug_status)
        ref_ti_list.append(t)

    if ref_ti_list[0][1] > 0.8:
        rec_ti_type = _return_ti_type_by_fix_version(ref_ti_list[0][3])

    print('most 5 similar ti: %s' % str(ref_ti_list))
    print('reference method 2 recommended ti type: %s' % rec_ti_type)

    return rec_ti_type, ref_ti_list

def _reference_method_2(sims_list,history_ti_dict):
    '''
    method 2: 取相似度最高的5个, 然后计算每类TI的得分, 相似度小于0.8的不予参考
    '''
    print('ti reference method 2')

    sims_list = sims_list[:5] # 取前5个
    ref_ti_list = []
    ti_type_score_dict = {}
    rec_ti_type = ''
    for each in sims_list:
        index = each[0]
        score = each[1]
        ti_name = history_ti_dict[index][0]
        bug_id = history_ti_dict[index][1]
        fix_version = history_ti_dict[index][2]
        bug_status = history_ti_dict[index][3]
        t = (ti_name,score,bug_id,fix_version,bug_status)
        ref_ti_list.append(t)
        if float(score) > 0.8:
            if fix_version in ti_type_score_dict:
                ti_type_score_dict[fix_version] += score
            else:
                ti_type_score_dict[fix_version] = score

    sorted_score_list = sorted(ti_type_score_dict.items(), key = lambda x : x[1], reverse=True)
    if sorted_score_list:
        rec_ti_type = _return_ti_type_by_fix_version(sorted_score_list[0][0])

    print('most 5 similar ti: %s' % str(ref_ti_list))
    print('ti type score list: %s' % str(sorted_score_list))
    print('reference method 2 recommended ti type: %s' % rec_ti_type)

    return rec_ti_type, ref_ti_list

def _reference_method_3(sims_list,history_ti_dict,job_name,domain_name,atc_name):
    '''
    adjust priority if job_name, domain_name and atc_name matches
    '''
    # print('ti reference method 3')

    sims_list = sims_list[:3]
    ref_ti_list = []
    rec_ti_type = ''

    for each in sims_list:
        index = each[0]
        score = each[1]
        ref_job_name = history_ti_dict[index][1]
        ref_job_num = str(history_ti_dict[index][2])
        ref_batch_name = history_ti_dict[index][3]
        ref_domain_name = history_ti_dict[index][4]
        ref_atc_name = history_ti_dict[index][5]
        ref_bug_id = history_ti_dict[index][6]
        ref_bug_info = _retrieve_current_bug_info_from_jira(ref_bug_id)
        ref_fix_version = ref_bug_info.get('fix_version')
        ref_bug_status = ref_bug_info.get('bug_status')
        ref_ti_name = ref_job_name+ '_' + ref_job_num + '_' + ref_batch_name + '_'  + ref_domain_name  + '_' + ref_atc_name
        #adjust socre
        bonus = 0.0
        if atc_name == ref_atc_name:
            bonus += 0.05
        if job_name and job_name == ref_job_name:
            bonus += 0.01
        if domain_name and domain_name == ref_domain_name:
            bonus += 0.02
        score_adj = score * (1 + bonus)
        t = (ref_ti_name,score_adj,ref_bug_id,ref_fix_version,ref_bug_status,score)
        ref_ti_list.append(t)
    
    #sort ref_ti_list again by score
    ref_ti_list = sorted(ref_ti_list, key=lambda x: x[1], reverse=True)

    #need original socre > 0.8
    if ref_ti_list[0][5] > 0.8:
        rec_ti_type = _return_ti_type_by_fix_version(ref_ti_list[0][3])

    # print('most 5 similar ti: %s' % str(ref_ti_list))
    # print('reference method 2 recommended ti type: %s' % rec_ti_type)

    return rec_ti_type, ref_ti_list

def _return_ti_type_by_fix_version(fix_version):
    if fix_version.lower() == 'lsratc':
        return 'ATC'
    elif fix_version.lower() == 'rlab':
        return 'ENV'
    elif fix_version.lower().startswith('bbdr'):
        return 'SW-ONT'
    else:
        return 'SW'

def _retrieve_current_bug_info_from_jira(bug_id):
    '''
    return bug's info like 'fix_version', 'status', etc
    '''
    bug_info_dict = {'bug_id': bug_id}
    jira_inst = JIRA('https://jiradc2.ext.net.nokia.com/', auth=('jieminbz', 'Jim#2346'))

    issue = jira_inst.issue(bug_id)
    fix_version = issue.fields.fixVersions[0].name
    bug_status = issue.fields.status.name
    bug_type = issue.fields.issuetype.name
    affects_version = issue.fields.versions[0].name
    labels = issue.fields.labels    # return is a list
    resolution = issue.fields.resolution

    bug_info_dict.update({'fix_version': fix_version, 'bug_status': bug_status, 'bug_type': bug_type, 'affects_version': affects_version,
        'labels': labels, 'resolution': resolution})

    return bug_info_dict

def retrieve_history_ti_by_build_list(build_id_list,keep_num=None,fetch_num=None):
    '''
    retrieve history ti per build id in 'build_id_list'
    keep_num:  total ti number returned by this method
    fetch_num: number of fetched TI in one SQL query of each build
    '''
    history_ti_list = []
    moswa_job_list = _get_job_names_from_file('MOSWA_JOB_NAME.txt')
    
    for build_id in build_id_list:
        print(f'fetch ti with build id: {build_id}')
        # Connect to the database
        connection = pymysql.connect(host='135.249.27.193',
            user='smtlab',
            password='smtlab123',
            database='robot2')

        with connection:
            with connection.cursor() as cursor:
                sql = "SELECT id,jobName,jobNum,ATCName,batchName,DomainName,buildID,testCS,testResult,frId,frClassify \
                    FROM testATCResults WHERE testResult = 'FAIL' and buildID = %s and frClassify in ('SW','ATC') \
                    ORDER by id DESC" % build_id
                if fetch_num:
                    sql += ' LIMIT 0,%s' % fetch_num
                try:
                    tmp_ti_list = []
                    cursor.execute(sql)
                    tmp_ti_list = cursor.fetchall()
                except Exception as inst:
                    print('Error, fail to fetch data from DB due to %s' % inst)

        print(len(tmp_ti_list))
        tmp_ti_list = [each for each in tmp_ti_list if each[1] in moswa_job_list]   #remove entries not in moswa batch job
        if keep_num:
            tmp_ti_list = tmp_ti_list[:keep_num]    #only return keep_num entries
        print(len(tmp_ti_list))
        history_ti_list += tmp_ti_list

    output_file = _export_history_ti_list_to_excel(history_ti_list)
    return output_file

def select_ti_for_ml(input_file):
    '''
    1. drop duplicated TI of same bug id, only keep the first one
    2. drop TI if fix_verison = 'LSRATC' while affects_verisoin not
    3. drop TI if fix_version = 'LSRATC' and labels in ['atc_swimpact', 'atc_rcrdrop_impact']
    
    '''
    df = pd.read_excel(os.path.join(LOG_DIR,input_file),engine='openpyxl')
    print('source entry num from input is %d' %len(df))
    df.dropna(subset=['JOB_NAME','JOB_NUM','ATC_NAME','BUILD_ID','CS_ID','TEST_RESULT','FIX_VERSION','BUG_ID','BUG_STATUS'],inplace=True)
    df.fillna('',inplace=True)
    df.sort_values(by=['TI_ID'],inplace=True)
    df.drop_duplicates(subset=['JOB_NAME','JOB_NUM','BATCH_NAME','DOMAIN_NAME','BUG_ID'],inplace=True)
    df.drop(df[(df.FIX_VERSION == 'LSRATC') & (df.AFFECTS_VERSION != 'LSRATC')].index,inplace=True)
    df.drop(df[(df.FIX_VERSION == 'LSRATC') & (df.LABELS.isin(['ATC_RCRDROP_IMPACT', 'ATC_SWIMPACT']))].index,inplace=True)
    df.reset_index(drop=True,inplace=True)
    print('entry num after process is %d' %len(df))
    
    file_name = 'history_ti_list_{}_selection.xlsx'.format(time.strftime('%Y%m%d'))
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
    worksheet.set_column('F:N', 12, format1)
    worksheet.set_column('O:O', 20, format1)
    writer.save()

def _sample_ti(input_file,sheet_name,sample_num):
    df = pd.read_excel(input_file,sheet_name=sheet_name,engine='openpyxl')
    df = df.sample(sample_num)

    file_name = 'tmp.xlsx'
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
    worksheet.set_column('F:M', 12, format1)
    writer.save()

def validate_ti_reference_in_file(input_file,ref_file):
    '''
    input_file: TIs in the file to validate
    ref_file: TIs in the file to references
    '''
    print('Load AI Analysis Model')
    ai_dictionary=corpora.Dictionary.load_from_text(os.path.join(COMP_DIR,'auto_ti.dict'))
    ai_lsi=models.LsiModel.load(os.path.join(COMP_DIR,'auto_ti_lis_mode.mo'))
    ai_index=similarities.MatrixSimilarity.load(os.path.join(COMP_DIR,'auto_ti_lsi_index.ind'))

    #read ref_file to generate referenace dict
    df = pd.read_excel(os.path.join(LOG_DIR,ref_file),engine='openpyxl')
    df.fillna('',inplace=True)
    history_ti_dict = df.T.to_dict('list')

    #read input_file to get TI entries to validate
    df = pd.read_excel(os.path.join(LOG_DIR,input_file),engine='openpyxl')
    df.fillna('',inplace=True)

    match_num = 0.0
    ana_num = 0.0 # count analyzed ti number
    total_num = len(df)

    #dict to pandas df
    ti_name_list = []
    ti_type_list =[] # recommended ti type
    actual_bug_id_list = []
    actual_ti_type_list = []
    match_list = []
    ref_bug_list = [] # referenced ti type

    iter_count = 0
    for index, row in df.iterrows():
        job_name = row['JOB_NAME']
        job_num = str(row['JOB_NUM'])
        batch_name = row['BATCH_NAME']
        domain_name = row['DOMAIN_NAME']
        atc_name = row['ATC_NAME']

        job_index = job_name+ '_' + job_num + '_' + batch_name+ '_'  + domain_name
        ti_name = job_index + '_' + atc_name
        print('*'*5 + ti_name + '*'*5)
        iter_count +=1
        print(f'{iter_count} of {total_num}')

        ti_name_list.append(ti_name)
        actual_bug_id_list.append(row['BUG_ID'])
        actual_bug_type = _return_ti_type_by_fix_version(row['FIX_VERSION'])
        actual_ti_type_list.append(actual_bug_type)

        atc_file_name = row['ROBOT_LOG']
        sims_list = _sims_compare(ai_dictionary,ai_lsi,ai_index,[atc_file_name])
        if sims_list:
            rec_ti_type, ref_ti_list = _reference_method_3(sims_list, history_ti_dict,job_name, domain_name, atc_name)
            if rec_ti_type:
                ana_num +=1
                ti_type_list.append(rec_ti_type)
                ref_bug_list.append(ref_ti_list)
                if actual_bug_type == rec_ti_type:
                    match_num += 1
                    match_list.append('1')
                    print(f'actual ti type: {actual_bug_type}, recomended ti type: {rec_ti_type}, MATCH')
                else:
                    match_list.append('0')
                    print(f'actual ti type: {actual_bug_type}, recomended ti type: {rec_ti_type}, NOT MATCH')
            else:
                ti_type_list.append('None')
                ref_bug_list.append(ref_ti_list)
                match_list.append('None')
                print(f'cannot recommend ti type for {ti_name} due to too low similarities')
        else:
            ti_type_list.append('None')
            ref_bug_list.append('None')
            match_list.append('None')
            print(f'cannot recommend ti type for {ti_name} due to no query document')

    print('total TI number: %d, analyzed %d TIs, matched %d TIs' % (total_num, int(ana_num), int(match_num)))
    print('reference accuracy is %f' % (match_num/ana_num,))

    #export result to Excel
    d = {
    'TI_NAME': ti_name_list,
    'REC_TI_TYPE': ti_type_list,
    'ACT_BUG_ID': actual_bug_id_list,
    'ACT_TI_TYPE': actual_ti_type_list,
    'MATCH': match_list,
    'RFE_TI': ref_bug_list
    }

    new_df = pd.DataFrame(data=d)
    print('new df shape is %s' % str(new_df.shape))

    #use xlsxwriter to write xlsx
    file_name = f'validate_ti_build_result_val.xlsx'
    sheet_name = 'Result'
    writer = pd.ExcelWriter(file_name, engine='xlsxwriter')
    new_df.to_excel(writer,index=False,sheet_name=sheet_name)

    workbook  = writer.book
    worksheet = writer.sheets[sheet_name]
    format1 = workbook.add_format({'text_wrap': True,'border': 1,'align': 'left'})
    worksheet.set_column('A:A', 50, format1)
    worksheet.set_column('B:E', 13, format1)
    worksheet.set_column('F:F', 85, format1)
    writer.save()
    print('excel for ti validation completed...')

    shutil.move(file_name,os.path.join(LOG_DIR,file_name))

def _retrieve_new_ti_by_job(job_name,job_num,batch_name,domain_name,build_id):
    '''
    retrieve all ti entries by job
    called by recommend_ti_by_job()
    '''
    new_ti_list = []
    if all([job_name,job_num,build_id]):
        pass
    else:
        print('input args error, please give correct job_name, job_num and build_id')
        return new_ti_list

    print('start to retrieve new ti by job...')
    # Connect to the database
    connection = pymysql.connect(host='135.249.27.193',
        user='smtlab',
        password='smtlab123',
        database='robot2')

    with connection:
        with connection.cursor() as cursor:
            sql = "SELECT ATCName,frClassify FROM testATCResults \
                  WHERE testResult != 'PASS' and jobName = '%s' and jobNum = %s and batchName = '%s' and DomainName = '%s' \
                  and buildID = %s " %(job_name,job_num,batch_name,domain_name,build_id)
            try:
                cursor.execute(sql)
                new_ti_list = cursor.fetchall()
            except Exception as inst:
                print('Error, fail to fetch data from DB due to %s' % inst)
                return None

    print(len(new_ti_list))
    return new_ti_list

def recommend_ti_by_job(job_name,job_num,batch_name,domain_name,build_id,ml_excel):
    '''
    auto ti by job
    '''
    #load ai model
    print('Load AI Analysis Model')
    ai_dictionary=corpora.Dictionary.load_from_text(os.path.join(COMP_DIR,'auto_ti.dict'))
    ai_lsi=models.LsiModel.load(os.path.join(COMP_DIR,'auto_ti_lis_mode.mo'))
    ai_index=similarities.MatrixSimilarity.load(os.path.join(COMP_DIR,'auto_ti_lsi_index.ind'))

    atc_result_list = _retrieve_new_ti_by_job(job_name,job_num,batch_name,domain_name,build_id)
    robot_log_url = _get_robot_url_of_ti(job_name,job_num,batch_name,domain_name,build_id=build_id)
    xml_file = _download_robot_xml_file(robot_log_url,job_name,job_num,batch_name,domain_name)

    #read ml excel to refer bug type
    df = pd.read_excel(os.path.join(LOG_DIR,ml_excel),engine='openpyxl')
    df.fillna('',inplace=True)
    history_ti_dict = df.T.to_dict('list')
    job_index = job_name+ '_' + job_num + '_' + batch_name+ '_'  + domain_name
    print(f'Start to auto analyze new TI for job: {job_index}')

    total_num = len(atc_result_list)
    iter_count = 0
    rec_ti_list = []
    if robot_log_url and os.path.exists(os.path.join(LOG_DIR,xml_file)):
        for each in atc_result_list:
            file_list_to_reference = []
            job_index = job_name+ '_' + job_num + '_' + batch_name+ '_'  + domain_name
            atc_name = each[0]
            ti_name = job_index + '_' + atc_name
            print('*'*5 +job_index + ':' + ' '*4 + atc_name + '*'*5)
            iter_count +=1
            print(f'{iter_count} of {total_num}')

            if atc_name.startswith('setup:'):
                atc_name = atc_name.lstrip('setup:')
                ti_name = ti_name.replace(':','_')
                tmp_steps = _retrieve_failed_step_from_xml(xml_file,kw_name=atc_name)
                if tmp_steps:
                    atc_file_name = ti_name +'_ROBOT_MESSAGES.txt'
                    with open(os.path.join(LOG_DIR,atc_file_name),'w',encoding='UTF-8') as fp:
                        fp.writelines(tmp_steps)
                    file_list_to_reference.append(atc_file_name)
            elif atc_name.startswith('teardown:'):
                atc_name = atc_name.lstrip('teardown:')
                ti_name = ti_name.replace(':','_')
                tmp_steps = _retrieve_failed_step_from_xml(xml_file,kw_name=atc_name,kw_type='teardown')
                if tmp_steps:
                    atc_file_name = ti_name +'_ROBOT_MESSAGES.txt'
                    with open(os.path.join(LOG_DIR,atc_file_name),'w',encoding='UTF-8') as fp:
                        fp.writelines(tmp_steps)
                    file_list_to_reference.append(atc_file_name)
            else:
                tmp_steps = _retrieve_failed_step_from_xml(xml_file, atc_name)
                #use atc xml instead of output.xml if fail to parse steps
                if not tmp_steps:
                    atc_xml_file = _download_atc_xml_file(robot_log_url,job_name, job_num, batch_name, domain_name,atc_name)
                    tmp_steps = _retrieve_failed_step_from_xml(atc_xml_file, atc_name) 
                #if still return empty, it is probably a NOT RUN case due to parent setup failure, so retrieve failed setup steps
                # if not tmp_steps:
                #     tmp_steps = _retrieve_failed_parent_step_from_xml(xml_file, atc_name) 
                if tmp_steps:
                    atc_file_name = ti_name +'_ROBOT_MESSAGES.txt'
                    with open(os.path.join(LOG_DIR,atc_file_name),'w',encoding='UTF-8') as fp:
                        fp.writelines(tmp_steps)
                    file_list_to_reference.append(atc_file_name)

            sims_list = _sims_compare(ai_dictionary,ai_lsi,ai_index,file_list_to_reference)
            if sims_list:
                rec_ti_type, ref_ti_list = _reference_method_3(sims_list, history_ti_dict,job_name, domain_name, atc_name)
                if rec_ti_type:
                    ref_bug_id = ref_ti_list[0][2]
                    ref_bug_status = ref_ti_list[0][4]
                    print(f'TI name: {atc_name}, Rec TI type: {rec_ti_type}, Ref bug: {ref_bug_id}')
                    t = (atc_name, rec_ti_type, ref_bug_id, ref_bug_status, ref_ti_list[0], ref_ti_list[1], ref_ti_list[2])
                else:
                    print(f'TI name: {atc_name}, Rec TI type: None, Ref bug: None')
                    t = (atc_name, 'None', 'None','None', ref_ti_list[0], ref_ti_list[1], ref_ti_list[2])
            else:
                t = (atc_name, 'None', 'None','None','None','None','None')

            rec_ti_list.append(t)

    df = pd.DataFrame(rec_ti_list,columns=['ATC_NAME','REC_TI_TYPE','REF_BUG_ID','REF_BUG_STATUS','REF_TI_1','REF_TI_2','REF_TI_3'])
    #use xlsxwriter to write xlsx
    file_name = 'auto_ti_{}_{}_{}_{}.xlsx'.format(job_name,job_num,batch_name,domain_name)
    sheet_name = 'TI List'
    writer = pd.ExcelWriter(file_name, engine='xlsxwriter')
    df.to_excel(writer,index=False,sheet_name=sheet_name)

    workbook  = writer.book
    worksheet = writer.sheets[sheet_name]
    format1 = workbook.add_format({'text_wrap': True,'border': 1,'align': 'left'})
    worksheet.set_column('A:A', 35, format1)
    worksheet.set_column('B:D', 15, format1)
    worksheet.set_column('E:G', 80, format1)

    writer.save()
    print('excel for ml completed...')

    shutil.move(file_name,os.path.join(LOG_DIR,file_name))

def load_ml_model():
    print('Load AI Analysis Model')
    ai_dictionary=corpora.Dictionary.load_from_text(os.path.join(COMP_DIR,'auto_ti.dict'))
    ai_lsi=models.LsiModel.load(os.path.join(COMP_DIR,'auto_ti_lis_mode.mo'))
    ai_index=similarities.MatrixSimilarity.load(os.path.join(COMP_DIR,'auto_ti_lsi_index.ind'))
    print('Load AI Analysis Model complete')
    return ai_dictionary, ai_lsi, ai_index

def recommend_ti_by_case(ti_dict, ml_excel, ai_dictionary, ai_lsi, ai_index):
    '''
    for SLS usage
    '''
    job_name = ti_dict['jobName']
    job_num = str(ti_dict['jobNum'])
    batch_name = ti_dict['batchName']
    domain_name = ti_dict['domainName']
    atc_name = ti_dict['ATCName']
    error_msg = ti_dict['errorInfo']
    build_id = str(ti_dict['buildID'])
    res = {
        'ATC_NAME': atc_name,
        'REF_TI_1': 'None',
        'REF_TI_2': 'None',
        'REF_TI_3': 'None',
        'REC_TI_TYPE': 'None',
        'REF_BUG_ID': 'None',
        'REF_BUG_STATUS': 'None'
    }

    #read ml excel to refer bug type
    df = pd.read_excel(os.path.join(LOG_DIR,ml_excel),engine='openpyxl')
    df.fillna('',inplace=True)
    history_ti_dict = df.T.to_dict('list')
    print(f'Start to auto analyze new TI for atc: {atc_name}')

    # if atc_name.startswith('setup:'):
        # robot_log_url = _get_robot_url_of_ti(job_name,job_num,batch_name,domain_name,build_id=build_id)
        # xml_file = _download_robot_xml_file(robot_log_url,job_name,job_num,batch_name,domain_name)
        # kw_name = atc_name.lstrip('setup:')
        # error_msg = _retrieve_failed_step_from_xml(xml_file,kw_name=kw_name)
    # elif atc_name.startswith('teardown:'):
        # robot_log_url = _get_robot_url_of_ti(job_name,job_num,batch_name,domain_name,build_id=build_id)
        # xml_file = _download_robot_xml_file(robot_log_url,job_name,job_num,batch_name,domain_name)
        # kw_name = atc_name.lstrip('teardown:')
        # error_msg = _retrieve_failed_step_from_xml(xml_file,kw_name=kw_name,kw_type='teardown')

    if error_msg:
        sims_list = _sims_compare(ai_dictionary,ai_lsi,ai_index,error_msg,qtype='Text')
        if sims_list:
            rec_ti_type, ref_ti_list = _reference_method_3(sims_list, history_ti_dict,job_name, domain_name, atc_name)
            res.update({'REF_TI_1': ref_ti_list[0],'REF_TI_2': ref_ti_list[1],'REF_TI_3': ref_ti_list[2]})
            if rec_ti_type:
                ref_bug_id = ref_ti_list[0][2]
                ref_bug_status = ref_ti_list[0][4]
                res.update({'REC_TI_TYPE': rec_ti_type,'REF_BUG_ID': ref_bug_id,'REF_BUG_STATUS': ref_bug_status})

    return res

def _raise_new_bug_in_jira(ref_bug_id, cs_id, build_id):
    '''
    decide whether need to raise a new bug in Jira
    return True or False
    '''
    ref_bug_info = _retrieve_current_bug_info_from_jira(ref_bug_id)
    ref_fix_version = ref_bug_info.get('fix_version')
    ref_bug_status = ref_bug_info.get('bug_status')

    ref_ti_type = _return_ti_type_by_fix_version(ref_fix_version)

    if ref_ti_type == 'ATC':
        pass
    elif ref_ti_type == 'SW':
        pass




if __name__ == '__main__':
    '''
    python3 test.py -t job -i 'LSFX_NFXSD_FANTG_FGLTD_GPON_EONUAV_WEEKLY_01,121,SLS_BATCH_1,EQMT' -u jieminbz -p Jim#2346
    python3 test.py -t build -i 2206.229 -u jieminbz -p Jim#2346
    '''
    start_time = time.time()

    build_id_list = ['2206.260', '2206.256', '2206.254','2206.252', '2206.250','2206.248','2206.246', '2206.244','2206.241',
        '2206.235','2206.233','2206.231','2206.229','2206.227','2206.225','2206.223','2206.221','2206.217','2206.215', '2206.213',
        '2203.106','2203.102','2203.101','2203.098','2203.096','2203.094','2203.092','2203.090','2203.088','2203.086']

    # tmp_excel = retrieve_history_ti_by_build_list(build_id_list)
    # select_ti_for_ml(tmp_excel)
    # tmp_excel = generate_input_excel_for_ml(tmp_excel)
    # build_ml_model(tmp_excel)

    # validate_ti_reference_by_job('LSFX_NFXSD_FANTG_FGLTD_GPON_EONUAV_WEEKLY_01','128','SLS_BATCH_1','EQMT','2206.250','ti_list_for_ml_20220517_baseline.xlsx')
    # domain_list = ['EQMT','MGMT','TRANSPORT','SUBMGMT', 'MCAST', 'QOS', 'L2FWD', 'REDUN']
    # for each_domain in domain_list:
    #     validate_ti_reference_by_build('2206.241','ti_list_for_ml_20220530_cut.xlsx',val_domain=each_domain)

    # recommend_ti_by_job('LSFX_NFXSD_FANTG_FGLTB_GPON_EONUAV_WEEKLY_01','153','SLS_BATCH_1','EQMT','2203.107','ti_list_for_ml_20220614_training.xlsx')

    #below script is to test SLS usage
    # ai_dictionary, ai_lsi, ai_index = load_ml_model()

    # job_name = 'LSMF_LMFSA_LANTA_LWLTC_GPON_EONU_WEEKLY_02'
    # job_num = '106'
    # batch_name = 'SLS_BATCH_1'
    # domain_name = 'MGMT'
    # build_id = '2206.267'
    # new_ti_list = []

    # connection = pymysql.connect(host='135.249.27.193',
    #     user='smtlab',
    #     password='smtlab123',
    #     database='robot2')
    
    # with connection:
    #     with connection.cursor() as cursor:
    #         sql = "SELECT jobName, jobNum, batchName,domainName,buildID,ATCName,errorInfo FROM testATCResults \
    #               WHERE testResult != 'PASS' and jobName = '%s' and jobNum = %s and batchName = '%s' and DomainName = '%s' \
    #               and buildID = %s " %(job_name,job_num,batch_name,domain_name,build_id)
    #         try:
    #             cursor.execute(sql)
    #             new_ti_list = cursor.fetchall()
    #         except Exception as inst:
    #             print('Error, fail to fetch data from DB due to %s' % inst)

    # # print(new_ti_list)
    # for each in new_ti_list:
    #     tmp_dict =  dict(zip(['jobName', 'jobNum', 'batchName','domainName','buildID','ATCName','errorInfo'],each))
    #     # print(tmp_dict)
    #     res = recommend_ti_by_case(tmp_dict,'ti_list_for_ml_20220614_training.xlsx',ai_dictionary, ai_lsi, ai_index)
    #     print(res)

    print("cost %d seconds" % int(time.time() - start_time))
