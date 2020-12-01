from nltk import Tree
import codecs

the_other_labels = ['NULL-CON', 'NULL-AUX', 'NULL-MOD', 'w']
other_labels = ['NULL-MOD', 'w']
and_words = ('、', '和', '或', '且', '及', '以及', '，', '跟', '与')


def traverse(t):
    ret = str(t)
    ret = ret.replace('\n', '')
    ret = ret.replace('  ', ' ')
    return ret


def combine_nodes(tree, num1, num2, label):
    # 合并tree下num1到num2的节点，[num1,num2]的全闭区间
    ret = ''
    # tree = Tree.fromstring('(IP (NP 杭州市萧山区的金马饭店，) (VP-PRD (NULL-MOD 对入住客人)(VP-PRD 进行)) (NP “文明用餐、拒绝剩宴”的提醒) (w 。))')
    if num2 < 0:
        num2 = len(tree) + num2
    if num1 < 0:
        num1 = len(tree) + num1
    for i in range(num1, num2 + 1):
        ret = ret + traverse(tree[i])
    ret = '(' + label + ' ' + ret + ')'
    ret = Tree.fromstring(ret)
    tree.__setitem__(num1, ret)
    for i in range(num1, num2):
        tree.__delitem__(num1 + 1)


def convert_1(node):
    label = node._label
    if label != 'IP' and label.find('UNK') < 0:
        label = 'VP-PRD'
    if len(node) > 2:
        if node[-1]._label.find('AUX') >= 0 or node[-1]._label.find('CON') >= 0 or node[-1]._label.find('w') >= 0 or \
                node[-1]._label.find('x') >= 0:
            combine_nodes(node, 0, -2, label+'-TMP')
            convert_1(node[0])
        elif node[0]._label.find('MOD') >= 0 or node[0]._label.find('AUX') >= 0 or node[0]._label.find('CON') >= 0 or \
                node[0]._label.find('w') >= 0 or node[0]._label.find('x') >= 0:
            combine_nodes(node, 1, -1, label+'-TMP')
            convert_1(node[-1])


def has_PRDother(tree):
    idx = 0
    id1 = 0
    id2 = 0
    last_child = ''
    for child in tree:
        if child._label.find('VP-PRD') >= 0  and (last_child == 'NULL-MOD' or last_child.find('w') >= 0 or last_child.find(
                'x') >= 0) and last_child != 'w-CON':
            id1 = idx - 1
            id2 = idx
            break
        elif last_child.find('VP-PRD') >= 0 and (child._label == 'NULL-AUX' or child._label == 'NULL-MOD' or child._label.find(
                'w') >= 0 or child._label.find('x') >= 0) and child._label != 'w-CON':
            id1 = idx - 1
            id2 = idx
            break
        idx = idx + 1
        last_child = child._label
    return id1, id2


def recursive_convert_1(tree):
    for child in tree:
        if isinstance(child, Tree):
            if len(child) > 2:
                convert_1(child)
            if child._label.find('VP') >= 0 or child._label.find('IP') >= 0 or child._label == 'UNK' >= 0:
                if child._label.find('VP-PRD') < 0 or str(child).find('SBJ') >= 0 or str(child).find('OBJ') >= 0:
                    recursive_convert_1(child)


def convert_2(tree):
    num1, num2 = has_PRDother(tree)
    if len(tree) > 2:
        if num1 or num2:
            combine_nodes(tree, num1, num2, 'VP-PRD-TMP')
            convert_2(tree)


def recursive_convert_2(tree):
    for child in tree:
        if isinstance(child, Tree):
            if len(child) > 2:
                convert_2(child)
            if child._label.find('VP') >= 0 or child._label.find('IP') >= 0 or child._label.find('UNK') >= 0:
                # if child._label.find('VP-PRD') < 0 or str(child).find('SBJ') >= 0 or str(child).find('OBJ') >= 0:
                recursive_convert_2(child)


