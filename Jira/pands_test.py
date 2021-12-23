import pandas as pd

d = {'id': [1,2,3], 'status': ['closed','open','verified']}

df = pd.DataFrame(data=d)

# df.to_excel('output.xlsx')

records_trc = pd.read_csv('./jira/BBN_Organization.csv',sep='\t',error_bad_lines=False)

# print(records_trc)

records_list = records_trc.to_dict(orient='records')

for record in records_list:
    if record['MEMBERCSL'] == 'jieminbz':
        member_csl = record['MEMBERCSL']
        member_area = record['AREATEAM']
        print(f'{member_csl}\'s area is {member_area}')
        break
