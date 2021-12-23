from flask import Flask
from flask import request


'''
用python运行脚本后，会启动一个web服务器
使用web框架，让我们专注于用一个函数处理一个URL，至于URL到函数的映射，就交给Web框架来做
例如下面的例子，3个函数处理3个URL。
注意，同一个URL /signin分别有GET和POST两种请求，映射到两个处理函数中。
flask 默认监听端口5000，浏览器中输入http://127.0.0.1:5000/，显示'Home'; 输入http://127.0.0.1:5000/signin, 显示一个输入
用户名和密码的页面
'''


app = Flask(__name__)

@app.route('/', methods=['GET', 'POST'])
def home():
    return '<h1>Home</h1>'

@app.route('/signin', methods=['GET'])
def signin_form():
    return '''<form action="/signin" method="post">
              <p><input name="username"></p>
              <p><input name="password" type="password"></p>
              <p><button type="submit">Sign In</button></p>
              </form>'''

@app.route('/signin', methods=['POST'])
def signin():
    # 需要从request对象读取表单内容：
    if request.form['username']=='admin' and request.form['password']=='password':
        return '<h3>Hello, admin!</h3>'
    return '<h3>Bad username or password.</h3>'

if __name__ == '__main__':
    app.run()

