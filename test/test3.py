from multiprocessing import Process, JoinableQueue
import random, time

'''
使用JoinableQueue实现多进程间的通信
生产者-消费者模式
'''

def consumer(q,name):
    while True:
        res = q.get()
        if res is None: break
        print(f'{name} consumes {res}')
        q.task_done()

def producer(q,name,food):
    #stime.sleep(random.random()*3)
    time.sleep(1)
    print(f'{name} produce {food}')
    res = (name, food)
    q.put(res)
    q.join()

if __name__ == '__main__':
    q = JoinableQueue()
    
    producer_num = 100
    consumer_num = 1
    producer_list = [ (f'p_{i}', f'food_{i}') for i in range(1,producer_num+1)]
    consumer_list = [ f'c_{i}' for i in range(1,consumer_num+1)]
    process_list = []

    start_time = time.time()

    for each in producer_list:
        p = Process(target=producer, args=(q,each[0],each[1]))
        process_list.append(p)
        p.start()
    
    for each in consumer_list:
        p = Process(target=consumer, args=(q,each))
        p.daemon = True
        p.start()

    for p in process_list:
        p.join()

    end_time = time.time()
    print(end_time - start_time, 'seconds spend...')

    print('main process...')