from gensim import corpora
import pprint


'''
以下内容为核心概念
https://radimrehurek.com/gensim/auto_examples/core/run_core_concepts.html#sphx-glr-auto-examples-core-run-core-concepts-py

    Document: some text.

    Corpus: a collection of documents.

    Vector: a mathematically convenient representation of a document.

    Model: an algorithm for transforming vectors from one representation to another.
'''


text_corpus = [
    "Human machine interface for lab abc computer applications",
    "A survey of user opinion of computer system response time",
    "The EPS user interface management system",
    "System and human system engineering testing of EPS",
    "Relation of user perceived response time to error measurement",
    "The generation of random binary unordered trees",
    "The intersection graph of paths in trees",
    "Graph minors IV Widths of trees and well quasi ordering",
    "Graph minors A survey",
]

# Create a set of frequent words
stoplist = set('for a of the and to in'.split(' '))
# Lowercase each document, split it by white space and filter out stopwords
texts = [[word for word in document.lower().split() if word not in stoplist]
         for document in text_corpus]


# pprint.pprint(texts)
'''
[['human', 'machine', 'interface', 'lab', 'abc', 'computer', 'applications'],
 ['survey', 'user', 'opinion', 'computer', 'system', 'response', 'time'],
 ['eps', 'user', 'interface', 'management', 'system'],
 ['system', 'human', 'system', 'engineering', 'testing', 'eps'],
 ['relation', 'user', 'perceived', 'response', 'time', 'error', 'measurement'],
 ['generation', 'random', 'binary', 'unordered', 'trees'],
 ['intersection', 'graph', 'paths', 'trees'],
 ['graph', 'minors', 'iv', 'widths', 'trees', 'well', 'quasi', 'ordering'],
 ['graph', 'minors', 'survey']]
'''

# Count word frequencies
from collections import defaultdict
'''
defaultdict的作用：
当从defaultdict取值时，如果key不存在，会返回一个默认值。
defaultdict接受一个工厂函数作为参数，这个factory_function可以是list、set、str等等。比如list对应[ ]，str对应的是空字符串，set对应set( )，int对应0
'''
frequency = defaultdict(int)
for text in texts:
    for token in text:
        frequency[token] += 1   #frequency[token] 第一次出现时值为0，得到的是texts中所有词的词频


# print(frequency)

# Only keep words that appear more than once
processed_corpus = [[token for token in text if frequency[token] > 1] for text in texts]
# pprint.pprint(processed_corpus)

'''
[['human', 'interface', 'computer'],
 ['survey', 'user', 'computer', 'system', 'response', 'time'],
 ['eps', 'user', 'interface', 'system'],
 ['system', 'human', 'system', 'eps'],
 ['user', 'response', 'time'],
 ['trees'],
 ['graph', 'trees'],
 ['graph', 'minors', 'trees'],
 ['graph', 'minors', 'survey']]
'''


dictionary = corpora.Dictionary(processed_corpus)
print(dictionary)
#dictionary.save('test.dict')  # store the dictionary, for future reference

'''
Dictionary(12 unique tokens: ['computer', 'human', 'interface', 'response', 'survey']...)
'''

pprint.pprint(dictionary.token2id)
'''
{'computer': 0,
 'eps': 8,
 'graph': 10,
 'human': 1,
 'interface': 2,
 'minors': 11,
 'response': 3,
 'survey': 4,
 'system': 5,
 'time': 6,
 'trees': 9,
 'user': 7}
'''

new_doc = "Human computer interaction"
new_vec = dictionary.doc2bow(new_doc.lower().split())
print(new_vec)

'''
dense vector(密集向量):         包含了所有元素的向量（包括值为0的）
sparse vector(稀疏向量):        去除密接向量中，向量元素的值为0的向量
bag-of-words vector(词袋向量):  和稀疏向量类似

dictionary.doc2bow 返回的是稀疏向量
[(0, 1), (1, 1)]
The first entry in each tuple corresponds to the ID of the token in the dictionary, the second corresponds to the count of this token.
注意: 因为interaction 不在字典里，所以不会被统计
'''


bow_corpus = [dictionary.doc2bow(text) for text in processed_corpus]
pprint.pprint(bow_corpus)
#corpora.MmCorpus.serialize('test_corpus.mm', bow_corpus)   #store to disk, for later use
#corpus = corpora.MmCorpus('test_corpus.mm')        #load a corpus iterator from a Matrix Market file, 这里得到的corpus 是一个迭代器对象，如果要得到内容的话，需要list() 或者用for循环

'''
[[(0, 1), (1, 1), (2, 1)],
 [(0, 1), (3, 1), (4, 1), (5, 1), (6, 1), (7, 1)],
 [(2, 1), (5, 1), (7, 1), (8, 1)],
 [(1, 1), (5, 2), (8, 1)],
 [(3, 1), (6, 1), (7, 1)],
 [(9, 1)],
 [(9, 1), (10, 1)],
 [(9, 1), (10, 1), (11, 1)],
 [(4, 1), (10, 1), (11, 1)]]
'''

from gensim import models

# train the model
tfidf = models.TfidfModel(bow_corpus)
#tfidf.save(r'/olt_tfidf.ti')   # save model to disk
#loaded_tfidf_model = models.TfidfModel.load(r'/olt_tfidf.ti')      #load model

# transform the "system minors" string
words = "system minors".lower().split()
print(tfidf[dictionary.doc2bow(words)])

'''
[(5, 0.5898341626740045), (11, 0.8075244024440723)]
元组中，第一个表示的是token id，第二个是td-idf加权值
system在原语料中出现4次，它的加权值低；minors在原语料中出现2次，它的加权值高
'''


from gensim import similarities

index = similarities.SparseMatrixSimilarity(tfidf[bow_corpus], num_features=12)

query_document = 'system engineering'.split()
query_bow = dictionary.doc2bow(query_document)
sims = index[tfidf[query_bow]]
print(list(enumerate(sims)))
'''
[(0, 0.0), (1, 0.32448703), (2, 0.41707572), (3, 0.7184812), (4, 0.0), (5, 0.0), (6, 0.0), (7, 0.0), (8, 0.0)]
从结果可以看出，query_document 的内容和第四篇的相似的最高71%
'''
#index.save('/tmp/deerwester.index')    # save index to disk
#index = similarities.MatrixSimilarity.load('/tmp/deerwester.index')    #load index


'''
基本流程:
First, we started with a corpus of documents.
Next, we transformed these documents to a vector space representation.
After that, we created a model that transformed our original vector representation to TfIdf.
Finally, we used our model to calculate the similarity between some query document and all documents in the corpus.

'''

from smart_open import open

url = 'http://smartlab-service.int.net.nokia.com:9000/log/Fi-IWF/66.031/IWF_7360_FX16_qiangel/SB_Logs_52A9-atxuser-Jan05050019/temp.tms'


def download_file(url):
    with open(url,'r',encoding='utf-8') as fp:
        for line in fp:
            yield line
            # yield dictionary.doc2bow(line.lower().split())

# corpus_file = download_file(url)
# print(corpus_file)

# print(list(corpus_file))

pprint.pprint(dictionary.dfs.items())