from jira import JIRA
import pandas as pd
import os


def get_bug_list_from_jira():
    '''
    login Jira and serach user's bugs
    return a list contains jira issue objects
    '''

    url = 'https://jiradc2.ext.net.nokia.com/'
    jira_inst = JIRA(url, auth=('jieminbz', 'Jim#2345'))
    #bug_list = jira_inst.search_issues('project = BBN AND issuetype = Bug AND assignee in (currentUser()) order by created DESC', maxResults=-1)
    bug_list = jira_inst.search_issues('project = BBN AND issuetype = Bug AND Team = 8928 order by created DESC', maxResults=-1)
    return bug_list

def _get_area_team(user_cls):
    '''
    return user's area team info via csl
    '''

    csv_file = './BBN_Organization.csv'
    area_team = ''

    if os.path.exists(csv_file):
        raw_records = pd.read_csv(csv_file,sep='\t',error_bad_lines=False)
        record_list = raw_records.to_dict(orient='records')
        for record in record_list:
            if record['MEMBERCSL'] == user_cls:
                member_csl = record['MEMBERCSL']
                member_area = record['AREATEAM']
                area_team = member_area
                return area_team
    else:
        return area_team

def create_xlsx_file(bug_list):
    '''
    create a xlsx file contains bug list
    '''

    bug_key_list = []
    bug_summary_list = []
    bug_reporter_list = []  # reporter csl + mail address
    bug_reporter_team_list = []
    bug_status_list = []
    bug_created_list = []
    user_csl_to_team_dict = {}

    for bug in bug_list:
        bug_key_list.append(bug.key)
        bug_summary_list.append(bug.fields.summary)
        reporter_csl = bug.raw['fields']['reporter']['name']
        reporter_mail = bug.raw['fields']['reporter']['emailAddress']
        bug_reporter_list.append(f"{reporter_csl}({reporter_mail})")
        bug_status_list.append(bug.fields.status)
        bug_created_list.append(bug.fields.created)

        if reporter_csl not in user_csl_to_team_dict.keys():
            area_team = _get_area_team(reporter_csl)
            user_csl_to_team_dict.update({reporter_csl:area_team})
            bug_reporter_team_list.append(area_team)
        else:
            bug_reporter_team_list.append(user_csl_to_team_dict[reporter_csl])

    d = {
    'Bug Id': bug_key_list,
    'Summary': bug_summary_list,
    'Status': bug_status_list,
    'Reporter': bug_reporter_list,
    'Area Team': bug_reporter_team_list,
    'Created Data': bug_created_list,
    }

    df = pd.DataFrame(data=d)

    #use xlsxwriter to write xlsx
    sheet_name = 'Bug List'
    writer = pd.ExcelWriter('bug_list.xlsx',engine='xlsxwriter')
    df.to_excel(writer,index=False,sheet_name=sheet_name)

    workbook  = writer.book
    worksheet = writer.sheets[sheet_name]

    format1 = workbook.add_format({'text_wrap': True,'border': 1})

    worksheet.set_column('A:A', 10, format1)
    worksheet.set_column('B:B', 60, format1)
    worksheet.set_column('C:C', 15, format1)
    worksheet.set_column('D:F', 25, format1)

    writer.save()


if __name__ == '__main__':
    
    bug_list = get_bug_list_from_jira()
    create_xlsx_file(bug_list)

    print('over!!!')
