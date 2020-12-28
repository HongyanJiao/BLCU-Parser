import argparse
import trees
import pandas as pd
labels = ['ROOT', 'IP', 'NULL-HLP', 'VP-HLP',  'NP-HLP', 'VP-OBJ', 'UNK-OBJ',
          'NP-NPRE', 'NP-SBJ', 'VP-PRD', 'VP-SBJ', 'NP-OBJ',
          'NULL-CON', 'UNK-SBJ', 'NULL-MOD', 'NULL-AUX',  'w-CON']
# print('label数量：', len(labels))
def init_dict():
    return {label:0 for label in labels}
class ChunkStruct(object):
    def __init__(self, label, left, right):
        self.label = label
        self.left = left
        self.right = right
def Tree2DataStruct(train_treebank):
    train_parse = [tree.convert() for tree in train_treebank]
    all_structs = [] # for the whole file
    for tree in train_parse:
        nodes = [tree]
        one_tree_struct = []
        while nodes:
            node = nodes.pop()
            if isinstance(node, trees.InternalParseNode):
                # label = node.label[-1]
                for label in node.label:
                    if label in labels:
                        one_tree_struct.append(ChunkStruct(label, node.left, node.right))
                nodes.extend(reversed(node.children))
        all_structs.append(one_tree_struct)
    return all_structs


def ReadTrees(path):
    train_treebank = trees.load_trees(path)
    all_structs = Tree2DataStruct(train_treebank)
    print('load:{} lines in file:{}'.format(len(all_structs), path))
    # for one_tree_struct in all_structs:
    #     print(len(one_tree_struct), end=',')
    # print()
    return all_structs
def Cmp(one_gold_struct, one_pred_struct):
    model_right_one_tree = init_dict()
    for g in one_gold_struct:
        for p in one_pred_struct:
            if p.label == g.label and p.left == g.left and p.right == g.right:
                model_right_one_tree[p.label] += 1
    return model_right_one_tree

def Count(g_struct, p_struct):
    input_all = init_dict()
    model_all = init_dict()
    model_right = init_dict()

    for one_gold_struct, one_pred_struct in zip(g_struct,p_struct):
        for gold in one_gold_struct:
            input_all[gold.label] += int(1)
        for pred in one_pred_struct:
            model_all[pred.label] += 1
        model_right_one_tree = Cmp(one_gold_struct, one_pred_struct)
        for label, freq in model_right_one_tree.items():
            model_right[label] += freq
    return  model_all, input_all, model_right


def ComputeF1(gold_path, predict_path):
    all_model_right = 0
    all_model_all = 0
    all_input_all = 0

    g_struct = ReadTrees(gold_path)
    p_struct = ReadTrees(predict_path)
    assert len(g_struct) == len(p_struct), f'{g_struct},{p_struct}'
    model_all, input_all, model_right = Count(g_struct, p_struct)
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
    micro_p = all_model_right / all_model_all
    micro_r = all_model_right / all_input_all
    micro_f = (2 * micro_p * micro_r) / (micro_p + micro_r)
    return F1, input_all, micro_p, micro_r, micro_f, all_input_all
def get_labels():
    tmp = [('IP',), ('IP', 'NP-HLP'), ('IP', 'NP-NPRE'), ('IP', 'VP-HLP'), ('IP', 'VP-PRD'), ('IP', 'w'),
           ('NP-HLP',), ('NP-NPRE',), ('NP-OBJ',), ('NP-SBJ',), ('NULL-AUX',), ('NULL-CON',), ('NULL-HLP',),
           ('NULL-MOD',), ('ROOT',), ('ROOT', 'IP'), ('ROOT', 'IP', 'NP-HLP'), ('ROOT', 'IP', 'NP-NPRE'),
           ('ROOT', 'IP', 'VP-HLP'), ('ROOT', 'IP', 'VP-PRD'), ('UNK-OBJ',), ('UNK-SBJ',), ('VP-HLP',), ('VP-OBJ',),
           ('VP-OBJ', 'VP-PRD'), ('VP-PRD',), ('VP-PRD', 'VP-PRD'), ('VP-SBJ',), ('VP-SBJ', 'VP-PRD'), ('w',),
           ('w-CON',)]
    label_set = set()
    for labels in tmp:
        labels = str(labels).replace('(', '').replace(')', '').split(',')
        for i in labels:
            label_set.add(i.replace("'","").replace(' ',''))
    print(label_set)
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
    par.add_argument('--i', help='input path', default='../../data/dev.small')
    args = par.parse_args()
    # get_labels()
    # get_labels_nums(args.i, args.o)
    F1, input_all, micro_p, micro_r, micro_f, all_input = ComputeF1(args.g, args.p)
    out_array = list()
    for i in range(len(labels)):
        tmp_arr = [labels[i], F1[i][0], F1[i][1], F1[i][2], input_all[labels[i]]]
        # print('{}:{}个 p:{:.3f} r:{:.3f} f:{:.3f}'.format(labels[i],input_all[labels[i]], F1[i][0], F1[i][1], F1[i][2]))
        out_array.append(tmp_arr)

    out_array.append(['micro', micro_p, micro_r, micro_f, all_input])
    dataframe = pd.DataFrame(out_array, columns = ['labels', 'Precision', 'Recall','F1', 'Num'])
    dataframe.to_csv(args.o, float_format = '%.4f', encoding='utf8')