def has_PRDOBJ(tree):
    idx = 0
    id1 = -1
    id2 = -1
    last_child = ''
    for child in tree:
        if child._label.find('OBJ') >= 0:
            id2 = idx
            for i in range(0, idx):
                if tree[i]._label.find('VP-PRD') >= 0:
                    id1 = i
                if tree[i]._label == 'w-CON' or tree[i][0] in and_words:
                    id1 = -1
            if id1 == -1:
                idx = idx + 1
                continue
            else:
                idx = idx + 1
                break
        idx = idx + 1
    return id1, id2


def convert_3(tree):
    num1, num2 = has_PRDOBJ(tree)
    if len(tree) > 2:
        if num1 != -1 and num2 != -1:
            if num1 != 0 or num2 != len(tree) - 1:
                combine_nodes(tree, num1, num2, 'VP-PRD-TMP')
                convert_3(tree)


def recursive_convert_3(tree):
    for child in tree:
        if isinstance(child, Tree):
            if len(child) > 2:
                convert_3(child)
            if child._label.find('VP') >= 0 or child._label.find('IP') >= 0 or child._label.find('UNK') >= 0:
                if child._label.find('VP-PRD') < 0 or str(child).find('OBJ') >= 0:
                    recursive_convert_3(child)


def has_PRDPRD(tree):
    idx = 0
    id1 = 0
    id2 = 0
    last_child = ''
    for child in tree:
        if last_child.find('VP-PRD') >= 0 and child._label.find('VP-PRD') >= 0:
            id1 = idx - 1
            id2 = idx

        idx = idx + 1
        last_child = child._label
    return id1, id2


def convert_4(tree):
    num1, num2 = has_PRDPRD(tree)
    if len(tree) > 2:
        if num1 or num2:
            combine_nodes(tree, num1, num2, 'VP-PRD-TMP')
            convert_4(tree)


def normal_lianhe(tree):
    sig = 0
    for child in tree:
        if child._label.find('CON') >= 0 and child[0] in and_words:
            sig = 1
        if child._label.find('SBJ') >= 0 and sig == 1:
            return False
    return True


def recursive_convert_4(tree):
    for child in tree:
        if isinstance(child, Tree):
            if len(child) > 2:
                if normal_lianhe(child):
                    convert_4(child)
            if child._label.find('VP') >= 0 or child._label.find('IP') >= 0 or child._label.find('UNK') >= 0:
                if child._label.find('VP-PRD') < 0 or str(child).find('SBJ') >= 0 or str(child).find('OBJ') >= 0:
                    recursive_convert_4(child)


def convert_lianhe(tree):
    nums = [-1]
    idx = 0
    label = tree._label
    if label.find('UNK') < 0:
        label = 'VP-PRD'
    else:
        label = label.replace('UNK', 'NP')
    if normal_lianhe(tree):
        tag = False
    else:
        tag = True
    for child in tree:
        if child._label.find('CON') >= 0:
            nums.append(idx)
        idx = idx + 1
    nums.append(idx)
    nums.reverse()
    last_label = ''
    for i in range(1, len(nums) - 1):
        tmp = tree[nums[i]]._label
        if tree[nums[i]]._label == 'w-CON':
            num1 = nums[i + 1] + 1
            num2 = nums[i]
            if i == 1 and nums[0] - nums[1] > 2 and tag:
                for j in range(nums[1] + 1, nums[0]):
                    if tree[j]._label.find('VP') >= 0:
                        label = label.replace('NP', 'VP')
                        break
                combine_nodes(tree, nums[1] + 1, nums[0] - 1, label+'-TMP')
            for j in range(num1, num2 + 1):
                if tree[j]._label.find('VP') >= 0:
                    label = label.replace('NP', 'VP')
                    break
            combine_nodes(tree, num1, num2, label+'-TMP')
        else:
            num1 = nums[i]
            num2 = nums[i - 1] - 1
            for j in range(num1, num2 + 1):
                if tree[j]._label.find('VP') >= 0:
                    label = label.replace('NP', 'VP')
                    break
            if last_label == 'w-CON':
                combine_nodes(tree, num1, num1 + 1, label+'-TMP')
            else:
                combine_nodes(tree, num1, num2, label+'-TMP')
            if i == len(nums) - 2 and nums[-2] > 1 and tag:
                for j in range(0, nums[-2]):
                    if tree[j]._label.find('VP') >= 0:
                        label = label.replace('NP', 'VP')
                        break
                combine_nodes(tree, 0, nums[-2] - 1, label+'-TMP')
        last_label = tmp
    recursive_convert_1(tree)


