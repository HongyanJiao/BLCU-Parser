import argparse
import trees
import pandas as pd
labels = ['ROOT', 'IP', 'NP-HLP', 'VP-HLP', 'NULL-HLP', 'NP-OBJ', 'VP-OBJ', 'UNK-OBJ',
           'NP-SBJ', 'VP-SBJ','UNK-SBJ', 'NP-NPRE','VP-PRD',
            'NULL-MOD', 'NULL-AUX', 'NULL-CON', 'w-CON', 'W']
tags38 = ['b', 'nz', 'q', 'h', 'v', 'p', 'm', 'ns', 's', 'j', 'k', 't', 'a', 'Dg', 'Ag', 'z', 'nx', 'o', 'vn', 'an', 'y', 'n', 'c', 'r', 'd', 'Vg', 'i', 'Tg', 'u', 'f', 'ad', 'vd', 'e', 'nr', 'nt', 'Ng', 'l']
# print('label数量：', len(labels))
def init_dict(labels):
    return {label:0 for label in labels}
class ChunkStruct(object):
    def __init__(self, label, left, right):
        self.label = label
        self.left = left
        self.right = right
def Tree2DataStruct(train_treebank):
    train_parse = [tree.convert() for tree in train_treebank]
    label_all_structs = [] # for the whole file
    tag_all_structs = []
    for tree in train_parse:
        nodes = [tree]
        one_tree_struct = []
        one_tree_tags = []
        while nodes:
            node = nodes.pop()
            if isinstance(node, trees.InternalParseNode):
                # label = node.label[-1]
                for label in node.label:
                    if label in labels:
                        one_tree_struct.append(ChunkStruct(label, node.left, node.right))
                    if label in tags38:
                        one_tree_tags.append(ChunkStruct(label, node.left, node.right))


                nodes.extend(reversed(node.children))
        label_all_structs.append(one_tree_struct)
        tag_all_structs.append(one_tree_tags)
    return label_all_structs, tag_all_structs


def ReadTrees(path):
    train_treebank = trees.load_trees(path)
    label_all_structs, tag_all_structs = Tree2DataStruct(train_treebank)
    print('load:{} lines in file:{}'.format(len(label_all_structs), path))
    # for one_tree_struct in all_structs:
    #     print(len(one_tree_struct), end=',')
    # print()
    return label_all_structs, tag_all_structs
def Cmp(one_gold_struct, one_pred_struct, local_labels):
    model_right_one_tree = init_dict(local_labels)
    for g in one_gold_struct:
        for p in one_pred_struct:
            if p.label == g.label and p.left == g.left and p.right == g.right:
                model_right_one_tree[p.label] += 1
    return model_right_one_tree

def Count(g_struct, p_struct, local_labels):
    input_all = init_dict(local_labels)
    model_all = init_dict(local_labels)
    model_right = init_dict(local_labels)

    for one_gold_struct, one_pred_struct in zip(g_struct,p_struct):
        for gold in one_gold_struct:
            input_all[gold.label] += int(1)
        for pred in one_pred_struct:
            model_all[pred.label] += 1
        model_right_one_tree = Cmp(one_gold_struct, one_pred_struct, local_labels)
        for label, freq in model_right_one_tree.items():
            model_right[label] += freq
    return  model_all, input_all, model_right


def ComputeF1(gold_path, predict_path):
    g_struct, g_tag = ReadTrees(gold_path)
    p_struct, p_tag = ReadTrees(predict_path)
    assert len(g_struct) == len(p_struct), f'{g_struct},{p_struct}'
    def helper(g_struct, p_struct,local_labels):
        all_model_right = 0
        all_model_all = 0
        all_input_all = 0
        model_all, input_all, model_right = Count(g_struct, p_struct,local_labels)

        F1 = []
        '''
                Precision = model_right/model_all
                Recall = model_right/input_all
                F1 = (2 * Precision * Recall) /(Precision + Recall)
        '''
        for mr,ma,ia in zip(model_right.values(), model_all.values(), input_all.values()):
            ret = []
            all_model_right += mr
            all_model_all += ma
            all_input_all += ia
            if ma==0 or ia==0:
                ret = [0,0,0]
                f=0
            else:
                p = mr / ma
                r = mr / ia
                try:
                    f = (2 * p * r) / (p + r)
                except:
                    f = 0.0
                ret = [p,r,f]
            F1.append(ret)
        try:
            micro_p = all_model_right / all_model_all
        except:
            micro_p = 0
        try:
            micro_r = all_model_right / all_input_all
        except:
            micro_r = 0
        try:
            micro_f = (2 * micro_p * micro_r) / (micro_p + micro_r)
        except:
            micro_f = 0
        return F1, input_all, micro_p, micro_r, micro_f, all_input_all

    F1, input_all, micro_p, micro_r, micro_f, all_input = helper(g_struct,p_struct, labels)
    tF1, tinput_all, tmicro_p, tmicro_r, tmicro_f, tall_input = helper(g_tag,p_tag, tags38)
    return F1, input_all, micro_p, micro_r, micro_f, all_input, \
        tF1, tinput_all, tmicro_p, tmicro_r, tmicro_f, tall_input
