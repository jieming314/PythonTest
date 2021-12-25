from multiprocessing import Process
import os

'''
最简单的启动多进程的方法
使用Process 类，start() 和 join()
'''

def foo():
    print(os.getpid())

if __name__ == '__main__':
    
    p_list =[]
    for i in range(5):
        p = Process(target=foo)
        p_list.append(p)
        p.start()
    
    print(p_list) # p_list 中是5个process 实例
    '''
    [<Process name='Process-1' pid=8764 parent=11336 started>, <Process name='Process-2' pid=3316 parent=11336 started>, <Process name='Process-3' pid=12724 parent=11336 started>, <Process name='Process-4' pid=8128 parent=11336 started>, <Process name='Process-5' pid=8552 parent=11336 started>]
    '''

    for p in p_list:
        p.join()

    print('main process over')


