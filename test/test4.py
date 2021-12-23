import threading
import time
import os

'''
使用多进程并行创建多个文件
'''

current_path = os.getcwd()
target_path = os.path.join(current_path, 'multi_test')
if os.path.exists(target_path):
    pass
else:
    os.mkdir(target_path)

file_num = 500

def write_lines_to_file(f):
    s = ['hello Tom\r' for i in range(100000)]
    for line in s:
        f.write(line)

def create_and_write_file(file_name):
    with open(os.path.join(target_path,file_name),'w') as f:
            write_lines_to_file(f)

def single_file():
    files_list = [f'test_{x}.py' for x in range(1,file_num+1)]
    for tmp_file in files_list:
        with open(os.path.join(target_path,tmp_file),'w') as f:
            write_lines_to_file(f)

def multi_file():
    files_list = [f'test_{x}.py' for x in range(1,file_num+1)]

    threads = []
    for tmp_file in files_list:
        t = threading.Thread(target=create_and_write_file, args=(tmp_file,))
        threads.append(t)
    
    for t in threads:
        t.start()
    
    for t in threads:
        t.join()

s_time = time.time()
single_file()
e_time = time.time()

print("cost %s seconds" % str(e_time - s_time))