def get_labels():
    tmp = [('IP',), ('IP', 'NP-HLP'), ('IP', 'NP-NPRE'), ('IP', 'VP-HLP'), ('IP', 'VP-PRD'), ('IP', 'w'),
           ('NP-HLP',), ('NP-NPRE',), ('NP-OBJ',), ('NP-SBJ',), ('NULL-AUX',), ('NULL-CON',), ('NULL-HLP',),
           ('NULL-MOD',), ('ROOT',), ('ROOT', 'IP'), ('ROOT', 'IP', 'NP-HLP'), ('ROOT', 'IP', 'NP-NPRE'),
           ('ROOT', 'IP', 'VP-HLP'), ('ROOT', 'IP', 'VP-PRD'), ('UNK-OBJ',), ('UNK-SBJ',), ('VP-HLP',), ('VP-OBJ',),
           ('VP-OBJ', 'VP-PRD'), ('VP-PRD',), ('VP-PRD', 'VP-PRD'), ('VP-SBJ',), ('VP-SBJ', 'VP-PRD'), ('w',),
           ('w-CON',)]
    tmp1 = [('Ag',), ('Dg',), ('IP',), ('IP', 'NP-HLP'), ('IP', 'NP-HLP', 'n'), ('IP', 'NP-HLP', 'nt'), ('IP', 'NP-HLP', 'w'), ('IP', 'NP-NPRE'), ('IP', 'NP-NPRE', 'n'), ('IP', 'VP-HLP', 'i'), ('IP', 'VP-HLP', 'l'), ('IP', 'VP-PRD'), ('IP', 'w', 'w'), ('NP-HLP',), ('NP-HLP', 'i'), ('NP-HLP', 'j'), ('NP-HLP', 'l'), ('NP-HLP', 'm'), ('NP-HLP', 'n'), ('NP-HLP', 'nr'), ('NP-HLP', 'ns'), ('NP-HLP', 'nt'), ('NP-HLP', 'nz'), ('NP-HLP', 'r'), ('NP-HLP', 't'), ('NP-HLP', 'v'), ('NP-HLP', 'vn'), ('NP-NPRE',), ('NP-NPRE', 'b'), ('NP-NPRE', 'l'), ('NP-NPRE', 'm'), ('NP-NPRE', 'n'), ('NP-NPRE', 'nr'), ('NP-NPRE', 'r'), ('NP-NPRE', 't'), ('NP-OBJ',), ('NP-OBJ', 'Ag'), ('NP-OBJ', 'Ng'), ('NP-OBJ', 'Vg'), ('NP-OBJ', 'a'), ('NP-OBJ', 'ad'), ('NP-OBJ', 'an'), ('NP-OBJ', 'b'), ('NP-OBJ', 'c'), ('NP-OBJ', 'd'), ('NP-OBJ', 'f'), ('NP-OBJ', 'i'), ('NP-OBJ', 'j'), ('NP-OBJ', 'k'), ('NP-OBJ', 'l'), ('NP-OBJ', 'm'), ('NP-OBJ', 'n'), ('NP-OBJ', 'nr'), ('NP-OBJ', 'ns'), ('NP-OBJ', 'nt'), ('NP-OBJ', 'nx'), ('NP-OBJ', 'nz'), ('NP-OBJ', 'p'), ('NP-OBJ', 'q'), ('NP-OBJ', 'r'), ('NP-OBJ', 's'), ('NP-OBJ', 't'), ('NP-OBJ', 'u'), ('NP-OBJ', 'v'), ('NP-OBJ', 'vn'), ('NP-OBJ', 'y'), ('NP-OBJ', 'z'), ('NP-SBJ',), ('NP-SBJ', 'Ng'), ('NP-SBJ', 'a'), ('NP-SBJ', 'ad'), ('NP-SBJ', 'an'), ('NP-SBJ', 'b'), ('NP-SBJ', 'c'), ('NP-SBJ', 'd'), ('NP-SBJ', 'f'), ('NP-SBJ', 'i'), ('NP-SBJ', 'j'), ('NP-SBJ', 'l'), ('NP-SBJ', 'm'), ('NP-SBJ', 'n'), ('NP-SBJ', 'nr'), ('NP-SBJ', 'ns'), ('NP-SBJ', 'nt'), ('NP-SBJ', 'nx'), ('NP-SBJ', 'nz'), ('NP-SBJ', 'p'), ('NP-SBJ', 'q'), ('NP-SBJ', 'r'), ('NP-SBJ', 's'), ('NP-SBJ', 't'), ('NP-SBJ', 'u'), ('NP-SBJ', 'v'), ('NP-SBJ', 'vn'), ('NP-SBJ', 'z'), ('NULL-AUX',), ('NULL-AUX', 'e'), ('NULL-AUX', 'r'), ('NULL-AUX', 'u'), ('NULL-AUX', 'v'), ('NULL-AUX', 'y'), ('NULL-CON',), ('NULL-CON', 'c'), ('NULL-CON', 'd'), ('NULL-CON', 'f'), ('NULL-CON', 'l'), ('NULL-CON', 'm'), ('NULL-CON', 'n'), ('NULL-CON', 'p'), ('NULL-CON', 'q'), ('NULL-CON', 'r'), ('NULL-CON', 't'), ('NULL-CON', 'u'), ('NULL-CON', 'v'), ('NULL-CON', 'w'), ('NULL-HLP', 'e'), ('NULL-HLP', 'n'), ('NULL-HLP', 'nr'), ('NULL-HLP', 'ns'), ('NULL-HLP', 'nz'), ('NULL-HLP', 'u'), ('NULL-MOD',), ('NULL-MOD', 'Ag'), ('NULL-MOD', 'Ng'), ('NULL-MOD', 'Tg'), ('NULL-MOD', 'Vg'), ('NULL-MOD', 'a'), ('NULL-MOD', 'ad'), ('NULL-MOD', 'an'), ('NULL-MOD', 'b'), ('NULL-MOD', 'c'), ('NULL-MOD', 'd'), ('NULL-MOD', 'f'), ('NULL-MOD', 'i'), ('NULL-MOD', 'j'), ('NULL-MOD', 'l'), ('NULL-MOD', 'm'), ('NULL-MOD', 'n'), ('NULL-MOD', 'nr'), ('NULL-MOD', 'ns'), ('NULL-MOD', 'p'), ('NULL-MOD', 'q'), ('NULL-MOD', 'r'), ('NULL-MOD', 's'), ('NULL-MOD', 't'), ('NULL-MOD', 'u'), ('NULL-MOD', 'v'), ('NULL-MOD', 'vd'), ('NULL-MOD', 'vn'), ('NULL-MOD', 'y'), ('NULL-MOD', 'z'), ('Ng',), ('ROOT',), ('ROOT', 'IP'), ('ROOT', 'IP', 'NP-HLP'), ('ROOT', 'IP', 'NP-HLP', 'n'), ('ROOT', 'IP', 'NP-HLP', 'nr'), ('ROOT', 'IP', 'NP-HLP', 'ns'), ('ROOT', 'IP', 'NP-HLP', 'nt'), ('ROOT', 'IP', 'NP-HLP', 'nz'), ('ROOT', 'IP', 'NP-HLP', 'vn'), ('ROOT', 'IP', 'NP-NPRE'), ('ROOT', 'IP', 'VP-HLP'), ('ROOT', 'IP', 'VP-HLP', 'l'), ('ROOT', 'IP', 'VP-PRD'), ('Tg',), ('UNK-OBJ',), ('UNK-SBJ',), ('VP-HLP',), ('VP-HLP', 'a'), ('VP-HLP', 'ad'), ('VP-HLP', 'd'), ('VP-HLP', 'i'), ('VP-HLP', 'l'), ('VP-HLP', 'v'), ('VP-HLP', 'vn'), ('VP-OBJ',), ('VP-OBJ', 'Ag'), ('VP-OBJ', 'VP-PRD'), ('VP-OBJ', 'a'), ('VP-OBJ', 'ad'), ('VP-OBJ', 'an'), ('VP-OBJ', 'b'), ('VP-OBJ', 'd'), ('VP-OBJ', 'i'), ('VP-OBJ', 'j'), ('VP-OBJ', 'l'), ('VP-OBJ', 'n'), ('VP-OBJ', 'p'), ('VP-OBJ', 'r'), ('VP-OBJ', 'v'), ('VP-OBJ', 'vn'), ('VP-OBJ', 'z'), ('VP-PRD',), ('VP-PRD', 'Ag'), ('VP-PRD', 'Dg'), ('VP-PRD', 'Ng'), ('VP-PRD', 'Tg'), ('VP-PRD', 'VP-PRD'), ('VP-PRD', 'Vg'), ('VP-PRD', 'a'), ('VP-PRD', 'ad'), ('VP-PRD', 'an'), ('VP-PRD', 'b'), ('VP-PRD', 'c'), ('VP-PRD', 'd'), ('VP-PRD', 'f'), ('VP-PRD', 'h'), ('VP-PRD', 'i'), ('VP-PRD', 'j'), ('VP-PRD', 'k'), ('VP-PRD', 'l'), ('VP-PRD', 'm'), ('VP-PRD', 'n'), ('VP-PRD', 'nr'), ('VP-PRD', 'ns'), ('VP-PRD', 'nx'), ('VP-PRD', 'nz'), ('VP-PRD', 'p'), ('VP-PRD', 'q'), ('VP-PRD', 'r'), ('VP-PRD', 't'), ('VP-PRD', 'u'), ('VP-PRD', 'v'), ('VP-PRD', 'vd'), ('VP-PRD', 'vn'), ('VP-PRD', 'z'), ('VP-SBJ',), ('VP-SBJ', 'VP-PRD'), ('VP-SBJ', 'a'), ('VP-SBJ', 'ad'), ('VP-SBJ', 'an'), ('VP-SBJ', 'd'), ('VP-SBJ', 'i'), ('VP-SBJ', 'l'), ('VP-SBJ', 'm'), ('VP-SBJ', 'n'), ('VP-SBJ', 'ns'), ('VP-SBJ', 'r'), ('VP-SBJ', 'v'), ('VP-SBJ', 'vn'), ('Vg',), ('a',), ('ad',), ('an',), ('b',), ('c',), ('d',), ('e',), ('f',), ('h',), ('i',), ('j',), ('k',), ('l',), ('m',), ('n',), ('nr',), ('ns',), ('nt',), ('nx',), ('nz',), ('o',), ('p',), ('q',), ('r',), ('s',), ('t',), ('u',), ('v',), ('vd',), ('vn',), ('w',), ('w', 'w'), ('w-CON', 'w'), ('y',), ('z',)]
    label_set = set()
    tag_set = set()
    for labels in tmp:
        labels = str(labels).replace('(', '').replace(')', '').split(',')
        for i in labels:
            label_set.add(i.replace("'","").replace(' ',''))
    for labels in tmp1:
        labels = str(labels).replace('(', '').replace(')', '').split(',')
        for i in labels:
            tag_set.add(i.replace("'","").replace(' ',''))
    print(tag_set - label_set)
