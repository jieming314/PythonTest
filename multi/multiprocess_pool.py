from multiprocessing import Pool, Process
import os
import time

'''
使用进程池创建多进程
'''

def foo(i,**kw):
    pid = os.getpid()
    print(f'start child process {pid}')
    print(f'i is {i}')
    print(f'kw is {kw}')
    time.sleep(i)
    print(f'stop child process {pid}')
    return i

if __name__ == '__main__':

    '''
    下面的方法使用Pool.apply_async(),Pool.close() 和 Pool.join()的方法创建进程池并执行子进程
    close() 和 join() 是必须的。join()保证阻塞主进程，保证进程池内所有的进程执行玩后再继续
    如果不用join()的话，主进程不会阻塞，会瞬间完成，进程池中的进程也相应结束（可能这些子进程本身并没有执行完）
    如果要获得所有子程序的返回，可以先把子进程的结果存在一个list中，再用get()方法获取
    下列代码段执行时间约为4s
    '''

    # s_time = time.time()
    # pid = os.getpid()
    # print(f'main process {pid} start')
    # dict1 = {'a': 1}
    # with Pool() as p:
    #     result = []
    #     for i in range(1,5):
    #         '''
    #         p.apply_async() 会返回一个异步结果对象，例如:
    #         <multiprocessing.pool.ApplyResult object at 0x00000239A8886BB0>
    #         '''
    #         result.append(p.apply_async(foo,(i,),dict1))
    #     p.close()
    #     p.join()

    # print([p.get() for p in result])

    # e_time = time.time()
    # print(f'main process {pid} end')
    # print("main process cost %s seconds" % str(e_time - s_time))


    '''
    下面的方法使用Pool.map()
    '''

    s_time = time.time()
    pid = os.getpid()
    print(f'main process {pid} start')
    dict1 = {'a': 1}
    with Pool() as p:
        result = []
        list1 = [1,2,3,4]
        '''
        使用偏函数重新定义一个函数new_foo, Pool.map()作用在这个新的函数上
        这里由于使用的是map_async(), 必须要使用close()和join()方法阻塞主进程，不然主进程会迅速结束
        如果使用的是map(), 则不需要close()和join() 因为map本身是会阻塞主进程的
        '''

        from functools import partial
        new_foo = partial(foo,**dict1)
        result = p.map_async(new_foo,list1)

        p.close()
        p.join()

    print(result.get())
    e_time = time.time()
    print(f'main process {pid} end')
    print("main process cost %s seconds" % str(e_time - s_time))

