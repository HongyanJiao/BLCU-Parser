#coding:utf8
import argparse
import codecs
import src.trees as trees
import os
import sys
def process(fin, fout):
    for line in fin:
        flag = True
        words = line.strip().split()
        sent = '(ROOT (IP '
        if not words:
            flag = False
        for word in words:
            try:
                w, p = word.split('/')
                sent += '(' + str(p) + ' ' + str(w) + ')'
            except:
                flag = False
        sent += '))'
        trees.tree_from_str(sent)
        if flag:
            fout.write(sent + '\n')
def main(i, o):
    fin = codecs.open(i, 'r', 'utf8')
    fout = codecs.open(o, 'w', 'utf8')
    process(fin, fout)

if __name__=='__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--i', default='../../../data/rmrb.txt')
    parser.add_argument('--o', default='../../../data/rmrb.tree')
    args = parser.parse_args()
    main(args.i, args.o)