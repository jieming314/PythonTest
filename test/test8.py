from multiprocessing import Process, Queue
import random, time, os

def f1(q, name):
  pid = os.getpid()
  print('pid %s start' % pid)
  time.sleep(random.random()*3)
  q.put((pid, name))
  print('pid %s end' % pid)

def test_proc(q,tag):
    print('current pid is %s' % os.getpid())
    print(f'tag is {tag}')
    q.put(tag)

if __name__ == '__main__':
  max_num = 5
  q = Queue()
  for i in range(max_num):
    p = Process(target=test_proc,args=(q,f'p_{i+1}'))
    p.start()

  #等待所有的f1进程都执行完
  while q.qsize() < max_num:
    time.sleep(0.1)

  #获取q队列中的值，一次get()操作只能取一个值，所以这里要用循环
  while not q.empty():
    print(q.get())
