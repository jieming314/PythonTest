import seaborn as sns
import pandas as pd
import matplotlib.pyplot as plt
import os
import logging
logging.basicConfig(format='%(asctime)s : %(levelname)s : %(message)s', level=logging.INFO)

LOG_DIR = 'AI_LOG'
plt.style.use('fivethirtyeight')

'''
标签数量分布
'''
def map_fix_version_to_ti_type(fix_version):
    if fix_version.lower() == 'lsratc':
        return 'ATC'
    elif fix_version.lower() == 'rlab':
        return 'ENV'
    elif fix_version.lower().startswith('bbdr'):
        return 'SW-ONT'
    else:
        return 'SW'

# train_data = pd.read_excel(os.path.join(LOG_DIR,'ti_list_for_ml_20220521_baseline.xlsx'),engine='openpyxl')
# train_data['TI_TYPE'] = list(map(map_fix_version_to_ti_type, train_data['FIX_VERSION']))

# sns.countplot(x='TI_TYPE',data=train_data)
# plt.title('train_data')
# plt.show()


'''
文本长度分布, 无法在win下执行
'''
def return_text_len(file_name):
    with open(os.path.join(LOG_DIR,file_name), 'r', encoding='utf-8') as fp:
        text = fp.read()
    text = text.replace('\t',' ')
    text = text.replace('\n',' ')
    text = text.replace('\r\n',' ')
    text = text.replace('\r',' ')
    text = text.replace('&nbsp',' ')

    return len(text.split())

# train_data = pd.read_excel(os.path.join(LOG_DIR,'ti_list_for_ml_20220521_baseline.xlsx'),engine='openpyxl')
# train_data = train_data[:1000]  #截取前1000个结果

# train_data['TEXT_LEN'] = list(map(return_text_len, train_data['ROBOT_LOG']))

# sns.displot(x='TEXT_LEN',data=train_data)
# plt.yticks([])
# plt.show()

'''
散点分布图
'''
# train_data = pd.read_excel(os.path.join(LOG_DIR,'ti_list_for_ml_20220521_baseline.xlsx'),engine='openpyxl')
# train_data = train_data[:3000]  #截取前1000个结果

# train_data['TI_TYPE'] = list(map(map_fix_version_to_ti_type, train_data['FIX_VERSION']))
# train_data['TEXT_LEN'] = list(map(return_text_len, train_data['ROBOT_LOG']))

# sns.stripplot(x='TI_TYPE',y='TEXT_LEN',data=train_data)
# plt.show()


'''
计算词库长度
'''
# from itertools import chain

def return_text_as_list(file_name):
    with open(os.path.join(LOG_DIR,file_name), 'r', encoding='utf-8') as fp:
        text = fp.read()
    text = text.replace('\t',' ')
    text = text.replace('\n',' ')
    text = text.replace('\r\n',' ')
    text = text.replace('\r',' ')
    text = text.replace('&nbsp',' ')
    return text.split()

# train_data = pd.read_excel(os.path.join(LOG_DIR,'ti_list_for_ml_20220521_baseline.xlsx'),engine='openpyxl')
# train_data = train_data[:3000]  #截取前3000个结果

# train_vocab = set(chain(*map(return_text_as_list, train_data['ROBOT_LOG'])))
# print('total %s words' % len(train_vocab))

'''
词云
'''
# from wordcloud import WordCloud
# train_data = pd.read_excel(os.path.join(LOG_DIR,'ti_list_for_ml_20220521_baseline.xlsx'),engine='openpyxl')

# wordcloud = WordCloud(max_words=100,background_color='white')
# words_string = " ".join(return_text_as_list(train_data.loc[0,'ROBOT_LOG']))
# wordcloud.generate(words_string)    # wordcloud accept string type

# plt.figure()
# plt.imshow(wordcloud, interpolation='bilinear')
# plt.axis('off')
# plt.show()


'''
添加n-gram特征
给定一段文本序列,其中n各自或字的相邻共现特征即n-gram特征, n一般用取2或者3
假定分词列表['是谁','敲动','我心'], 对应的数值列表[1,34,21], 可以把“是谁”和“敲动” 两个词同时出现并相邻也作为一个特征1000加入到数值列表中
此时, 数值列表就变成了包含2-gram 特征的特征列表[1,34,21,1000]
'''
#提取2-gram 特征

# ngram_range = 2

# def create_ngram_set(input_list):
#     return set(zip(*[input_list[i:] for i in range(ngram_range)]))

# res = create_ngram_set([1,4,9,1,4])
# print(res)


'''
文本长度规范
把任意长度的文本变换成指定长度的文本, 通过截断或者补零

import keras.preprocessing import sequence
sequence.pad_sequence(x,y)
x 为文本序列, 例如：[[1,3,5,666,65,656,77], [43,454,54]]
y 为长度

如果指定y = 4, x 的返回为[[666 65 656 77], [0 43 454 54]]
'''

'''
文本数据增强

方法: 回译数据增强， 将文本数据翻译成另外一种语言(小语种), 再翻译回原语言, 即可得到与原语料同标签的新语料
'''
from httpcore import SyncHTTPProxy
from googletrans import Translator

p_sample1 = "酒店设施非常不错"
p_sample2 = "酒店价格比较便宜，交通方便"
p_sample3 = "卫生太差,吃的东西都发霉了"
p_sample4 = "无法使用电视机,隔音差"

http_proxy = SyncHTTPProxy((b'http', b'10.158.100.6', 8080, b''))

proxies = {
    'http': http_proxy,
    'https': http_proxy
}

translator = Translator(proxies = proxies)
res = []

for text in [p_sample1,p_sample2,p_sample3,p_sample4]:
    ja_res = translator.translate(text, dest='ja')
    zh_res = translator.translate(ja_res.text, dest='zh-cn')
    res.append(zh_res.text)

print(res)

print('script completed')