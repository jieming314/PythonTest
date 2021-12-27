import pandas as pd
'''
need to pip install openpyxl
'''

df = pd.read_excel('./pd_test.xlsx',engine='openpyxl')
print(df)

df.set_index('ATC_Name',inplace=True)
print(df)

dict1 = {'FR_ID': ['111'], 'FR_Type': ['ATC'], 'FR_Des': ['plus']}

df2 = pd.DataFrame.from_dict(dict1)
print(df2)

df4 = pd.DataFrame(dict1)
print(df4)


df3 = pd.DataFrame([['test1','222','ENV','gtwo']],columns=['ATC_Name','FR_ID','FR_Type','FR_Des'])
df3.set_index('ATC_Name',inplace=True)
print(df3)

df=df.append(df3)
print(df)

print(df['FR_ID']) #返回某一列，series
print(df[:]) #行切片，dataframe
print(df.loc[['test1','test2'],'FR_ID']) 
print(df.loc[['test1','test2'],['FR_ID','FR_Type']])
print(df.loc['test1',['FR_ID','FR_Type']]) 
print(df.loc['test1','FR_ID']) 

print(df.iloc[0:1])  #切片操作和python类似，从0开始，不包括冒号右边

print(df[df['FR_Type'] == 'ENV']) #依据某一列的条件

print(df[df['FR_Type'].isin(['ENV'])]) # 根据列筛选，使用isin

df.at['test2','FR_Type'] = 'SW' #改值

df.iat[0,1] = 'ATC' #依据位置改值

df.loc[:,'FR_Type'] = 'ATC' #所有行的某列

df.dropna(how='any') #drop掉有空值的行

df.fillna(value='') #把所有的空值替换成''




