import pandas as pd
'''
need to pip install openpyxl,xlsxwriter
https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.html
'''

'''
创建Series
'''


'''
创建DataFrame
'''

#直接创建
df = pd.DataFrame([['test1','111','ENV','gone'],['test2','222','ATC','gtwo']],columns=['ATC_Name','FR_ID','FR_Type','FR_Des'])
'''
>>> df
  ATC_Name FR_ID FR_Type FR_Des
0    test1   111     ENV   gone
1    test2   222     ATC   gtwo
'''

#从字典创建
dict1 = {
    'FR_ID': ['111'],
    'FR_Type': ['ATC'],
    'FR_Des': ['plus']
    }
df2 = pd.DataFrame.from_dict(dict1)
'''
>>> df2
  FR_ID FR_Type FR_Des
0   111     ATC   plus
'''
#也可以不适用from_dict(), df2 = pd.DataFrame.from_dict(dict1), 效果一样


#从excel读取
# df = pd.read_excel('pd_test.xlsx',engine='openpyxl')


#从csv读取
#df = pd.read_csv('csv_file.csv',sep='\t',error_bad_lines=False)

'''
设置index
'''
df.set_index('ATC_Name',inplace=True)   #把column 'ATC_Name' 设置为index


'''
DataFrame的查询操作
'''
df.head()   #输出df的前几行
df.index    #输出所有的index，一个列表
print(df['FR_ID']) #返回某一列，series
print(df[:]) #行切片，dataframe
print(df.loc[[0,1],'FR_ID'])  # 2行1列
print(df.loc[[0,1],['FR_ID','FR_Type']])    #2行2列
print(df.loc[0,['FR_ID','FR_Type']])  #1行2列，是一个series
print(df.loc[0,'FR_ID']) #一个具体值
print(df.iloc[0:1])  #行切片，操作和python类似，从0开始，不包括冒号右边；这里返回1行
print(df[df['FR_Type'] == 'ENV']) #依据某一列的条件(布尔查询)
print(df[df['FR_Type'].isin(['ENV'])]) # 根据列筛选，使用isin
df.loc[df['FR_ID'] == '111',:]    #返回'FR_ID' 等于111 的所有行
# 注：df['FR_ID'] == '111' 返回一个布尔序列
'''
>>> df['FR_ID'] == '111'
	      
0     True
1    False
Name: FR_ID, dtype: bool
'''

print(df.loc[(df['Fail_Step'] == 'abc') & (df['Error_Info'] == 'kkk'), :])     #复杂条件查询

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


'''
改值操作
'''
df.at[0,'FR_Type'] = 'SW' #改值
df.iat[0,2] = 'ATC' #依据位置改值
df.loc[:,'FR_Type'] = 'ATC' #所有行的某列



'''
数据清洗
'''
df.isnull()     # 判断数据是否被认为无效，被认为无效的数据会被dropna()方法处理
'''
默认情况下，以下字符会被认为无效：
‘’, ‘#N/A’, ‘#N/A N/A’, ‘#NA’, ‘-1.#IND’, ‘-1.#QNAN’, ‘-NaN’, ‘-nan’, ‘1.#IND’, ‘1.#QNAN’, ‘<NA>’, ‘N/A’, ‘NA’, ‘NULL’, ‘NaN’, ‘n/a’, ‘nan’, ‘null’

可以通过参数na_values添加，例如：
missing_values = ["n/a", "na", "--"]
df = pd.read_csv('property-data.csv', na_values = missing_values)
'''


df.dropna(how='any') #drop掉有空值的行
'''
根据参数删除含有无效数据的行或者列
axis：默认为 0，表示逢空值剔除整行，如果设置参数 axis＝1 表示逢空值去掉整列。
how：默认为 'any' 如果一行（或一列）里任何一个数据有出现 NA 就去掉整行，如果设置 how='all' 一行（或列）都是 NA 才去掉这整行。
subset：设置想要检查的列。如果是多个列，可以使用列名的 list 作为参数。
inplace：如果设置 True，将计算得到的值直接覆盖之前的值并返回 None，修改的是源数据。
'''

df.fillna(value='') #把所有的空值替换成''
df['FR_Type'] = df.fillna('ATC',inplace=True)   #只把'FR_Type' 列的na值改为'ATC'
#在使用read_excel()时，如果使用了keep_default_na=False，所有的空白单元格的内容会变成空字符串
df['FR_Type'].mean()    # 列的平均值
df['FR_Type'].median()  # 列的中位数
df['FR_Type'].mode()    # 列中出现频率最高的

df.drop_duplicates(inplace = True)  # 删除重复的行


'''
拼接操作
'''

df2 = pd.DataFrame([['test3','224','ENV','gtwo']],columns=['ATC_Name','FR_ID','FR_Type','FR_Des'])
df=df.append(df2,ignore_index=True)
print(df)


'''
数据类型的操作
'''
df.astype('str') #把所有的数据转换成str，也可以按列来转换


