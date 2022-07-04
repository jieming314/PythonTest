import os,re
from weakref import ref
import pandas as pd
from gensim import corpora, models, similarities
from jira import JIRA
import pymysql

LOG_DIR = 'AI_LOG'    #store case logs, ml execl files
COMP_DIR = 'AI_COMP'    #store ml components
CURRENT_PATH = os.path.abspath(os.path.dirname(__file__))
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
# BUG_MAPPING_LIST = []   # [{'TestATCResults_id': '123545' ,'refBugID': 'BBN-00001', 'mappedBugID': 'BBN-00001'}]

def load_ml_model():
    print('Load AI Analysis Model')
    ai_dictionary=corpora.Dictionary.load_from_text(os.path.join(CURRENT_PATH,COMP_DIR,'auto_ti.dict'))
    ai_lsi=models.LsiModel.load(os.path.join(CURRENT_PATH,COMP_DIR,'auto_ti_lis_mode.mo'))
    ai_index=similarities.MatrixSimilarity.load(os.path.join(CURRENT_PATH,COMP_DIR,'auto_ti_lsi_index.ind'))
    print('Load AI Analysis Model complete')
    return ai_dictionary, ai_lsi, ai_index

def recommend_ti_by_case(ti_dict, ml_excel, ai_dictionary, ai_lsi, ai_index):
    '''
    for SLS usage
    '''
    job_name = ti_dict['jobName']
    domain_name = ti_dict['domainName']
    atc_name = ti_dict['ATCName']
    error_msg = ti_dict['errorInfo']
    res = {
        'ATC_NAME': atc_name,
        'REF_TI_1': None,
        'REF_TI_2': None,
        'REF_TI_3': None,
        'REC_TI_TYPE': None,
        'REF_BUG_ID': None,
        'REF_BUG_STATUS': None
    }

    #read ml excel to refer bug type
    df = pd.read_excel(os.path.join(CURRENT_PATH,LOG_DIR,ml_excel),engine='openpyxl')
    df.fillna('',inplace=True)
    history_ti_dict = df.to_dict('index')
    print(f'Start to auto analyze new TI for atc: {atc_name}')

    if error_msg:
        sims_list = _sims_compare(ai_dictionary,ai_lsi,ai_index,error_msg,qtype='Text')
        if sims_list:
            rec_ti_type, ref_ti_list = _reference_method_3(sims_list, history_ti_dict,job_name, domain_name, atc_name)
            res.update({'REF_TI_1': ref_ti_list[0],'REF_TI_2': ref_ti_list[1],'REF_TI_3': ref_ti_list[2]})
            if rec_ti_type:
                ref_bug_id = ref_ti_list[0]['BUG_ID']
                ref_bug_status = ref_ti_list[0]['BUG_STATUS']
                res.update({'REC_TI_TYPE': rec_ti_type,'REF_BUG_ID': ref_bug_id,'REF_BUG_STATUS': ref_bug_status})

    return res

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
        ref_fix_build = ref_bug_info.get('fix_build')
        history_ti_dict[index].update({'FIX_VERSION': ref_fix_version, 'BUG_STATUS': ref_bug_status,'FIX_BUILD':ref_fix_build})
        #adjust socre
        bonus = 0.0
        if atc_name == ref_atc_name:
            bonus += 0.05
        if job_name and job_name == ref_job_name:
            bonus += 0.01
        if domain_name and domain_name == ref_domain_name:
            bonus += 0.02
        score_adj = score * (1 + bonus)
        history_ti_dict[index].update({'SCORE': score, 'ADJ_SCORE': score_adj})
        ref_ti_list.append(history_ti_dict[index])
    
    #sort ref_ti_list again by score
    ref_ti_list = sorted(ref_ti_list, key=lambda x: x['ADJ_SCORE'], reverse=True)

    #need original socre > 0.8
    if ref_ti_list[0]['SCORE'] > 0.8:
        rec_ti_type = _return_ti_type_by_fix_version(ref_ti_list[0]['FIX_VERSION'])

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
    fix_build = issue.fields.customfield_37027

    bug_info_dict.update({'fix_version': fix_version, 'bug_status': bug_status, 'bug_type': bug_type, 'affects_version': affects_version,
        'labels': labels, 'resolution': resolution,'fix_build':fix_build})

    return bug_info_dict

def map_bug_to_ti(ref_bug_dict, cs_id, build_id):
    '''
    decide the bug id to map according to input
    return a bug id
    '''
    ref_fix_version = ref_bug_dict.get('FIX_VERSION')
    ref_bug_status = ref_bug_dict.get('BUG_STATUS')
    ref_fix_build = ref_bug_dict.get('FIX_BUILD')
    ref_bug_id = ref_bug_dict.get('BUG_ID')

    ref_ti_type = _return_ti_type_by_fix_version(ref_fix_version)

    if ref_bug_status.lower() in ['resolved','closed']:
        if ref_ti_type == 'ATC':
            cs_id = cs_id.lower().strip('cs')
            ref_fix_build = ref_fix_build.lower().strip('cs').split('.')[0] #CS2379.01
            if int(cs_id) < int(ref_fix_build):
                print(f'Not raise a new bug, bug id to map: {ref_bug_id}')
                return ref_bug_id
            else:
                new_bug = _raise_bug_in_jira()
                print(f'Need to raise a new bug, bug id to map: {new_bug}')
                return new_bug
        elif ref_ti_type == 'SW':
            release_id, sub_id = build_id.split('.')
            ref_release_id, ref_sub_id = ref_fix_build.split('.')
            if release_id == ref_release_id and int(sub_id) < int(ref_sub_id):
                print(f'Not raise a new bug, bug id to map: {ref_bug_id}')
                return ref_bug_id
            else:
                new_bug = _raise_bug_in_jira()
                print(f'Need to raise a new bug, bug id to map: {new_bug}')
                return new_bug
    elif ref_bug_status.lower() == 'obsolete':
        new_bug = _raise_bug_in_jira()
        print(f'Need to raise a new bug, bug id to map: {new_bug}')
        return new_bug
    else:
        #"open", "in progress", "implemented", etc.
        if ref_ti_type == 'SW':
            release_id, sub_id = build_id.split('.')
            ref_release_id, ref_sub_id = ref_fix_build.split('.')
            if release_id == ref_release_id:
                print(f'Not raise a new bug, bug id to map: {ref_bug_id}')
                return ref_bug_id
            else:
                new_bug = _raise_bug_in_jira()
                print(f'Need to raise a new bug, bug id to map: {new_bug}')
                return new_bug
        else:
            print(f'Not raise a new bug, bug id to map: {ref_bug_id}')
            return ref_bug_id

