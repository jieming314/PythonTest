from jira import JIRA
import pandas as pd


jira_inst = JIRA('https://jiradc2.ext.net.nokia.com/', auth=('jieminbz', 'Jim#2345'))


# projects = jira_inst.projects()

# with open('./jira_projects.txt','w',encoding='utf-8') as fp:
#     fp.write(str(projects))

bbn_project = jira_inst.project('BBN')

# print(bbn_project.key,bbn_project.name,bbn_project.lead)


# issue1 = jira_inst.issue('BBN-45705')

# print(type(issue1))

# print(issue1.key, '\n' ,issue1.fields.summary, '\n' , issue1.fields.status, issue1.fields.reporter)

# print(issue1.raw)

search_result = jira_inst.search_issues('project = BBN AND issuetype = Bug AND assignee in (currentUser()) order by created DESC', maxResults=-1)

# print(search_result)

print(len(search_result))

bug_key_list = []
bug_summary_list = []
bug_reporter_list = []  # reporter csl + mail address
bug_status_list = []
bug_created_list = []
bug_updated_list = []

for each in search_result:
    bug_key_list.append(each.key)
    bug_summary_list.append(each.fields.summary)
    bug_reporter_list.append(f"{each.raw['fields']['reporter']['name']}({each.raw['fields']['reporter']['emailAddress']})")
    bug_status_list.append(each.fields.status)
    bug_created_list.append(each.fields.created)
    bug_updated_list.append(each.fields.updated)


d = {
    'Bug Id': bug_key_list,
    'Summary': bug_summary_list,
    'Status': bug_status_list,
    'Reporter': bug_reporter_list,
    'Created Data': bug_created_list,
    }

df = pd.DataFrame(data=d)

#use xlsxwriter
'''
xlsxwriter guide
https://xlsxwriter.readthedocs.io/contents.html
'''

sheet_name = 'Bug List'
writer = pd.ExcelWriter('bug_list.xlsx',engine='xlsxwriter')
df.to_excel(writer,index=False,sheet_name=sheet_name)

workbook  = writer.book
worksheet = writer.sheets[sheet_name]

format1 = workbook.add_format({'text_wrap': True,'border': 1})

worksheet.set_column('A:A', 10, format1)
worksheet.set_column('B:B', 60, format1)
worksheet.set_column('C:C', 15, format1)
worksheet.set_column('D:E', 25, format1)

writer.save()