def is_lianhe(node):
    is_true = False
    for child_node in node:
        if child_node[0] in and_words and child_node._label.find('CON') >= 0:
            is_true = True
            break
    return is_true


def recursive_convert_lianhe(tree):
    # 特殊：异构联合
    # 习近平总书记代表中央政治局作的工作报告\\，(实事求是) <、 > 内涵(丰富) <、 > (催)人(奋进)。
    # 习近平总书记就《建议》稿作的说明{，思想(深刻) <、 > 论述(精辟) <、 > 重点(突出)}。
    # 这种测验(包括){枯季和冰期的流量测验 <， > 汛期跟踪洪水的测验 <， > [定期]水质(取样) << 等 >>}。
    #  (从交易方式的角度可(分为)){函电 <、 > (拍卖) <、 > (投标) <、 > (招标) <、 > 交易所(成交) <、 > (展卖) << 等 >>}；
    for child in tree:
        if isinstance(child, Tree):
            if len(child) > 2:
                if is_lianhe(child):
                    convert_lianhe(child)
                    continue
            if child._label.find('VP') >= 0 or child._label.find('IP') >= 0 or child._label.find('UNK') >= 0:
                if child._label.find('VP-PRD') < 0 or str(child).find('SBJ') >= 0 or str(child).find('OBJ') >= 0:
                    recursive_convert_lianhe(child)


def has_CONPRD(tree):
    idx = 0
    id1 = 0
    id2 = 0
    last_child = ''
    for child in tree:
        if (last_child == 'NULL-CON' or last_child == 'NULL-AUX' or last_child == 'NULL-MOD') and child._label.find('VP-PRD') >= 0:
            id1 = idx - 1
            id2 = idx
            break
        idx = idx + 1
        last_child = child._label
    return id1, id2


def convert_5(tree):
    num1, num2 = has_CONPRD(tree)
    if len(tree) > 2:
        if num1 or num2:
            combine_nodes(tree, num1, num2, 'VP-PRD-TMP')
            convert_5(tree)


def recursive_convert_5(tree):
    for child in tree:
        if isinstance(child, Tree):
            if len(child) > 2:
                convert_5(child)
            if child._label.find('VP') >= 0 or child._label.find('IP') >= 0 or child._label.find('UNK') >= 0:
                if child._label.find('VP-PRD') < 0 or str(child).find('SBJ') >= 0 or str(child).find('OBJ') >= 0:
                    recursive_convert_5(child)


def convert_6(tree):
    length = len(tree) - 2
    label = tree._label
    for i in range(0, length):
        if tree[-2]._label.find('VP') >= 0 and tree[-1]._label.find('VP') >= 0:
            label = label.replace('UNK', 'VP')
        elif tree[-2]._label.find('NP') >= 0 and tree[-1]._label.find('NP') >= 0:
            label = label.replace('UNK', 'NP')
        combine_nodes(tree, -2, -1, label+'-TMP')


def recursive_convert_6(tree):
    for child in tree:
        if isinstance(child, Tree):
            if len(child) > 2 and child._label.find('UNK') >= 0:
                convert_6(child)
            if child._label.find('VP') >= 0 or child._label.find('IP') >= 0 or child._label.find('UNK') >= 0:
                if child._label.find('VP-PRD') < 0 or str(child).find('SBJ') >= 0 or str(child).find('OBJ') >= 0:
                    recursive_convert_6(child)


def check_bi(tree):
    ret = True
    for child in tree:
        if len(child) > 2:
            ret = False
            break
        elif len(child) == 2:
            ret = check_bi(child)
    return ret


def has_CONOBJ(tree):
    idx = 0
    id1 = 0
    id2 = 0
    last_child = ''
    for child in tree:
        if last_child == 'NULL-CON' and child._label == 'VP-OBJ':
            id1 = idx - 1
            id2 = idx
            break
        idx = idx + 1
        last_child = child._label
    return id1, id2


