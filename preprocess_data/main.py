# !/usr/bin/env python
# -*- coding: UTF-8 -*-

import os
import preprocess_data.build_tree as build_tree
import codecs
import json
import argparse

I_ROOT = 0
I_FILE = 0


#遍历文件夹
def iter_files(inp_dir,fOut,f_wrong,f_luan):
    #遍历根目录
    global I_ROOT,I_FILE
    for root,dirs,files in os.walk(inp_dir):
        for file in files:
            file_name = os.path.join(root,file)
            I_FILE += 1
            print(I_FILE,file_name)
            I_ROOT=build_tree.ReadCorpus(I_ROOT,file_name, fOut,f_wrong,f_luan)
        for dirname in dirs:
            #递归调用自身,只改变目录名称
            iter_files(dirname,fOut,f_wrong)


def parseargs():
    parser = argparse.ArgumentParser()
    # parser.add_argument("--inp_path", default='../data/clean_root/', help="input corpus")
    # parser.add_argument("--out_path", default='../data/chunk_data_out/',help='out dataset path')
    parser.add_argument("--inp_path", default='../../../data/news_tree/news_tree', help="input corpus")
    parser.add_argument("--out_path", default='../t_out/', help='out dataset path')
    return parser.parse_args()


def main():
    my_args =parseargs()
    input_dir = my_args.inp_path
    output_dir = my_args.out_path  # clean_root and wrong_clean_root
    if os.path.exists(output_dir):
        os.system('rm -rf ' + output_dir)
    os.system('mkdir ' + output_dir)

    f_wrong = open(output_dir+'/wrong_clean_root.json', 'w')
    fOut = codecs.open(output_dir+'/clean_root.txt', 'w', encoding='utf-8', errors='ignore')
    f_luan = codecs.open(output_dir+'/luan_clean_root.txt', 'w', encoding='utf-8', errors='ignore')
    print('Begin building chunk tree .....................')
    iter_files(input_dir, fOut, f_wrong,f_luan)
    fOut.close()
    f_wrong.close()
    print('There are ' + str(I_ROOT) + ' lines in clean root files!')
    print('There are ' + str(I_FILE) + ' files in clean root files!')



if __name__ == '__main__':
    main()