from selenium import webdriver
from time import sleep

bro = webdriver.Chrome(executable_path='./chromedriver.exe')

bro.get('https://www.baidu.com')

sleep(2)

bro.quit()
