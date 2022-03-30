from lxml import etree
import os

parent_dir = 'ML_LOG'
file_name = 'SHA_NC_OLT_CFXRE_DFMBA_MPM_EONUAV_WEEKLY_01_44_SLS_BATCH_1_MGMT_output.xml'
atc_name = 'FT_PARALLEL_UPLOAD_ABORT'

parser = etree.HTMLParser(encoding='utf-8')
tree = etree.parse(os.path.join(parent_dir,file_name),parser=parser)

# testcase_xpath = f'//test[@name="{atc_name}"]'
# print(testcase_xpath)

test_tag = tree.xpath(f'//test[@name="{atc_name}"]')[0]
test_id = test_tag.xpath('./@id')[0]
print(test_id)
# test_kw_tags = test_tag.xpath('.//kw')  #all kw tag under this test
# test_messages = []
# for kw_tag in test_kw_tags:
#     kw_name = kw_tag.xpath('./@name')[0]
#     #print(kw_name)
#     kw_args = kw_tag.xpath('./arguments//text()')
#     if kw_args:
#         kw_args = [each for each in kw_args if each != '\r\n']
#     #print(kw_args)
#     test_messages.append(kw_name + ' '*4 + " ".join(kw_args) + '\n')    # add kw name + args
#     kw_msg_tags = kw_tag.xpath('./msg')
#     for kw_msg_tag in kw_msg_tags:
#         tmp_msg = kw_msg_tag.xpath('./text()')[0] + '\n'
#         #print('tmp msg is %s' % tmp_msg)
#         test_messages.append(tmp_msg)

# print(len(test_messages))
# with open('case_step_messages.txt','w',encoding='UTF-8') as fp:
#     fp.writelines(test_messages) 






test_id_list = test_id.split('-')[0:-1]
print(test_id_list)

setup_messages = []
for num, id in enumerate(test_id_list):
    if num == 0:
        test_id = id
    else:
        test_id = test_id + '-' + id
    suite_tag = tree.xpath(f'//suite[@id="{test_id}"]')[0]
    suite_name = suite_tag.xpath('./@name')[0]
    print(suite_tag)
    print(suite_name)
    suite_setup_kw_tags = suite_tag.xpath('./kw[@type="setup"]')  #当前这个suite 直接的setup keyword(第一层)
    for suite_setup_kw_tag in suite_setup_kw_tags:
        suite_setup_kw_name = suite_setup_kw_tag.xpath('./@name')[0]
        print(f'suite setup name: {suite_setup_kw_name}')
        suite_setup_kw_args = suite_setup_kw_tag.xpath('./arguments//text()')
        if suite_setup_kw_args:
            suite_setup_kw_args = [each for each in suite_setup_kw_args if each != '\r\n']
            #print(suite_setup_kw_args)
            setup_messages.append(suite_setup_kw_name + ' '*4 + " ".join(suite_setup_kw_args) + '\n')    # add kw name + args
        else:
            setup_messages.append(suite_setup_kw_name + '\n')
        suite_setup_kw_msg_tags = suite_setup_kw_tag.xpath('./msg')
        for suite_setup_kw_msg_tag in suite_setup_kw_msg_tags:
            tmp_msg = suite_setup_kw_msg_tag.xpath('./text()')[0] + '\n'
            setup_messages.append(tmp_msg)

        suite_setup_child_kw_tags = suite_setup_kw_tag.xpath('.//kw') #get all child kws under this first level setup kw
        #print(suite_setup_child_kw_tags)
        for suite_setup_child_kw_tag in suite_setup_child_kw_tags:
            suite_setup_child_kw_name = suite_setup_child_kw_tag.xpath('./@name')[0]
            print(suite_setup_child_kw_name)
            suite_setup_child_kw_args = suite_setup_child_kw_tag.xpath('./arguments//text()')
            if suite_setup_child_kw_args:
                suite_setup_child_kw_args = [each for each in suite_setup_child_kw_args if each != '\r\n']
                #print(suite_setup_child_kw_args)
                setup_messages.append(suite_setup_child_kw_name + ' '*4 + " ".join(suite_setup_child_kw_args) + '\n')    # add kw name + args
            else:
                setup_messages.append(suite_setup_child_kw_name + '\n')
            suite_setup_child_kw_msg_tags = suite_setup_child_kw_tag.xpath('./msg')
            for suite_setup_child_kw_msg_tag in suite_setup_child_kw_msg_tags:
                tmp_msg = suite_setup_child_kw_msg_tag.xpath('./text()')[0] + '\n'
                setup_messages.append(tmp_msg)



        

        #tmp_messages = suite_setup_tag.xpath('.//text()')
        #print(tmp_messages)
#         print(len(tmp_messages))
#         setup_messages.extend(tmp_messages)

print(len(setup_messages))
with open('case_setup_step_test.txt','w',encoding='UTF-8') as fp:
    fp.writelines(setup_messages)


# suite_tag = tree.xpath(f'//suite[@id="s1"]')[0]
# suite_name = suite_tag.xpath('./@name')[0]
# suite_setup_tag_list = suite_tag.xpath('./kw[@type="setup"]')  #当前层级下直接的setup keyword
# print(suite_tag)
# print(suite_name)

# setup_messages = []
# for suite_setup_tag in suite_setup_tag_list:
#     setup_name = suite_setup_tag.xpath('./@name')[0]
#     print(setup_name)
#     tmp_messages = suite_setup_tag.xpath('.//text()')
#     #print(tmp_messages)
#     setup_messages.extend(tmp_messages)


# suite_tag = tree.xpath(f'//suite[@id="s1-s1"]')[0]
# suite_name = suite_tag.xpath('./@name')[0]
# print(suite_tag)
# print(suite_name)


# suite_tag = tree.xpath(f'//suite[@id="s1-s1-s1-s2-s2"]')[0]
# suite_name = suite_tag.xpath('./@name')[0]
# print(suite_tag)
# print(suite_name)

# case_messages = tree.xpath('//test[@name="{}"]//text()'.format(atc_name))
# print(len(case_messages))