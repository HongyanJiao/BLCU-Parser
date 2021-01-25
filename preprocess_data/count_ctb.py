# !/usr/bin/env python
# -*- coding: UTF-8 -*-
import codecs
from nltk import Tree
import argparse
# import src.trees as trees
import os
import sys
from ..src import trees
class Count(object):
    def __init__(self, file=None, dir=None):
        self.label_set = set()
        self.word_length_list = list()
        self.height_list = list()
        self.nums = 0
        # self.process_dir(dir)
        if dir:
            self.process_dir(dir)
        if file:
            self.count_label(file)
            self.count_hz_height(file)
        print('行数', self.nums)
        print(len(self.label_set), self.label_set)
        print('最大字数', max(self.word_length_list))
        print('平均字数', sum(self.word_length_list)/self.nums)
        print('最大高度', max(self.height_list))
        print('平均高度', sum(self.height_list) / self.nums)
    def process_dir(self, dir):
        for temp_root, temp_dirs, temp_files in os.walk(dir):
            for temp_file in temp_files:
                if temp_file.startswith('.') == False and temp_file.endswith('.zip') == False:
                    # and temp_file.endswith('.tree') == True \
                    # self.count_label(temp_root + '/' + temp_file)
                    self.count_hz_height(temp_root + '/' + temp_file)


    def count_label(self, file):
        train_treebank = trees.load_trees(file)
        train_parse = [tree.convert() for tree in train_treebank]
        for tree in train_parse:
            self.nums += 1
            nodes = [tree]
            while nodes:
                node = nodes.pop()
                if isinstance(node, trees.InternalParseNode):
                    for l in node.label:
                        self.label_set.add(l)
                    nodes.extend(reversed(node.children))
                else:
                    pass

    def count_hz_height(self, file):
        fin = codecs.open(file, 'r', encoding='utf8')
        for line in fin:
            self.nums += 1
            t = Tree.fromstring(line)
            self.height_list.append(t.height())
            self.word_length_list.append(len(''.join(t.leaves())))

if __name__=='__main__':
    parser = argparse.ArgumentParser(description='tree to chunk')
    parser.add_argument('--input_dir', default='../../../data/ctb8')
    parser.add_argument('--input_file', default='../../../data/PMT1.0_cfg_bi.txt')
    args = parser.parse_args()
    # Count(file=args.input_file, dir=None)
    Count(file=None, dir=args.input_dir)


