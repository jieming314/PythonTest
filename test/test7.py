'''
测试异步I/O
'''
import asyncio
import time

async def hello1():
    print('Hello world 1')
    await asyncio.sleep(1)
    print('Hello world 1 over')
    return 'hello1 done'


async def hello2():
    print('Hello world 2')
    await asyncio.sleep(3)
    print('Hello world 2 over')
    return 'hello2 done'


async def hello3():
    print('Hello world 3')
    await asyncio.sleep(1)
    print('Hello world 3 over')
    return 'hello3 done'


start_time = time.time()

loop = asyncio.get_event_loop()
task_list = [hello1, hello2, hello3]
tasks = [loop.create_task(task()) for task in task_list]
loop.run_until_complete(asyncio.wait(tasks))
#task = loop.create_task(hello1())
#loop.run_until_complete(task)

loop.close()

for task in tasks:
    print(task.result())



end_time = time.time()
print(end_time - start_time, 'seconds spend...')
