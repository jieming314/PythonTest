import time

'''
使用协程实现生产者-消费者模式
'''

def consumer():
    yield
    while True:
        item = yield
        print(f'consuming {item}...')
        if not item:
            break

def producer(c, food_list):
    c.send(None)
    for food in food_list:
        time.sleep(0.1) #cost 0.1 second to produce an item
        print(f'produce {food}...')
        c.send(food)
        print(f'{food} is consumed...')
    c.close()

max_num = 10
food_list = [ f'Apple_{i}' for i in range(1, max_num + 1)]

g = consumer()
producer(g,food_list)