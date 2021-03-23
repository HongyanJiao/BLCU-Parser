# !/usr/bin/env python
# -*- coding: UTF-8 -*-

import codecs
import argparse
import pandas as pd
import re
import json
# IP 2, ('NP-SBJ',) 6 ,('NP-OBJ',) 8  ('VP-PRD',) 7  ('VP-OBJ',) 13  ('ROOT', 'IP') 12

# def count_label(label2heads, label_id):
#     head_list = label2heads[label_id]
#     head_dict = [0] * 31
#     for i in head_list:
#         head_dict[int(i)] += 1
#     sum_times = sum(head_dict)
#     return list(map(lambda x: "{0:.4f}".format(x /sum_times),head_dict))
def main(inp, out):
    # label2heads = json.load(open(inp, 'r'))
    # label_id = '2'
    # id_list = ['12','7']
    # for label_id in id_list:
    #     head_list = count_label(label2heads,label_id)
    #     print(head_list)
    df = pd.DataFrame()
    fin = codecs.open(inp, 'r', 'utf8')
    label2head = dict()
    for line in fin:
        if line[0] == '(':
            label, label_id, head = line.strip().split('\t')
            if label not in label2head:
                label2head[label] = [0] * 31
            label2head[label][int(head)] += 1
    for k, v in label2head.items():
        sum_times = sum(v)
        df[k] = list(map(lambda x: "{0:.4f}".format(x / sum_times), v))
    df.to_csv(out, float_format='%.4f', encoding='utf8')




if __name__=='__main__':
    parser = argparse.ArgumentParser(description='tree to chunk')
    parser.add_argument('--i', default='../../../data/all.small')
    parser.add_argument('--o', default='../../../data/out.csv')
    args = parser.parse_args()
    main(args.i,args.o)