def _convert_bug_mapping_list_to_df(bug_mapping_list):
    df = pd.DataFrame(bug_mapping_list)
    df.drop_duplicates(subset=['refBugID'],inplace=True)
    df.reset_index(drop=True,inplace=True)
    return df

def _get_bug_mapping(df,ref_bug_id):
    '''
    check if there is a bug mapped to reference bug id in mapping dict
    return the mapped new bug id if exist
    '''
    mapped_bug_id = None
    try:
        mapped_bug_id = df.loc[df['refBugID'] == ref_bug_id, 'mappedBugID'].iloc[0]
        print(f'Found an existing bug id in DF to map: {mapped_bug_id}')
    except:
        pass
    return mapped_bug_id

def _update_bug_mapping_dataframe(df, id, ref_bug_id, mapped_bug_id):
    # if not df.empty:
    #     x = df['refBugID'] == ref_bug_id
    #     if x.any():
    #         df.loc[df['refBugID'] == ref_bug_id,'mappedBugID'] = mapped_bug_id
    #     else:
    #         tmp_df = pd.DataFrame([[id,ref_bug_id,mapped_bug_id]],columns=['TestATCResults_id','refBugID','mappedBugID'])
    #         df = df.append(tmp_df, ignore_index=True)
    # else:
    #     tmp_df = pd.DataFrame([[id,ref_bug_id,mapped_bug_id]],columns=['TestATCResults_id','refBugID','mappedBugID'])
    #     df = df.append(tmp_df, ignore_index=True)
    tmp_df = pd.DataFrame([[id,ref_bug_id,mapped_bug_id]],columns=['TestATCResults_id','refBugID','mappedBugID'])
    df = df.append(tmp_df, ignore_index=True)
    return df

def _raise_bug_in_jira():
    '''
    raise a bug in jira, return bug id
    '''
    return 'BBN-XXXXXX'


if __name__ == '__main__':

    #below script is to test SLS usage
    ai_dictionary, ai_lsi, ai_index = load_ml_model()

    job_name = 'LSMF_LMFSA_LANTA_LWLTC_GPON_EONU_WEEKLY_02'
    job_num = '106'
    batch_name = 'SLS_BATCH_1'
    domain_name = 'MGMT'
    build_id = '2206.267'
    new_ti_list = []

    connection = pymysql.connect(host='135.249.27.193',
        user='smtlab',
        password='smtlab123',
        database='robot2')
    
    with connection:
        with connection.cursor() as cursor:
            sql = "SELECT id, jobName, jobNum, batchName,domainName,buildID,ATCName,errorInfo,testCS FROM testATCResults \
                  WHERE testResult != 'PASS' and jobName = '%s' and jobNum = %s and batchName = '%s' and DomainName = '%s' \
                  and buildID = %s " %(job_name,job_num,batch_name,domain_name,build_id)
            try:
                cursor.execute(sql)
                new_ti_list = cursor.fetchall()
            except Exception as inst:
                print('Error, fail to fetch data from DB due to %s' % inst)

    # BUG_MAPPING_LIST = [{'TestATCResults_id': '123545' ,'refBugID': 'BBN-00001', 'mappedBugID': 'BBN-00001'},
    #                 {'TestATCResults_id': '123546' ,'refBugID': 'BBN-00002', 'mappedBugID': 'BBN-00003'},
    #                 {'TestATCResults_id': '123547' ,'refBugID': 'BBN-00002', 'mappedBugID': 'BBN-00003'},
    #                 ]
    BUG_MAPPING_LIST = []
    df_ori = _convert_bug_mapping_list_to_df(BUG_MAPPING_LIST)
    df_res = pd.DataFrame()

    # print(new_ti_list)
    for each in new_ti_list:
        tmp_dict =  dict(zip(['id', 'jobName', 'jobNum', 'batchName','domainName','buildID','ATCName','errorInfo','testCS'],each))
        # print(tmp_dict)
        res = recommend_ti_by_case(tmp_dict,'ti_list_for_ml_20220614_training.xlsx',ai_dictionary, ai_lsi, ai_index)
        print(res['REF_TI_1'])

        if res['REF_BUG_ID']:
            bug_to_map = _get_bug_mapping(df_ori, res['REF_BUG_ID'])
            if not bug_to_map:
                bug_to_map = map_bug_to_ti(res['REF_TI_1'], tmp_dict['testCS'], tmp_dict['buildID'])
                df_ori = _update_bug_mapping_dataframe(df_ori, tmp_dict['id'] ,res['REF_BUG_ID'], bug_to_map)
            df_res = _update_bug_mapping_dataframe(df_res, tmp_dict['id'] ,res['REF_BUG_ID'], bug_to_map)

    print(df_ori)
    print(df_res)
