import re
import argparse
import codecs
import os
import sys
def process(fin, fout):
    for line in fin:
        if len(line) > 0:
            match = re.match('<id:(.*)>', line)
            if match:
                line = line.replace((str(match.group())), '')
                fout.write(line)
def main(inp_dir, out_dir):
    files = []
    if not os.path.exists(out_dir):
        os.mkdir(out_dir)
    for temp_root, temp_dirs, temp_files in os.walk(inp_dir):
        for temp_file in temp_files:
            if temp_file.startswith('.') == False \
                    and temp_file.endswith('.tree') == True \
                    and temp_file.endswith('.zip') == False:
                files.append(temp_file)
    for file in files:
        fin = codecs.open(os.path.join(inp_dir,file), 'r', 'utf8')
        fout = codecs.open(os.path.join(out_dir, file), 'w', 'utf8')
        process(fin, fout)

if __name__=='__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--inp_dir', default='../../../data/news_tree/news_tree')
    parser.add_argument('--out_dir', default='../../../data/news_tree/clean')
    args = parser.parse_args()
    main(args.inp_dir, args.out_dir)