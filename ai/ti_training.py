from urllib.error import HTTPError
import time,os,re,shutil,wget,zipfile
from multiprocessing import Pool
import pandas as pd
from lxml import etree
from gensim import corpora, models, similarities
from jira import JIRA
import pymysql


#define some global variables
LOG_DIR = 'AI_LOG'    #store case logs, ml execl files
COMP_DIR = 'AI_COMP'    #store ml components
CURRENT_PATH = os.path.abspath(os.path.dirname(__file__))
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
if not os.path.exists(os.path.join(CURRENT_PATH,LOG_DIR)):
    os.mkdir(os.path.join(CURRENT_PATH,LOG_DIR))

if not os.path.exists(os.path.join(CURRENT_PATH,COMP_DIR)):
    os.mkdir(os.path.join(CURRENT_PATH,COMP_DIR))

def retrieve_history_ti_by_build_list(build_id_list,keep_num=None,fetch_num=None):
    '''
    Retrieve history ti per build id in 'build_id_list', export result to an excel file
    Only fetch TI whose testResult = 'FAIL' and frClassify in ('SW','ATC') and job name in MOSWA job list
    Input:
        build_id_list: a build id list like ['2206.260', '2206.256', '2206.254']
        keep_num:  total ti number returned by this method
        fetch_num: number of fetched TI in one SQL query of each build
    Output:
        Excel file name
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

def _get_job_names_from_file(file_name='MOSWA_JOB_NAME.txt'):
    '''
    return the job names in file_name
    return is a list
    '''
    job_list = []
    if os.path.exists(os.path.join(CURRENT_PATH,file_name)):
        with open(os.path.join(CURRENT_PATH,file_name),'r',encoding='UTF-8') as fp:
            job_list = fp.readlines()
        job_list = [each.rstrip('\n') for each in job_list]
    else:
        print(f'cannot find moswa job name list file: {file_name}')
    return job_list

def _export_history_ti_list_to_excel(ti_list):
    '''
    export the ti_list info into Excel
    '''
    bug_info_dict = {} # store bug's fix version, status, affects_version and labels value, key is bug id
    new_ti_list = []

    for ti_entry in ti_list:
        ti_entry = [x for x in ti_entry]
        bug_id = ti_entry[9]
        # ti_entry: id,jobName,jobNum,ATCName,batchName,DomainName,buildID,testCS,testResult,frId,frClassify
        if bug_id and bug_id not in bug_info_dict:
            bug_info_dict[bug_id] = []
            try:
                tmp_bug_dict = _retrieve_current_bug_info_from_jira(bug_id)
                fix_version = tmp_bug_dict.get('fix_version')
                bug_status = tmp_bug_dict.get('bug_status')
                issue_type = tmp_bug_dict.get('issue_type')
                affects_version = tmp_bug_dict.get('affects_version')
                labels = tmp_bug_dict.get('labels')
                labels = ','.join(labels).upper()
            except:
                bug_info_dict[bug_id] = [''] * 4
                ti_entry += [''] * 4
            else:
                if issue_type.lower() in ['bug', 'sub-task']:
                    bug_info_dict[bug_id] = [fix_version, bug_status, affects_version, labels]
                    ti_entry +=  [fix_version, bug_status, affects_version, labels]
                else:
                    bug_info_dict[bug_id] = [''] * 4
                    ti_entry += [''] * 4
        elif bug_id:
            ti_entry += bug_info_dict[bug_id]
        else:
            ti_entry += [''] * 4

        new_ti_list.append(ti_entry)

    df = pd.DataFrame(new_ti_list,
        columns=['TI_ID','JOB_NAME','JOB_NUM','ATC_NAME','BATCH_NAME','DOMAIN_NAME','BUILD_ID','CS_ID','TEST_RESULT',
            'BUG_ID','TI_TYPE','FIX_VERSION','BUG_STATUS','AFFECTS_VERSION','LABELS'])
    df['JOB_NUM'] = df['JOB_NUM'].values.astype(str)
    df['BUG_ID'] = df['BUG_ID'].values.astype(str)

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
    shutil.move(file_name,os.path.join(CURRENT_PATH,LOG_DIR,file_name))
    return file_name

def select_ti_for_ml(input_file,training_num=1000,validation_num=300):
    '''
    select TI from input_file for machine learning model
        1. drop duplicated TI of same bug id, only keep the first one
        2. drop TI if fix_verison = 'LSRATC' while affects_verisoin not
        3. drop TI if fix_version = 'LSRATC' and labels in ['atc_swimpact', 'atc_rcrdrop_impact']
        4. select TI randomly for each ti type
    Input:
        input_file: excel file name generated by retrieve_history_ti_by_build_list()
        trainging_num: number of TI to train model(per TI type)
        validation_num: number of TI to validate model(per TI type)
    Output:
        generate an excel which contains two sheets. 'Training_Set' sheet contains the TI for training model
        'Validation_Set' sheet contains the TI for validating model
    '''
    df = pd.read_excel(os.path.join(CURRENT_PATH,LOG_DIR,input_file),engine='openpyxl',dtype={'JOB_NUM': str, 'BUILD_ID': str})
    print('source entry num from input is %d' %len(df))
    df.dropna(subset=['JOB_NAME','JOB_NUM','ATC_NAME','BUILD_ID','CS_ID','TEST_RESULT','FIX_VERSION','BUG_ID','BUG_STATUS'],inplace=True)
    df.fillna('',inplace=True)
    df.sort_values(by=['TI_ID'],inplace=True)   #asencding sort by 'TI_ID'
    df.drop_duplicates(subset=['JOB_NAME','JOB_NUM','BATCH_NAME','DOMAIN_NAME','BUG_ID'],inplace=True)
    df.drop(df[(df.FIX_VERSION == 'LSRATC') & (df.AFFECTS_VERSION != 'LSRATC')].index,inplace=True)
    df.drop(df[(df.FIX_VERSION == 'LSRATC') & (df.LABELS.isin(['ATC_RCRDROP_IMPACT', 'ATC_SWIMPACT']))].index,inplace=True)
    df.reset_index(drop=True,inplace=True)
    print('entry num after process is %d' %len(df))

    #select ATC and SW TI
    df_atc = df[df['FIX_VERSION'] == 'LSRATC']
    df_sw = df[df['FIX_VERSION'] != 'LSRATC']

    #sample TI
    totol_num = training_num + validation_num
    df_atc = df_atc.sample(totol_num)
    df_sw = df_sw.sample(totol_num)

    #generate training and validation set
    df_atc_t = df_atc[:training_num]
    df_atc_v = df_atc[training_num:]
    df_sw_t = df_sw[:training_num]
    df_sw_v = df_sw[training_num:]

    df_t = df_atc_t.append(df_sw_t,ignore_index=True)   #training set
    df_v = df_atc_v.append(df_sw_v,ignore_index=True)   #validation set

    file_name = 'history_ti_list_{}_selection.xlsx'.format(time.strftime('%Y%m%d'))
    sheet_name = 'TI List'
    writer = pd.ExcelWriter(file_name, engine='xlsxwriter')
    df_t.to_excel(writer,index=False,sheet_name='Training_Set')
    df_v.to_excel(writer,index=False,sheet_name='Validation_Set')

    for sheet_name in ['Training_Set','Validation_Set']:
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
    shutil.move(file_name,os.path.join(CURRENT_PATH,LOG_DIR,file_name))
    return file_name

def generate_input_excel_for_ml(input_file,sheet_name='Training_Set'):
    '''
    generate an excel file to train model or validate model
    Input:
        input_file: excel file name generated by select_ti_for_ml()
        sheet_name: sheet name to read
    Output:
        excel file name
    '''
    df = pd.read_excel(os.path.join(CURRENT_PATH,LOG_DIR,input_file),sheet_name=sheet_name,engine='openpyxl',dtype={'JOB_NUM': str, 'BUILD_ID': str})
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
    _download_robot_xml_file_mp(input_file=input_file,sheet_name=sheet_name)

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
    new_df['JOB_NUM'] = new_df['JOB_NUM'].values.astype(str)
    new_df['BUG_ID'] = new_df['BUG_ID'].values.astype(str)
    print('new df shape is %s' % str(new_df.shape))
    print('generate excel for ml...')

    #use xlsxwriter to write xlsx
    file_name = 'ti_list_for_ml_{}_{}.xlsx'.format(time.strftime('%Y%m%d'),sheet_name.lower())
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

    shutil.move(file_name,os.path.join(CURRENT_PATH,LOG_DIR,file_name))
    return file_name

def _download_robot_xml_file(url,job_name,job_num,batch_name,domain_name):
    '''
    download the output.xml of a job
    be called by _download_robot_xml_file_mp()
    '''
    robot_out_path = url + 'ROBOT'
    target_file = robot_out_path + '/output.xml'
    output_file_name = job_name + '_' + job_num + '_' + batch_name + '_' + domain_name + '_output.xml'

    print(f'target robot output xml is {target_file}')

    if os.path.exists(os.path.join(CURRENT_PATH,LOG_DIR,output_file_name)):
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
                    wget.download(target_file,out=os.path.join(CURRENT_PATH,LOG_DIR,output_file_name))
                    print(f'\ndownload target file {target_file} completed')
                    return output_file_name
                except Exception as inst:
                    print('download target file %s failed, due to %s' % (target_file,inst))
                    return None
        
        print(f'\ndownload target file {tmp_target_file} completed')
        with zipfile.ZipFile(tmp_zip_file) as z:
            for zip_file in z.namelist():
                with z.open(zip_file) as zf, open(os.path.join(CURRENT_PATH,LOG_DIR,output_file_name), 'wb') as f:
                    shutil.copyfileobj(zf, f)
        print(f'unzip target file {tmp_target_file} completed')
        os.remove(tmp_zip_file)

    return output_file_name

def _download_robot_xml_file_mp(input_file=None,sheet_name=None,ti_list=None):
    '''
    use process pool to download robot output.xml concurrently
    '''
    download_task_list  = [] # store download task list
    print('start to download all required robot xml files first...')

    if input_file:
        df = pd.read_excel(os.path.join(CURRENT_PATH,LOG_DIR,input_file),sheet_name=sheet_name,engine='openpyxl',dtype={'JOB_NUM': str, 'BUILD_ID': str})
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
    res = [ti_id, job_name, job_num, batch_name,domain_name, atc_name, bug_id, fix_version, bug_status]

    print('*'*5 +job_index + ':' + ' '*4 + atc_name + '*'*5)
    if robot_log_url and os.path.exists(os.path.join(CURRENT_PATH,LOG_DIR,xml_file)):
        if atc_name.startswith('setup:'):
            atc_name = atc_name.lstrip('setup:')
            ti_name = ti_name.replace(':','_')
            tmp_steps = _retrieve_failed_step_from_xml(xml_file,kw_name=atc_name)
            if tmp_steps:
                atc_file_name = ti_name +'_ROBOT_MESSAGES.txt'
                with open(os.path.join(CURRENT_PATH,LOG_DIR,atc_file_name),'w',encoding='UTF-8') as fp:
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
                with open(os.path.join(CURRENT_PATH,LOG_DIR,atc_file_name),'w',encoding='UTF-8') as fp:
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
                with open(os.path.join(CURRENT_PATH,LOG_DIR,atc_file_name),'w',encoding='UTF-8') as fp:
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
        tree = etree.parse(os.path.join(CURRENT_PATH,LOG_DIR,file_name),parser=parser)
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

def _download_atc_xml_file(url,job_name,job_num,batch_name,domain_name,case_name):
    '''
    download case's xml file
    this operation only happens when fail to parse step from output.xml, use this xml instead
    '''
    parent_path = url + 'ROBOT/robot-data/ATC/'
    output_file_name = job_name + '_' + job_num + '_' + batch_name + '_' + domain_name + '_' + f'{case_name}.xml'
    target_file = parent_path + f'{case_name}.xml'

    print(f'target atc xml file is {target_file}')
    if os.path.exists(os.path.join(CURRENT_PATH,LOG_DIR,output_file_name)):
        print(f'target atc xml {output_file_name} alread exist, skip downloading')
    else:
        try:
            print('start downloading target atc xml ...')
            wget.download(target_file,out=os.path.join(CURRENT_PATH,LOG_DIR,output_file_name))
            print('\ndownloading atc xml completed')
        except Exception as inst:
            print('download atc xml failed, due to %s' % inst)
            return None

    return output_file_name

def build_ml_model(file_name):
    '''
    train model according to input excel
    Input:
        file_name: excel file name generated by generate_input_excel_for_ml()
    Output:
        model related files under AI_COMP folder
    '''
    print('start to build LSI mode')
    excel_file = os.path.join(CURRENT_PATH,LOG_DIR,file_name)
    if not os.path.exists(excel_file):
        print(f'cannot find {file_name}, pls check...')
        return

    print('start to create dictionary and corpus')
    documents_text = Read_File(excel_file)
    no_below_number=2
    no_above_rate=0.8
    dictionary = corpora.Dictionary(documents_text)
    dictionary.filter_extremes(no_below=no_below_number,no_above=no_above_rate,keep_n=600000)
    dictionary.compactify()
    dictionary.save_as_text(os.path.join(CURRENT_PATH,COMP_DIR,'auto_ti.dict'))
    corpus = _create_corpus(dictionary, documents_text)
    corpus = list(corpus)
    corpora.MmCorpus.serialize(os.path.join(CURRENT_PATH,COMP_DIR,'auto_ti_corpus.mm'), corpus)

    print('start to train model')
    tfidf = models.TfidfModel(corpus)
    tfidf.save(os.path.join(CURRENT_PATH,COMP_DIR,'auto_ti_tfidf.ti'))
    corpus_tfidf = tfidf[corpus]

    numtopics=500
    lsi = models.LsiModel(corpus_tfidf, id2word=dictionary, num_topics=numtopics)
    lsi.save(os.path.join(CURRENT_PATH,COMP_DIR,'auto_ti_lis_mode.mo'))
    # lsi.print_topics(numtopics)

    # Build index with LSI index
    index = similarities.MatrixSimilarity(lsi[corpus])
    index.save(os.path.join(CURRENT_PATH,COMP_DIR,'auto_ti_lsi_index.ind'))

    print('LSI mode building complete')

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
            df = pd.read_excel(self.input_file,engine='openpyxl',dtype={'JOB_NUM': str, 'BUILD_ID': str})
            for index, row in df.iterrows():
                t= (row['ROBOT_LOG'],)
                self.file_list.append(t)
        else:
            print(f'{self.input_file} does not exist...')

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
            robot_log_file = os.path.join(CURRENT_PATH,LOG_DIR,each[0])
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

def _retrieve_current_bug_info_from_jira(bug_id):
    '''
    return bug's info like 'fix_version', 'status', etc
    '''
    bug_info_dict = {'bug_id': bug_id}
    jira_inst = JIRA('https://jiradc2.ext.net.nokia.com/', auth=('jieminbz', 'Jim#2346'))

    issue = jira_inst.issue(bug_id)
    fix_version = issue.fields.fixVersions[0].name
    bug_status = issue.fields.status.name
    issue_type = issue.fields.issuetype.name
    affects_version = issue.fields.versions[0].name
    labels = issue.fields.labels    # return is a list
    resolution = issue.fields.resolution

    bug_info_dict.update({'fix_version': fix_version, 'bug_status': bug_status, 'issue_type': issue_type, 'affects_version': affects_version,
        'labels': labels, 'resolution': resolution})

    return bug_info_dict

def validate_ti_reference_in_file(input_file,ref_file):
    '''
    Valiate TI recomendation accuracy using 'Validation_Set' TI
    Input:
        input_file: excel file contains 'Validation_Set' TI
        ref_file: excel file contains 'Training_Set' TI
    Output:
        an excel file contains comparison result of each validation TI
    '''
    print('Load AI Analysis Model')
    ai_dictionary=corpora.Dictionary.load_from_text(os.path.join(CURRENT_PATH,COMP_DIR,'auto_ti.dict'))
    ai_lsi=models.LsiModel.load(os.path.join(CURRENT_PATH,COMP_DIR,'auto_ti_lis_mode.mo'))
    ai_index=similarities.MatrixSimilarity.load(os.path.join(CURRENT_PATH,COMP_DIR,'auto_ti_lsi_index.ind'))

    #read ref_file to generate referenace dict
    df = pd.read_excel(os.path.join(CURRENT_PATH,LOG_DIR,ref_file),engine='openpyxl',dtype={'JOB_NUM': str, 'BUILD_ID': str})
    df.fillna('',inplace=True)
    history_ti_dict = df.to_dict('index')

    #read input_file to get TI entries to validate
    df = pd.read_excel(os.path.join(CURRENT_PATH,LOG_DIR,input_file),engine='openpyxl',dtype={'JOB_NUM': str, 'BUILD_ID': str})
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

    shutil.move(file_name,os.path.join(CURRENT_PATH,LOG_DIR,file_name))

def _return_ti_type_by_fix_version(fix_version):
    if fix_version.lower() == 'lsratc':
        return 'ATC'
    elif fix_version.lower() == 'rlab':
        return 'ENV'
    elif fix_version.lower().startswith('bbdr'):
        return 'SW-ONT'
    else:
        return 'SW'

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

def _reference_method_3(sims_list,history_ti_dict,job_name,domain_name,atc_name):
    '''
    adjust priority if job_name, domain_name and atc_name matches
    '''
    sims_list = sims_list[:3]
    ref_ti_list = []
    rec_ti_type = ''

    for each in sims_list:
        index = each[0]
        score = each[1]
        ref_job_name = history_ti_dict[index].get('JOB_NAME')
        ref_domain_name = history_ti_dict[index].get('DOMAIN_NAME')
        ref_atc_name = history_ti_dict[index].get('ATC_NAME')
        ref_bug_id = history_ti_dict[index].get('BUG_ID')
        ref_bug_info = _retrieve_current_bug_info_from_jira(ref_bug_id)
        ref_fix_version = ref_bug_info.get('fix_version')
        ref_bug_status = ref_bug_info.get('bug_status')
        history_ti_dict[index].update({'FIX_VERSION': ref_fix_version, 'BUG_STATUS': ref_bug_status})
        #adjust socre
        bonus = 0.0
        if atc_name == ref_atc_name:
            bonus += 0.05
        if job_name and job_name == ref_job_name:
            bonus += 0.01
        if domain_name and domain_name == ref_domain_name:
            bonus += 0.02
        score_adj = score * (1 + bonus)
        history_ti_dict[index].update({'SCORE': score, 'ADJ_CORE': score_adj})
        ref_ti_list.append(history_ti_dict[index])
    
    #sort ref_ti_list again by score
    ref_ti_list = sorted(ref_ti_list, key=lambda x: x['ADJ_CORE'], reverse=True)

    #need original socre > 0.8
    if ref_ti_list[0]['SCORE'] > 0.8:
        rec_ti_type = _return_ti_type_by_fix_version(ref_ti_list[0]['FIX_VERSION'])

    return rec_ti_type, ref_ti_list


if __name__ == '__main__':
    '''
    python3 test.py -t job -i 'LSFX_NFXSD_FANTG_FGLTD_GPON_EONUAV_WEEKLY_01,121,SLS_BATCH_1,EQMT' -u jieminbz -p Jim#2346
    python3 test.py -t build -i 2206.229 -u jieminbz -p Jim#2346
    '''
    start_time = time.time()

    build_id_list = ['2206.260', '2206.256', '2206.254','2206.252', '2206.250','2206.248','2206.246', '2206.244','2206.241',
        '2206.235','2206.233','2206.231','2206.229','2206.227','2206.225','2206.223','2206.221','2206.217','2206.215', '2206.213',
        '2203.106','2203.102','2203.101','2203.098','2203.096','2203.094','2203.092','2203.090','2203.088','2203.086']

    tmp_excel = retrieve_history_ti_by_build_list(build_id_list)
    tmp_excel = select_ti_for_ml(tmp_excel)
    excel_train = generate_input_excel_for_ml(tmp_excel)
    excel_validate = generate_input_excel_for_ml(tmp_excel,sheet_name='Validation_Set')
    build_ml_model(excel_train)
    validate_ti_reference_in_file(excel_validate,excel_train)

    print("cost %d seconds" % int(time.time() - start_time))