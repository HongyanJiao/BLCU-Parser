# !/usr/bin/env python
# -*- coding: UTF-8 -*-

import codecs
import argparse
import re
import json
# IP 2, ('NP-SBJ',) 6 ,('NP-OBJ',) 8  ('VP-PRD',) 7  ('VP-OBJ',) 13  ('ROOT', 'IP') 12

def count_label(label2heads, label_id):
    head_list = label2heads[label_id]
    head_dict = [0] * 31
    for i in head_list:
        head_dict[int(i)] += 1
    sum_times = sum(head_dict)
    return list(map(lambda x: "{0:.4f}".format(x /sum_times),head_dict))
def main(inp, out):
    label2heads = json.load(open(inp, 'r'))
    # label_id = '2'
    id_list = ['12','7']
    for label_id in id_list:
        head_list = count_label(label2heads,label_id)
        print(head_list)



if __name__=='__main__':
    parser = argparse.ArgumentParser(description='tree to chunk')
    parser.add_argument('--i', default='../../../data/out.json')
    parser.add_argument('--o', default='../../../data/out.json')
    args = parser.parse_args()
    main(args.i,args.o)


