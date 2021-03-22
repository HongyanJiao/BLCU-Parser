# !/usr/bin/env python
# -*- coding: UTF-8 -*-

import codecs
import argparse
import re
import json
label2con = dict()
for i in range(0, 31):
    label2con[i] = []
def clean(str1):
    return float(str1.strip('tensor(').strip(')'))
def get_con(sentence, contributions):
    label_id = int(sentence.split()[-2])
    # contributions = contributions.strip('CONTRIBUTIONS:\t').strip('[(').strip(']\n').split('), (')
    # tmp_dict = dict()
    # for i in contributions:
    #     head, con = i.split(',')
    #     con = con.replace(' ','').strip('tensor(').strip(')')
    #     print(con)
    #     tmp_dict[int(head)] = float(con)
    pattern = re.compile('tensor\(0\.\d+\)')
    tensors = re.findall(pattern,contributions)
    tensor_list = list(map(clean, tensors))
    head = tensor_list.index(max(tensor_list))
    label2con[label_id].append(head)
def main(inp, out):
    fin = list(codecs.open(inp, 'r', 'utf8'))
    length = len(fin)
    i = 1
    while i < length - 1:
        is_match = re.match(r'\d', fin[i])
        if is_match:
            sentence = fin[i]
            contributions = fin[i + 1]
            if re.match('CONTRIBUTIONS:', contributions):
                i += 2
                get_con(sentence, contributions)
            else:
                i += 1
        else:
            i += 1
    print(label2con)
    json_str = json.dumps(label2con)
    with open(out, 'w') as json_file:
        json_file.write(json_str)


if __name__=='__main__':
    parser = argparse.ArgumentParser(description='tree to chunk')
    parser.add_argument('--i', default='../../../data/out.small')
    parser.add_argument('--o', default='../../../data/out.json')
    args = parser.parse_args()
    main(args.i,args.o)


