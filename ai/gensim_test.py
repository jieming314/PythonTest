import pprint
import logging
logging.basicConfig(format='%(asctime)s : %(levelname)s : %(message)s', level=logging.INFO)


if __name__ == '__main__':
    

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

    import gensim
    processed_text_list = []

    text_name_list = ['traffic_log1.html', 'traffic_log2.html']
    for each in text_name_list:
        with open(each,'r',encoding='utf-8') as fp:
            text = fp.read().encode('UTF-8')
        new_text = gensim.utils.simple_preprocess(text)
        logging.debug(new_text)
        processed_text_list.append(new_text)
    
    from gensim import corpora
    dictionary = corpora.Dictionary(processed_text_list)
    logging.info(dictionary)

    #返回一个新文本的词袋向量[(642, 1), (1996, 1), (2044, 1)]
    #logging.debug(dictionary.doc2bow("html class id".lower().split()))

    bow_text_list = [dictionary.doc2bow(each) for each in processed_text_list]
    logging.debug(bow_text_list)

    from gensim import models
    '''
    训练模型，td-idf模型把词袋向量变换成基于tf-idf的词频向量
    '''
    tfidf = models.TfidfModel(bow_text_list) #训练模型
    tfidf_text = tfidf[bow_text_list]
    numtopics=2
    lsi = models.LsiModel(tfidf_text, id2word=dictionary, num_topics=numtopics)

    from gensim import similarities
    index = similarities.MatrixSimilarity(lsi[bow_text_list])


    #相似度比较

    with open('traffic_log3.html','r',encoding='utf-8') as fp:
        text = fp.read().encode('UTF-8')
    new_text = gensim.utils.simple_preprocess(text)
    tfidf_new_text = tfidf[dictionary.doc2bow(new_text)]
    lsi_new_text = lsi[tfidf_new_text]

    sims = index[lsi_new_text]
    logging.info(sims)
    



