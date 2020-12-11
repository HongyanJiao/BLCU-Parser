# !/usr/bin/env python
# -*- coding: UTF-8 -*-
import os
import sys
import math
import codecs
import random
import json
import argparse


def train_test_val(inp_path,out_path,p1,p2):
    with codecs.open(inp_path,'r',encoding='utf-8') as f_in:
        lines=f_in.readlines()
    random.shuffle(lines)
    V_T_num = math.ceil(len(lines) * p1)
    V_T_num2 = math.ceil(len(lines) * p2)+V_T_num
    Valid_dataset = lines[:V_T_num]
    Test_dataset = lines[V_T_num:V_T_num2]
    Train_dataset = lines[V_T_num2:]
    print('length of all dataset:{}'.format(len(lines)))

    if not os.path.exists(out_path):
        os.mkdir(out_path)

    # random.shuffle(Train_dataset)
    print('length of Training dataset:{}'.format(len(Train_dataset)))
    out = codecs.open(out_path + '/train.txt', 'w', encoding='utf-8')
    for data in Train_dataset:
        out.write("%s" % (data))

    # random.shuffle(Valid_dataset)
    print('length of Valid dataset:{}'.format(len(Valid_dataset)))
    out2 = codecs.open(out_path + '/dev.txt', 'w', encoding='utf-8')
    for data in Valid_dataset:
        out2.write("%s" % (data))

    # random.shuffle(Test_dataset)
    print('length of Test dataset:{}'.format(len(Test_dataset)))
    out3 = codecs.open(out_path + '/test.txt', 'w', encoding='utf-8')
    for data in Test_dataset:
        out3.write("%s" % (data))


def get_train_dev_test(inp_file,out_path,p1,p2):
    assert os.path.exists(inp_file), inp_file + " corpus not exists"
    if os.path.exists(out_path) == False:
        os.system('mkdir ' + out_path)
    train_test_val(inp_file, out_path,p1,p2)

if __name__ == '__main__':
    #inp_path = './data/18W/18W_lt500_plain.txt'
    #out_path = './data/18W/500'
    parser = argparse.ArgumentParser()
    parser.add_argument('--input_path', default='../../../data/news_tree/unk_segment')
    parser.add_argument('--out_path',default='../unk_data')
    parser.add_argument("--p1", default=0.1, type=float, help='out dataset path')
    parser.add_argument("--p2", default=0.1, type=float, help='out dataset path')
    args = parser.parse_args()
    get_train_dev_test(args.input_path,args.out_path,args.p1,args.p2)
