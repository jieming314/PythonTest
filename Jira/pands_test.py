import pandas as pd
from pandas.core.indexing import is_nested_tuple

# d = {'id': [1,2,3], 'status': ['closed','open','verified']}

# df = pd.DataFrame(data=d)

# df.to_excel('output.xlsx')

# records_trc = pd.read_csv('BBN_Organization.csv',sep='\t',error_bad_lines=False)

# print(records_trc)

# records_list = records_trc.to_dict(orient='records')

# for record in records_list:
#     if record['MEMBERCSL'] == 'jieminbz':
#         member_csl = record['MEMBERCSL']
#         member_area = record['AREATEAM']
#         print(f'{member_csl}\'s area is {member_area}')
#         break

excel_name = 'auto_ti.xlsx'
sheet_name = 'bug list'
#df = pd.read_excel(excel_name,sheet_name=sheet_name,engine='openpyxl',index_col='ATC_Name',keep_default_na=False)
df = pd.read_excel(excel_name,sheet_name=sheet_name,engine='openpyxl',index_col='ATC_Name',na_filter=False)
# print(df)

#df.set_index('xxx', inplace=True)  #   使用某一列作为index，并直接改变df


print(df['Job_Name'])   #输出列, 带上列名
'''
ATC_Name
QOS_ONU_CFG_NCY_03     LSFX_NFXSD_FANTF_FWLTB_ONU_IOP_EONU_STAND_01
QOS_ONU_CFG_NCY_04     LSFX_NFXSD_FANTF_FWLTB_ONU_IOP_EONU_STAND_01
QOS_ONU_FUNC_NCY_01    LSFX_NFXSD_FANTF_FWLTB_ONU_IOP_EONU_STAND_01
test1                                                           NaN
test2                                                           NaN
'''

print(df.head())    #输出前几行

print(df.index)     #输出所有的index，得到一个列表
'''
Index(['QOS_ONU_CFG_NCY_03', 'QOS_ONU_CFG_NCY_04', 'QOS_ONU_FUNC_NCY_01',
       'test1', 'test2'],
      dtype='object', name='ATC_Name')
'''

if 'test1' in df.index:
    print("有")
else:
    print("没有")

print(df.loc['QOS_ONU_CFG_NCY_04'])     #输出行，使用loc，带上index
'''
Name: Job_Name, dtype: object
Fail_Step               ['12.4.2.1.1', '12.4.3.1.1', '15', '27']
Error_Info     ERROR MSG: Several failures occurred:\n\n1) Pc...
FR_ID                                                  BBN-45705
FR_Type                                                      ATC
Job_Name            LSFX_NFXSD_FANTF_FWLTB_ONU_IOP_EONU_STAND_01
Last_Update                                  2021-12-24 15:50:02
Name: QOS_ONU_CFG_NCY_04, dtype: object
'''

print(df.loc['QOS_ONU_CFG_NCY_04','FR_ID'])     #输出单元格
'''
BBN-45705
'''

#由于在读取excel时，使用了keep_default_na=False，所有的空白单元格的内容会变成空字符串，所以以下判断输出111
# if df.loc['test1','FR_ID'] == '':
#     print(111)
# else:
#     print(222)



print(df.loc['QOS_ONU_CFG_NCY_04',['FR_ID','FR_Type']])  #输出一个series，特定行的特定列
'''
FR_ID      BBN-45705
FR_Type          ATC
Name: QOS_ONU_CFG_NCY_04, dtype: object
'''

# print(df.loc[['QOS_ONU_CFG_NCY_04','test1'],['FR_ID','FR_Type']])  #输出一个df
'''
                       FR_ID FR_Type
ATC_Name
QOS_ONU_CFG_NCY_04  BBN-45705     ATC
test1                     NaN     NaN
'''

# print(df.loc['QOS_ONU_CFG_NCY_04':'test1',['FR_ID','FR_Type']])  #切片查询，输出一个df, 注意结果和上面不同
'''
                         FR_ID FR_Type
ATC_Name
QOS_ONU_CFG_NCY_04   BBN-45705     ATC
QOS_ONU_FUNC_NCY_01  BBN-45705     ATC
test1                      NaN     NaN
'''

