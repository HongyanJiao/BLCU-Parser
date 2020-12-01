# !/usr/bin/env python
# -*- coding: UTF-8 -*-
import jieba
import jieba_fast.posseg as pseg
import codecs
from nltk import Tree
import argparse
import re
import os

def SegPOS(inPath,fOut):

    with codecs.open(inPath, 'r', encoding='utf-8') as sentences:
        for line in sentences:
            t = Tree.fromstring(line)
            sentences = []
            for pos in t.treepositions('leaves'):
                sent=''
                for wordlist, wordpos in pseg.cut(t[pos]):
                    str1 = '('+wordpos+' '+ wordlist+')'
                    sent+=str1
                t[pos] = sent
            sent = str(t).replace('\n', '').replace(')(', ') (')
            while '  ' in sent:
                sent = sent.replace('  ', ' ')
            # print(sent)
            fOut.write(sent + '\n')
def main(inp_dir, out_file):
    files = []
    for temp_root, temp_dirs, temp_files in os.walk(inp_dir):
        for temp_file in temp_files:
            if temp_file.startswith('.') == False \
                    and temp_file.endswith('.tree') == True \
                    and temp_file.endswith('.zip') == False:
                files.append(temp_root + '/' +temp_file)
    fOut = codecs.open(out_file, 'w', encoding='utf-8')
    for file in files:
        SegPOS(file, fOut)
if __name__=='__main__':
    parser = argparse.ArgumentParser(description='tree to chunk')
    parser.add_argument('--input_dir', default='../../../data/news_tree/clean')
    parser.add_argument('--output_file', default='../../../data/news_tree/segment')
    args = parser.parse_args()
    main(args.input_dir,args.output_file)


