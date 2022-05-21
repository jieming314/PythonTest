import time
import functools

def calc_time(fn):
    @functools.wraps(fn)
    def wrapper(*args,**kw):
        t1 = time.time()
        result = fn(*args,**kw)
        t2 = time.time()
        print("%s execution time is %s" % (fn.__name__,t2 - t1))
        return result
    return wrapper

def f1(lst1):
    '''
    generate all sub strings
    '''
    n = 0
    L = []
    l_len = len(lst1)
    while n < l_len:
        s1 = 0 # start left
        s2 = l_len - n #  start right
        while s2 <= l_len:
            L.append(lst1[s1:s2])
            s1 += 1
            s2 += 1
        n += 1
    return L

@calc_time
def f2(lst):
    '''
    search the max echo string
    '''
    l1 = f1(lst)
    #print("l1 is %s" % l1)
    l2 = f1(lst[::-1])
    #print("l2 is %s" % l2)
    s1 = set(l1)
    s2 = set(l2)
    s = s1 & s2
    s = sorted(s, key=lambda x: len(x))
    #test time
    #time.sleep(3)
    return s[-1]

def f3(n):
    '''
    print rhombus
    '''
    cmd_list = []
    m = 1
    while m <= n:
        max_mid_space = 2*(n-1) -1
        if n - m > 0:
            mid_space = max_mid_space - 2*(m-1)
            prt_str = " "*(m-1) + "*" + " "*mid_space + "*"
            cmd_list.insert(0,prt_str)
        else:
            prt_str = " "*(m-1) + "*"
            cmd_list.insert(0,prt_str)
        m += 1
    cmd_list = cmd_list + cmd_list[-2::-1]
    for cmd in cmd_list:
        print(cmd)


'''
问题：

实例化C时，只想执行Base 的__init__ 和 自己的__init___; C().f1 执行的是B的f1，如何实现？


'''
class Base(object):
    def __init__(self):
        print('Base.__init__')
    
    def f1(self,x):
        print("Base func")
        return x + 1

class A(Base):
    def __init__(self):
        super().__init__()
        print('A.__init__')
    
    def f1(self,x):
        print("A func")
        return x + 2

class B(Base):
    def __init__(self):
        super().__init__()
        print('B.__init__')
    
    def f1(self,x):
        print("B func")
        return x + 3

class C(A, B):
    def __init__(self):
        super(B,self).__init__()
        print('C.__init__')
    
    def f1(self,x):
        return super(A,self).f1(x)

def search_file(s):
    '''
    find and print all files whose name match s under current path
    '''
    import os
    file_list = []
    path_contents = os.listdir('.')

    for each in path_contents:
        if os.path.isdir(each):
            current_path = os.getcwd()
            os.chdir(each)
            file_list += search_file(s)
            os.chdir(current_path)
        else:
            if each.find(s) >= 0:
                file_list.append(os.path.join(os.getcwd(),each))
    
    return file_list

if __name__ == '__main__':
    s = f2('jljgllalfalfdsaljfdsal123ABCabaCBAa456flajflajfljljr33jllsf')
    print(s)

    f3(8)

    print(C.mro())
    x = C().f1(3)
    print(x)

    l = search_file('python')
    print(l)
    print(2)
    