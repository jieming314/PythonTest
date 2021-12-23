from multiprocessing import Pool, cpu_count, Process
import time
import os

'''
使用进程池并行创建多个文件
'''


current_path = os.getcwd()
target_path = os.path.join(current_path, 'multi_test')
if os.path.exists(target_path):
    pass
else:
    os.mkdir(target_path)

file_num = 50
files_list = [f'test_{x}.py' for x in range(1,file_num+1)]

def write_lines_to_file(f):
    s = ['hello Tom\r' for i in range(100000)]
    for line in s:
        f.write(line)

def create_and_write_file(file_name):
    with open(os.path.join(target_path,file_name),'w') as f:
            write_lines_to_file(f)

def multi_file():

    p = Pool(cpu_count())
    for tmp_file in files_list:
        p.apply_async(create_and_write_file, args=(tmp_file,))
    
    p.close()
    p.join()

def new_multi_file():
    with Pool(cpu_count()) as p:
        p.map(create_and_write_file, files_list)


if __name__ == '__main__':
    print('Parent process %s.' % os.getpid())

    s_time = time.time()
    new_multi_file()
    e_time = time.time()

    print("cost %s seconds" % str(e_time - s_time))

'''

   
s_time = time.time()
p = Process(target=create_and_write_file, args=('test_1.py',))
p.start()
p.join()
e_time = time.time()
print("cost %s seconds" % str(e_time - s_time))

'''