#coding:utf8
import argparse
import codecs
import os
import sys
def process(fin, fout):
    for line in fin:
        words = line.strip().split()
        if words and '/' in words[0]:
            sent = '(ROOT (IP '
            for word in words:
                w, p = word.split('/')
                sent += '(' + str(p) + ' ' + str(w) + ')'
            sent += '))'
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