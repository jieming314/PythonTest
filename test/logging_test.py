import logging
logging.basicConfig(format='%(asctime)s : %(levelname)s : %(message)s', level=logging.INFO)

'''
logging模块的用法参照
https://blog.csdn.net/colinlee19860724/article/details/90965100
'''


logging.info('this is an info message')
logging.debug('this is a debug message')
logging.warning('this is a warning message')

'''
输出：
2022-03-16 14:49:31,072 : INFO : this is an info message
2022-03-16 14:49:31,073 : WARNING : this is a warning message
'''