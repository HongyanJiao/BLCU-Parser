# !/usr/bin/env python
# -*- coding: UTF-8 -*-
import jieba
import jieba_fast.posseg as pseg
import codecs
from nltk import Tree
import argparse
import re
import os

def Word2Char(fin, fout):
    for line in fin:
        t = Tree.fromstring(line)
        for pos in t.treepositions('leaves'):
            sent=''
            word = t[pos]
            for char in word:
                str1 = '(UNK ' + char + ')'
                sent += str1
            t[pos] = sent
        sent = str(t).replace('\n', '').replace(')(', ') (')
        while '  ' in sent:
            sent = sent.replace('  ', ' ')
        fout.write(sent + '\n')
def main(inp_dir, out_dir):
    for temp_root, temp_dirs, temp_files in os.walk(inp_dir):
        for temp_file in temp_files:
            if temp_file.startswith('.') == False \
                    and temp_file.endswith('.txt') == True \
                    and temp_file.endswith('.zip') == False:
                fin = codecs.open(temp_root + '/' +temp_file, 'r', 'utf8')
                fout = codecs.open(out_dir + '/' +temp_file, 'w', 'utf8')
                Word2Char(fin, fout)


if __name__=='__main__':
    parser = argparse.ArgumentParser(description='tree to chunk')
    parser.add_argument('--input_dir', default='../data')
    parser.add_argument('--output_dir', default='../char_data')
    args = parser.parse_args()
    main(args.input_dir,args.output_dir)