def get_labels_nums(path, o):
    train_treebank = trees.load_trees(path)
    train_parse = [tree.convert() for tree in train_treebank]
    labels2num = init_dict()
    for tree in train_parse:
        nodes = [tree]
        while nodes:
            node = nodes.pop()
            if isinstance(node, trees.InternalParseNode):
                # label = node.label[-1]
                for label in node.label:
                    if label in labels:
                        labels2num[label] += 1
                nodes.extend(reversed(node.children))
    out_array = []
    for k, v in labels2num.items():
        out_array.append([k,v])
    dataframe = pd.DataFrame(out_array, columns=['labels', 'number'])
    dataframe.to_csv(o, float_format='%.4f', encoding='utf8')



if __name__=='__main__':
    par = argparse.ArgumentParser()
    par.add_argument('--g', help='gold path', default='../../data/dev.small')
    par.add_argument('--p', help='predict path',default='../../data/dev.small')
    par.add_argument('--o', help='output path', default='../../out.csv')
    par.add_argument('--o1', help='output path', default='../../out1.csv')
    par.add_argument('--i', help='input path', default='../../data/dev.small')
    args = par.parse_args()
    # get_labels()
    # get_labels_nums(args.i, args.o)

    F1, input_all, micro_p, micro_r, micro_f, all_input, tF1, tinput_all, tmicro_p, tmicro_r, tmicro_f, tall_input = ComputeF1(args.g, args.p)
    out_array = list()
    for i in range(len(labels)):
        tmp_arr = [labels[i], F1[i][0], F1[i][1], F1[i][2], input_all[labels[i]]]
        # print('{}:{}个 p:{:.3f} r:{:.3f} f:{:.3f}'.format(labels[i],input_all[labels[i]], F1[i][0], F1[i][1], F1[i][2]))
        out_array.append(tmp_arr)

    out_array.append(['micro', micro_p, micro_r, micro_f, all_input])
    dataframe = pd.DataFrame(out_array, columns = ['labels', 'Precision', 'Recall','F1', 'Num'])
    dataframe.to_csv(args.o, float_format = '%.4f', encoding='utf8')
    out_array1 = list()
    # for i in range(len(tags38)):
    #     tmp_arr = [tags38[i], tF1[i][0], tF1[i][1], tF1[i][2], tinput_all[tags38[i]]]
        # print('{}:{}个 p:{:.3f} r:{:.3f} f:{:.3f}'.format(labels[i],input_all[labels[i]], F1[i][0], F1[i][1], F1[i][2]))
        # out_array1.append(tmp_arr)

    # out_array1.append(['micro', tmicro_p, tmicro_r, tmicro_f, tall_input])
    # dataframe1 = pd.DataFrame(out_array1, columns=['tags', 'Precision', 'Recall', 'F1', 'Num'])
    # dataframe1.to_csv(args.o1, float_format='%.4f', encoding='utf8')


