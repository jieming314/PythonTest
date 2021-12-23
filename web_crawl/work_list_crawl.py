import requests
import os
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)  #抑制InsecureRequestWarning 打印
from custom_requests import requests_get
from lxml import etree
import pandas as pd


'''
爬取confluence上的work list并保存在excel中
'''


if __name__ == '__main__':

    url = 'https://confluence-app.ext.net.nokia.com/display/FADOMAIN/RFW+work+list+2021'
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.45 Safari/537.36'}
    response = requests_get(url=url,headers=headers,timeout=5,verify=False,auth=('jieminbz','Jim#2345'))
    response.encoding = response.apparent_encoding
    page_text = response.text


    parser = etree.HTMLParser(encoding='utf-8')
    tree = etree.HTML(page_text,parser=parser)
    td_tag_list = tree.xpath('//td[@class="confluenceTd"]')

    work_list = []
    for i, td_tag in enumerate(td_tag_list):
        print(td_tag)
        td_context = td_tag.xpath('.//text()')  #取td tag下所有的文本
        if not td_context:
            continue
        elif td_context[0].lower() in ['jia', 'jieming', 'sunil', 'chunyan & others']:
            continue
        else:
            td_context = [each.replace('\xa0','') for each in td_context]       #去掉所有的'\xa0'
            # print(td_context)
            work = '\n'.join(td_context)
            work_list.append(work)

    # print(work_list)

    d = {
        'work_item': work_list
    }

    df = pd.DataFrame(data=d)

    sheet_name = 'Work List'
    writer = pd.ExcelWriter('work_list.xlsx',engine='xlsxwriter')
    df.to_excel(writer,index=False,sheet_name=sheet_name)

    workbook  = writer.book
    worksheet = writer.sheets[sheet_name]
    format1 = workbook.add_format({'text_wrap': True,'border': 1})
    worksheet.set_column('A:A', 120, format1)
    writer.save()

    print("over!!!")