def convert_7(tree):
    num1, num2 = has_CONOBJ(tree)
    if len(tree) > 2:
        if num1 or num2:
            combine_nodes(tree, num1, num2, 'VP-OBJ-TMP')
            convert_7(tree)


def recursive_convert_7(tree):
    for child in tree:
        if isinstance(child, Tree):
            if len(child) > 2:
                convert_7(child)
            if child._label.find('VP') >= 0 or child._label.find('IP') >= 0 or child._label.find('UNK') >= 0:
                if child._label.find('VP-PRD') < 0 or str(child).find('SBJ') >= 0 or str(child).find('OBJ') >= 0:
                    recursive_convert_7(child)


def only_has_IP_child(tree):
    for child in tree:
        if isinstance(child, Tree):
            if child._label != 'IP':
                return False
        else:
            return False
    return True


def recursive_convert_8(tree):
    if len(tree) > 2 and only_has_IP_child(tree):
        combine_nodes(tree, 1, -1, 'IP-TMP')
        recursive_convert_8(tree[1])

def convert(tree):
    for child in tree:
        if isinstance(child, Tree):
            if len(child) > 2:
                combine_nodes(child, 1, -1, 'TMP')
            convert(child)


def entry_multi2bi(line):
    tree = Tree.fromstring(line)
    # 对于Root下的每个IP进行操作

    # AUX/MOD/w/CON+IP/VP-PRD+AUX/w/CON
    recursive_convert_1(tree)

    # MOD/w+PRD+AUX/MOD/w=PRD
    recursive_convert_2(tree)

    # 合并PRD+X+OBJ
    recursive_convert_3(tree)

    # 特殊：按是否有<， >判断，可得三种情况：1. 换主语联合；2. 异构联合；3. 普通联合。1和2有交叉，如第三例。
    # 习近平总书记代表中央政治局作的工作报告\\，(实事求是) <、 > 内涵(丰富) <、 > (催)人(奋进)。
    # 习近平总书记就《建议》稿作的说明{，思想(深刻) <、 > 论述(精辟) <、 > 重点(突出)}。
    # 这种测验(包括){枯季和冰期的流量测验 <， > 汛期跟踪洪水的测验 <， > [定期]水质(取样) << 等 >>}。
    # (从交易方式的角度可(分为)){函电 <、 > (拍卖) <、 > (投标) <、 > (招标) <、 > 交易所(成交) <、 > (展卖) << 等 >>}；
    recursive_convert_lianhe(tree)

    # 合并普通复谓结构的PRD+PRD
    recursive_convert_4(tree)

    # 合并CON/AUX+PRD
    recursive_convert_5(tree)

    # MOD/w+PRD+AUX/MOD/w=PRD
    recursive_convert_2(tree)

    # 合并普通复谓结构的PRD+PRD
    recursive_convert_4(tree)

    # 异构合并
    recursive_convert_6(tree)

    # CON+VP-OBJ
    recursive_convert_7(tree)

    # IP+IP=IP
    recursive_convert_8(tree)
    # tree.draw()

    #底层二叉化的代码：输入：nltk的tree，输出：新的tree
    # convert(tree)

    ret = check_bi(tree)

    if not ret:
        return '## wrong in line' + line + '!!\n' + traverse(tree) + '\n'
    else:
        return traverse(tree)


def read_multi_tree(fin_path, f_out, f_wrong):
    fin = codecs.open(fin_path, 'r', encoding='utf-8', errors='ignore')
    line_no = 0
    for line in fin:
        if line.find('ROOT') >= 0:
            print(line)
            bi_tree = entry_multi2bi(line)
            line_no += 1
            # f_out.write(line + '\n')

            if bi_tree.find('## wrong in line') >= 0:
                f_wrong.write(bi_tree + '\n')
            else:
                f_out.write(bi_tree + '\n')


def main():
    inp_file = './test.txt'
    outfile = './test.out'
    wrongout = './wrong.out'
    f_out = codecs.open(outfile, 'w', encoding='utf-8', errors='ignore')
    f_wrong = codecs.open(wrongout, 'w', encoding='utf-8', errors='ignore')
    read_multi_tree(inp_file, f_out, f_wrong)


if __name__ == '__main__':
    main()