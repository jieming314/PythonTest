from multiprocessing import Process, Queue
import random, time, os

'''
通过Queue实现进程间通信
假设主进程要升级2块LT和1块NT，先并行升级2块LT，等2块LT升级完成后，再升级NT
同时记录3块board 的升级是否成功
'''

def f1(q, name):
    pid = os.getpid()
    print('pid %s start' % pid)
    #time.sleep(random.random()*3)
    time.sleep(1)
    q.put((pid, name))
    print('pid %s end' % pid)

if __name__ == '__main__':
    max_num = 100

    start_time = time.time()

    q = Queue()
    for i in range(max_num):
        p = Process(target=f1,args=(q,f'p_{i+1}'))
        p.start()

    while q.qsize() < max_num:
        time.sleep(0.1)
    
    while not q.empty():
        print(q.get())

    end_time = time.time()
    print(end_time - start_time, 'seconds spend...')

    print('main process...')