# print(df.loc['QOS_ONU_CFG_NCY_04':'test1','FR_ID':'Last_Update'])  #切片查询，行和列都可以是一个序列，输出df
'''
                         FR_ID FR_Type                                      Job_Name          Last_Update
ATC_Name
QOS_ONU_CFG_NCY_04   BBN-45705     ATC  LSFX_NFXSD_FANTF_FWLTB_ONU_IOP_EONU_STAND_01  2021-12-24 15:50:02
QOS_ONU_FUNC_NCY_01  BBN-45705     ATC  LSFX_NFXSD_FANTF_FWLTB_ONU_IOP_EONU_STAND_01  2021-12-24 15:50:02
test1                      NaN     NaN                                           NaN                  NaN
'''

print(df.loc[df['FR_ID'] == 'BBN-45705', :])     #根据条件查询，FR_ID 值为BBN-45705的列
'''
                                                             Fail_Step                                         Error_Info  ...                                      Job_Name          Last_Update    
ATC_Name                                                                                                                   ...
QOS_ONU_CFG_NCY_03   ['12.4.2.1.1', '12.4.3.1.1', '15', '26.4.2.1.1...  ERROR MSG: Several failures occurred:\n\n1) Pc...  ...  LSFX_NFXSD_FANTF_FWLTB_ONU_IOP_EONU_STAND_01  2021-12-24 15:50:02    
QOS_ONU_CFG_NCY_04            ['12.4.2.1.1', '12.4.3.1.1', '15', '27']  ERROR MSG: Several failures occurred:\n\n1) Pc...  ...  LSFX_NFXSD_FANTF_FWLTB_ONU_IOP_EONU_STAND_01  2021-12-24 15:50:02    
QOS_ONU_FUNC_NCY_01  ['12.4.2.1.1', '12.4.3.1.1', '15', '15.1', '15...  ERROR MSG: Several failures occurred:\n\n1) Pc...  ...  LSFX_NFXSD_FANTF_FWLTB_ONU_IOP_EONU_STAND_01  2021-12-24 15:50:02 

[3 rows x 6 columns]
'''

#注：df['FR_ID'] == 'BBN-45705' 的结果为一个布尔值列表
print(df['FR_ID'] == 'BBN-45705')
'''
ATC_Name
QOS_ONU_CFG_NCY_03      True
QOS_ONU_CFG_NCY_04      True
QOS_ONU_FUNC_NCY_01     True
test1                  False
test2                  False
Name: FR_ID, dtype: bool
'''

#以下判断返回111
# if any(df['FR_ID'] == 'BBN-45705'):
#     print('111')
# else:
#     print('222')

#以下
# if all(df['FR_ID'] == 'BBN-45705'):
#     print('333')
# else:
#     print('444')

print(df.loc[(df['Fail_Step'] == 'abc') & (df['Error_Info'] == 'kkk'), :])     #复杂条件查询
'''
         Fail_Step Error_Info FR_ID FR_Type Job_Name Last_Update
ATC_Name
test3          abc        kkk   NaN     NaN      NaN         NaN
'''

#使用函数来查询（也可以使用匿名函数）
#如果查询条件含有index内容的，需要用到此方法
def query_my_data(df):
    return (df.index.str.startswith('test')) & (df['FR_Type'] == 'ATC')

print(df.loc[query_my_data,:])
'''
         Fail_Step Error_Info FR_ID FR_Type Job_Name Last_Update
ATC_Name
test2          abc        def   NaN     ATC      NaN         NaN
test3          abc        kkk   NaN     ATC      NaN         NaN
'''

print(df.loc[lambda df: (df.index.str.startswith('test2')) & (df['FR_Type'] == 'ATC'),:])

list1 = ['ATC_Name','Fail_Step','Error_Info','FR_ID','FR_Type','Job_Name','Last_Update']

d = {
            'ATC_Name': ['test3'],
            'Fail_Step': ['1'],
            'Error_Info': [2],
            'FR_ID': [3],
            'FR_Type': [4],
            'Job_Name': [5],
            'Last_Update': [6]
        }


df2 = pd.DataFrame(data=d)
df2.set_index('ATC_Name',inplace=True)

print(df2)

print(pd.concat([df,df2]))


print('##############################')
print(df.loc[df['FR_Type'] == 'ENV'])

print(df.index.str.match('TRANSPORT_L2FWD_CC_TRAF_TEMPLATE_01'))


print