import os,re
import pandas as pd
from gensim import corpora, models, similarities
from jira import JIRA

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
        'REF_TI_1': 'None',
        'REF_TI_2': 'None',
        'REF_TI_3': 'None',
        'REC_TI_TYPE': 'None',
        'REF_BUG_ID': 'None',
        'REF_BUG_STATUS': 'None'
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

    bug_info_dict.update({'fix_version': fix_version, 'bug_status': bug_status, 'bug_type': bug_type, 'affects_version': affects_version,
        'labels': labels, 'resolution': resolution})

    return bug_info_dict

if __name__ == '__main__':
    pass