# !/usr/bin/env python
# -*- coding: UTF-8 -*-
# 逗号、句号、分号、叹号、问号、冒号、破折号、省略号8个标点符号为确定单句边界的标句点号。
# << >> \/ || # ** ** ^*

import codecs
import re
import copy
import collections.abc
from nltk import Tree
import json
import preprocess_data.multi2bi as multi2bi

# 8个标句点号:句号、省略号、问号、叹号、分号、冒号、逗号、连接号
biaoju_puncs = ('。', '-', '？', '！', '；', '：', '，', '~', '…', '－', '．')

# 存储左括号和右括号
open_brackets = '([{<$^'
close_brackets = ')]}>&*'
# 映射左右括号便于出栈判断
brackets_map = {')': '(', ']': '[', '}': '{', '>': '<', '*': '^', '&': '$'}
# 所有的标注符号
original_anno_symbols = ('(', '[', '{', '<', ')', ']', '}', '>', '|', '*', '\\')
all_anno_symbols = ('(', '[', '{', '<', ')', ']', '}', '>', '^', '*', '$', '&', '|', '#')
# 占两个字节的符号用单符号替换的预处理：
# a.    <<  >> 换做一个字节的半角 $ 和&；
# b.    ||  换为 半角#
# c.    错误符 ** 和**替换为^和*

# 所有成对的已替换的标注符号
coupled_anno_symbols = '([{<)]}>^*$&'
punc_set = (
'，', '：', '、', '“', '”', '－', '）', '（', '？', '、', '。', '·', 'ˉ', 'ˇ', '¨', '〃', '々', '—', '～', '‖', '…', '‘', '’', '“',
'”', '〔', '〕', '〈', '〉', '《', '》', '「', '」', '『', '』', '〖', '〗', '【', '】', '±', '×', '÷', '∶', '∧', '∨', '∑', '∏', '∪',
'∩', '∈', '∷', '√', '⊥', '∥', '∠', '⌒', '⊙', '∫', '∮', '≡', '≌', '≈', '∽', '∝', '≠', '≮', '≯', '≤', '≥', '∞', '∵', '∴',
'♂', '♀', '°', '′', '″', '℃', '＄', '¤', '￠', '￡', '‰', '§', '№', '☆', '★', '○', '●', '◎', '◇', '◆', '□', '■', '△', '▲',
'※', '→', '←', '↑', '↓', '〓', '！', '＂', '＃', '￥', '％', '＆', '＇', '（', '）', '＊', '＋', '，', '－', '．', '／', '：', '；', '＜',
'＝', '＞', '？', '＠', '［', '＼', '］', '＾', '＿', '｀', '｛', '｜', '｝', '￣', '', '', '', '', '', '', '', '︵', '︶', '︹',
'︺', '︿', '﹀', '︽', '︾', '﹁', '﹂', '﹃', '﹄', '', '', '︻', '︼', '︷', '︸', '︱', '', '︳', '︴')  # 待完善???????


def _is_chinese_char(text):
    chinese = 0
    non_chinese = 0
    for char in text:
        cp = ord(char)
        if ((cp >= 0x4E00 and cp <= 0x9FFF) or  #
                (cp >= 0x3400 and cp <= 0x4DBF) or (cp >= 0x20000 and cp <= 0x2A6DF) or  #
                (cp >= 0x2A700 and cp <= 0x2B73F) or (cp >= 0x2B740 and cp <= 0x2B81F) or  #
                (cp >= 0x2B820 and cp <= 0x2CEAF) or (cp >= 0xF900 and cp <= 0xFAFF) or  #
                (cp >= 0x2F800 and cp <= 0x2FA1F)):
            # print('中文: ',end='')
            # print(cp)
            chinese = 1
        else:
            non_chinese = 1
    return chinese, non_chinese


def ConEnd(matched):
    IP = str(matched.group())
    if IsChineseword(IP):
        IP = str(matched.group()).replace('(', '').replace(')', '').replace('w', '').replace(' ', '')
        IPList = list(IP)
        IPList[0] = '(w ' + IPList[0]
        IPList[len(IP) - 1] = IPList[len(IP) - 1] + ')'
        IP = ''.join(IPList)
        return IP
    else:
        return IP


def ContEndAddLabel1(IP):
    searchObj = re.search(r'\(w \(w (.)*\)\)', IP)
    if searchObj:
        IP = re.sub(r'\(w \(w (.)*\)\)', ConEnd, IP)
    return IP


def IsChineseword(str1):  # 判断是否是汉字
    Chineseword = re.compile(u'[\u4e00-\u9fa5]')  # 检查汉字

    match = Chineseword.search(str1)
    if match:
        return False
    else:
        return True


def SingleDash(CorpusLine):
    str1 = '(w －)%%'
    pos = CorpusLine.find(str1, 0, len(CorpusLine))
    substr1 = CorpusLine[0:pos]
    substr2 = CorpusLine[pos + 7:]
    if (str1 not in substr1) and (str1 not in substr2):
        CorpusLine = CorpusLine.replace(str1, '－')
    return CorpusLine


def ConRR(matched):
    IP = str(matched.group())
    chinese, nonchinese = _is_chinese_char(IP)
    if nonchinese == 1:
        return IP
    elif chinese == 1:
        return str(matched.group()).replace('%%', '')


def ConR(CorpusLine):  # <>前后有标句点号,整个<>部分右归
    if re.search('%<(.)*>\(w .\)%%', CorpusLine):
        CorpusLine = re.sub(r'%<(.)*>\(w .\)%%', ConRR, CorpusLine)
    return CorpusLine


def ContEndAddLabel(IP):
    searchObj = re.search(r'\(w .\)\(w .\)(\(w .\))*%%', IP)
    if searchObj:
        start = searchObj.start()
        end = searchObj.end()
        IPList = list(IP)

        IPList[start] = '(w ' + IPList[start]
        IPList[end - 3] = IPList[end - 3] + ')'
        IP = ''.join(IPList)
        if re.search(r'\(w .\)\(w .\)(\(w .\))*%%', IP):
            IP = ContEndAddLabel(IP)
    return IP


def HRLeftReduce(CorpusLine):
    RightTwoByteBrac = ['〕', '”', '＂', '’', '〉', '》', '」', '』', '〗', '】', '）', '］', \
                        '＞', ' ｝', '︶', '︺', '﹀', '︾', '﹂', '﹄', '︼', '︸']
    CorpusLineList = list(CorpusLine)
    for i in range(1, len(CorpusLineList) - 1):
        if CorpusLineList[i - 1] == '%' and CorpusLineList[i] == '%' and CorpusLineList[
            i + 1] in RightTwoByteBrac and i > 3:
            if CorpusLineList[i - 3] != ')':
                CorpusLineList[i - 2] = ''
                CorpusLineList[i - 1] = ''
                CorpusLineList[i] = ''
                CorpusLineList[i + 1] = CorpusLineList[i + 1] + ')%%'
            elif CorpusLineList[i - 3] == ')':
                CorpusLineList[i - 3] = ''
                CorpusLineList[i - 2] = ''
                CorpusLineList[i - 1] = ''
                CorpusLineList[i] = ''
                CorpusLineList[i + 1] = CorpusLineList[i + 1] + '))%%'
    CorpusLine = ''.join(CorpusLineList)

    return CorpusLine


def GBK2UTF8(CorpusLine):
    return CorpusLine.encode('utf-8')


def DashAtStart(matched):
    return str(matched.group()).replace('%\(w －\)\(w －\)%%', '%\(w －－\)')


def DashRightReduce(CorpusLine):
    # 破折号在句首或破折号前有左符号LeftTwoByteBrac
    LeftTwoByteBrac = ['〔', '“', '‘', '〈', '《', '「', '『', '〖', '【', '（', '［', \
                       '＜', '｛', '︵', '︹', '︿', '︽', '﹁', '﹃', '︻', '︷']
    if re.match('\(w －\)\(w －\)%%', CorpusLine):  # 句首,前面空格或没东西
        CorpusLineList = list(CorpusLine)
        CorpusLineList[4] = ''
        CorpusLineList[5] = ''
        CorpusLineList[6] = ''
        CorpusLineList[7] = ''
        CorpusLine = ''.join(CorpusLineList)
    if re.search('%\(w －\)\(w －\)%%', CorpusLine):  # 句首,前面有标句点号
        CorpusLine = re.sub(r'%\(w －\)\(w －\)%%', DashAtStart, CorpusLine)

    pos = CorpusLine.find('(\s)?(w －)(w －)', 10, len(CorpusLine))
    CorpusLineList = list(CorpusLine)
    if CorpusLineList[pos - 1] in LeftTwoByteBrac:
        CorpusLineList[pos - 1] = '%%' + CorpusLineList[pos - 1]
    CorpusLine = ''.join(CorpusLineList)
    return CorpusLine


# 连续标句点号ContinuousEndPunc(ContinuousEnd)
def ContinuousEnd(matched):
    return str(matched.group()).replace(')%%(w', ')(w')


def ContinuousEndPunc(CorpusLine):
    Line1 = re.sub(r'(\s)?\(w .\)%%\(w .\)', ContinuousEnd, CorpusLine)
    if re.findall(r'(\s)?\(w .\)%%\(w .\)', Line1):  # 连续超过两个标句点号,递归处理
        Line1 = ContinuousEndPunc(Line1)

    return Line1


def LeftReduce(SingleIP):
    AllPunc = '([{<$^)]}>&*|#'
    open_brackets = '([{<$^'
    punc_end = ['，', '。', '；', '！', '？', '：', '…', '－', '．']

    SIPList = list(SingleIP)
    for j in range(0, len(SIPList) - 1):
        if (SIPList[j] in open_brackets) and (SIPList[j + 1] in punc_end):
            if j == 0:
                break
            else:
                # print('LeftReduce'+SIPList[j]+SIPList[j+1])
                for k in range(j, -1, -1):
                    if (SIPList[k] not in AllPunc) and k == j:
                        break
                    elif (SIPList[k] in AllPunc) and (SIPList[k - 1] not in AllPunc):
                        SIPList[k - 1] = SIPList[k - 1] + SIPList[j + 1]
                        # print('here'+SIPList[k-1])
                        SIPList[j + 1] = ""
                        break
        SingleIP = ''.join(SIPList)
        SingleIP = SingleIP.replace('，<>', '<，>')
    return SingleIP


def is_need_add(node):
    is_need = False
    if type(node[0]) != str:
        for child_node in node:
            if child_node._label == 'NP' or child_node._label == 'VP':
                is_need = True
                break
    return is_need


def is_lianhe(node):
    # 判断该节点的子节点序列是否是联合结构
    is_true = False
    idx = 0
    con_id = -1
    for child_node in node:
        if child_node[0] in and_words and (child_node._label == 'NULL-CON' or child_node._label == 'w-CON'):
            is_true = True
            con_id = idx
        idx += 1
    if con_id == 0:
        is_true = False
    return is_true


and_words = ('、', '和', '或', '且', '及', '以及', '，', '跟', '与')


def is_fenju(node):
    is_true = True
    if type(node[0]) != str:
        for child in node:
            if child._label != 'label':
                is_true = False
                break
    else:
        is_true = False
    return is_true


def is_all_punc(node):
    is_true = True
    if type(node) == str:
        chars = list(node)
    else:
        chars = list(node[0])
    for char in chars:
        if char not in punc_set:
            is_true = False
            break
    return is_true


# 判断node是否是真正的主谓谓语句，即主语在谓语之前出现
def has_sbj(node):
    for child in node:
        if isinstance(child, Tree):
            if child._label == 'NP' or child._label == 'VP':
                return True
            elif child._label == 'VP-PRD':
                return False
    return False


# 判断node节点下的孩子有没有主谓谓语句，即是否有NP、VP或VP、NP连续出现的情况
def is_zhuwei(node):
    label0 = 'NULL'
    idx = 0
    for child_node in node:
        label1 = child_node._label
        if (label0 == 'NP' and label1 == 'VP') or (label0 == 'VP' and label1 == 'VP'):
            if has_sbj(child_node):
                return idx
        label0 = child_node._label
        idx += 1
    return 0


# def split_w(tree):
#     id = 0
#     for child in tree:
#         if isinstance(child, Tree):
#             if child._label == 'w' and id != len(tree) - 1:
#                 if len(child[0]) >= 2:
#                     child.set_label('x2')
#                 else:
#                     child.set_label('x')
#             split_w(child)
#             id += 1


def add_other_labels(IPNode):
    # IP{str}是初步标记好的括号序列，该函数用于进一步确定NP、VP的功能标签
    # IP：(IP (NP 杭州市萧山区的金马饭店，) (VP-PRD (NULL-MOD 对入住客人)(VP-PRD 进行)) (NP “文明用餐、拒绝剩宴”的提醒) (w 。))
    # tree是element为InternalTreeNode类或的list
    tree = Tree.fromstring(IPNode)

    def recursive_add(node):
        if len(node):
            if is_need_add(node):
                for child_node in node:
                    # 单独标点成块标签处理为w
                    if child_node._label == 'NP' and is_all_punc(child_node):
                        child_node.set_label('w')
                # <，>
                if is_lianhe(node):
                    # 谓词同构、体谓异构、体词功能标签继承
                    idx = 0
                    con_list = [-1]
                    # prd_list = []
                    # con_list.append(int('0'))
                    for child_node in node:
                        if (child_node._label == 'NULL-CON' or child_node._label == 'w-CON') and child_node[0] in and_words:
                            if child_node[0] in punc_set:
                                child_node.set_label('w-CON')
                            con_list.append(idx)
                        # if child_node._label == 'VP-PRD':
                        #     prd_list.append(idx)
                        idx += 1
                    con_list.append(idx)
                    prd_idx = -1

                    for id in range(1, len(con_list)):
                        idx = 0
                        prd_idx = -1
                        for child_node in node:
                            if idx > con_list[id - 1] and idx < con_list[id] and child_node._label == 'VP-PRD':
                                prd_idx = idx
                                break
                            elif idx >= con_list[id]:
                                break
                            idx += 1
                        if prd_idx == -1:
                            # 该块无VP-PRD 1.主谓谓语句 2.整句主语：他<或>(聪明)<或>(努力)。
                            # 3.单独NP，功能标签继承父节点：这种测验(包括){枯季和冰期的流量测验<，>汛期跟踪洪水的测验<，>[定期]水质(取样) <<等>>}。
                            idx = 0
                            subprd_idx = -1
                            for child_node in node:
                                if idx > con_list[id - 1] and idx < con_list[id] and child_node._label == 'VP':
                                    subprd_idx = idx
                                idx += 1

                            if subprd_idx == -1:
                                # 不是主谓谓语句
                                if node._label == 'IP':
                                    # 整句主语
                                    idx = 0
                                    for child_node in node:
                                        if idx > con_list[id - 1] and idx < con_list[id]:
                                            if child_node._label == 'NP':
                                                child_node.set_label('NP-SBJ')
                                        elif idx >= con_list[id]:
                                            break
                                        idx += 1
                                else:
                                    # 异构体词
                                    idx = 0
                                    for child_node in node:
                                        if idx > con_list[id - 1] and idx < con_list[id]:
                                            label = node._label
                                            if label.find('UNK') < 0:
                                                label = label.replace('VP', 'UNK')
                                                node.set_label(label)
                                            label = label.replace('UNK', 'NP')
                                            child_node.set_label(label)
                                        elif idx >= con_list[id]:
                                            break
                                        idx += 1
                            else:
                                # 主谓谓语句
                                node[subprd_idx].set_label('VP-PRD')
                                recursive_add(node)
                        # elif prd_idx == -1:
                        #     idx = 0
                        #     for child_node in node:
                        #         if idx > con_list[id - 1] and idx < con_list[id]:
                        #             if child_node._label == 'NP':
                        #                 child_node.set_label('NP-SBJ')
                        #         elif idx >= con_list[id]:
                        #             break
                        #         idx += 1
                        else:
                            # 联合结构中的谓词性成分
                            idx = 0
                            for child_node in node:
                                if idx > con_list[id - 1] and idx < con_list[id]:
                                    if child_node._label == 'NP' or child_node._label == 'VP':
                                        if idx < prd_idx:
                                            child_node.set_label(child_node._label + '-SBJ')
                                        else:
                                            child_node.set_label(child_node._label + '-OBJ')
                                    if child_node._label == 'VP-SBJ' or child_node._label == 'VP-OBJ' or child_node._label == 'VP-PRD':
                                        recursive_add(child_node)
                                elif idx >= con_list[id]:
                                    break
                                idx += 1

                else:
                    prd_idx = -1
                    idx = 0
                    for child_node in node:
                        if child_node._label == 'VP-PRD':
                            prd_idx = idx
                            break
                        idx += 1
                    if prd_idx == -1:
                        # 主谓谓语句
                        idx = 0
                        for child_node in node:
                            if child_node._label == 'VP':
                                prd_idx = idx
                            idx += 1
                        node[prd_idx].set_label('VP-PRD')
                        recursive_add(node)
                    else:
                        no = is_zhuwei(node)
                        if no != 0:
                            # 兼语主谓谓语句 他(令)这件事{困难(重重)}

                            node[no].set_label('VP-PRD')
                            recursive_add(node)
                        else:
                            # 常规主谓宾结构 # 其他主谓谓语句 谭杰[入伍一年多来]{干劲(足)}、(肯(吃苦))
                            idx = 0
                            tag = 0
                            for child_node in node:
                                if child_node._label == 'NP' or child_node._label == 'VP':
                                    if idx < prd_idx and tag == 0:
                                        child_node.set_label(child_node._label + '-SBJ')
                                        tag = 1
                                    elif idx > prd_idx:
                                        child_node.set_label(child_node._label + '-OBJ')
                                    elif child_node._label == 'VP':
                                        if has_sbj(child_node):
                                            child_node.set_label(child_node._label + '-PRD')
                                        else:
                                            child_node.set_label('Ow')
                                    elif child_node._label == 'NP':
                                        child_node.set_label('wDS')

                                if child_node._label == 'VP-SBJ' or child_node._label == 'VP-OBJ' or child_node._label == 'VP-PRD':
                                    recursive_add(child_node)
                                idx += 1

            # { | }
            elif is_fenju(node):
                for child_node in node:
                    child_node.set_label('VP-PRD')
                    recursive_add(child_node)

    recursive_add(tree)

    # split_w(tree)

    ret = str(tree)
    ret = ret.replace('\n', '')
    ret = ret.replace('  ', ' ')

    if ret.find('(VP-PRD φ)') >= 0:
        pattern = re.compile(r'\(VP-PRD φ\)\s+\(NP-OBJ')
        result = pattern.findall(ret)
        if len(result) > 0:
            for matched in result:
                ret = ret.replace(matched, '(NP-NPRE')
        else:
            ret = '(wS)'
    return ret


def is_HLP(ret):
    if ret.find('NP') >= 0 and ret.find('VP') < 0:
        # 名词独词句
        return True
    if ret.count('VP-PRD') == 1 and ret.find('NP') < 0 and ret.find('NULL') < 0 and ret.count('VP') == 1:
        # 动词独词句
        return True
    if ret.find('NULL-AUX') >= 0 and ret.find('NP') < 0 and ret.find('VP') < 0 and ret.find('CON'):
        # 助语独词句
        return True
    return False


def label_isnot_all_right(root):
    labels = ('ROOT', 'IP', 'VP-HLP', 'NULL-HLP', 'NP-HLP', 'NULL-ERO', 'w', 'VP-SBJ', 'VP-PRD', 'VP-OBJ', 'NP-SBJ',
              'NP-OBJ', 'NULL-MOD', 'NULL-AUX', 'NULL-CON', 'UNK-SBJ', 'UNK-OBJ', 'w-CON', 'NP-NPRE')
    for child in root.children:
        if isinstance(child, InternalTreebankNode):
            if child.label not in labels:
                return True
            else:
                if label_isnot_all_right(child):
                    return True
        elif isinstance(child, LeafTreebankNode) and child.tag not in labels:
            return True
    return False


def SplitIP(lineNo, CorpusLine, fOut, fInPath, f_wrong):
    tmp_dict = {}
    chinese, nonchinese = _is_chinese_char(CorpusLine)
    # (lineNo, CorpusLine) = re.split('###', re.sub(r'^(\d+)\s+', r"\1###", CorpusLine))
    if re.findall(r'\*\*', CorpusLine):  # wrong sent
        tmp_dict = {'fname': fInPath, 'lineNo': lineNo, 'type': "wSent", 'IP': '', 'w_line': CorpusLine}
        f_wrong.write('{}\n'.format(json.dumps(tmp_dict, ensure_ascii=False)))
        return False
    elif len(re.findall(r'^\|', CorpusLine)) > 0:  # wrong seperator
        tmp_dict = {'fname': fInPath, 'lineNo': lineNo, 'type': "wS", 'IP': '', 'w_line': CorpusLine}
        f_wrong.write('{}\n'.format(json.dumps(tmp_dict, ensure_ascii=False)))
        return False
    elif len(re.findall(r'\\\\[\(\[\{<\)\]\}\>\|\*]+', CorpusLine)) > 0:  # wrong comment
        tmp_dict = {'fname': fInPath, 'lineNo': lineNo, 'type': "wC", 'IP': '', 'w_line': CorpusLine}
        f_wrong.write('{}\n'.format(json.dumps(tmp_dict, ensure_ascii=False)))
        return False
    elif CorpusLine.count('【')!=CorpusLine.count('】') or CorpusLine.count('（')!=CorpusLine.count('）') or\
            CorpusLine.count('《')!=CorpusLine.count('》') or CorpusLine.count('｛')!=CorpusLine.count('｝'): #unmatch
        tmp_dict = {'fname': fInPath, 'lineNo': lineNo, 'type': "unmatch", 'IP': '', 'w_line': CorpusLine}
        f_wrong.write('{}\n'.format(json.dumps(tmp_dict, ensure_ascii=False)))
        return False
    elif chinese ==0 and CorpusLine.count('<')==0:  # no chinese
        tmp_dict = {'fname': fInPath, 'lineNo': lineNo, 'type': "nochinese", 'IP': '', 'w_line': CorpusLine}
        f_wrong.write('{}\n'.format(json.dumps(tmp_dict, ensure_ascii=False)))
        return False
    else:
        CorpusLine0 = CorpusLine
        # print(CorpusLine0)
        CorpusLine = Replace(CorpusLine)
        BigBracketStack = []
        da_bracket_open_idxs =[]
        punc_end = ['，', '。', '；', '！', '？', '：', '…', '－', '－']
        # '……', '－－',
        open_brackets = '([{<$\\'
        close_brackets = ')]}>&!'

        CorpusLineList = list(CorpusLine)
        is_ok = True
        da_bracket_idx = ''
        for i in range(0, len(CorpusLineList) - 1):

            if CorpusLineList[i] in punc_end:
                if (CorpusLineList[i - 1] not in open_brackets) and \
                        (CorpusLineList[i + 1] not in close_brackets) and \
                        (CorpusLineList[i - 1] != '\\') and len(BigBracketStack) == 0:
                    CorpusLineList[i] = '(w ' + CorpusLine[i] + ')%%'
            elif CorpusLineList[i] == '{':
                BigBracketStack.append('{')
                da_bracket_open_idxs.append(i)
            elif CorpusLineList[i] == '}':
                if len(BigBracketStack) <= 0 or BigBracketStack[-1] != '{':
                    tmp_dict = {'fname': fInPath, 'lineNo': lineNo, 'type': "NP", 'IP': '',
                                'w_line': CorpusLine0}  # Not Paired
                    f_wrong.write('{}\n'.format(json.dumps(tmp_dict, ensure_ascii=False)))
                    return False
                da_bracket_idx = da_bracket_open_idxs.pop()
                if i+1 < len(CorpusLineList) and CorpusLineList[i+1] in biaoju_puncs:
                    if da_bracket_idx == 0 or (da_bracket_idx-1 > 0 and CorpusLineList[da_bracket_idx-1] in biaoju_puncs and CorpusLineList[da_bracket_idx-2] != '\\'):  # wrong da brackets
                        tmp_dict = {'fname': fInPath, 'lineNo': lineNo, 'type': "wD", 'IP': '', 'w_line': CorpusLine}
                        f_wrong.write('{}\n'.format(json.dumps(tmp_dict, ensure_ascii=False)))
                        return False

                BigBracketStack.pop()
            elif CorpusLineList[i] == '|' and len(BigBracketStack) == 0:
                CorpusLineList[i] = '%%'

        else:
            if CorpusLineList[-1] in punc_end:
                CorpusLineList[-1] = '(w ' + CorpusLine[-1] + ')%%'

            CorpusLine = "".join(CorpusLineList)
            CorpusLine = CorpusLine.replace('－(w －)%%', '－－')
            CorpusLine = CorpusLine.replace('(w －)%%－', '－－')
            CorpusLine = CorpusLine.replace('…(w …)%%', '……')
            CorpusLine = CorpusLine.replace('(w …)%%…', '……')
            CorpusLine = ContinuousEndPunc(CorpusLine)  # 连续标句点号最后一个分句
            CorpusLine = DashRightReduce(CorpusLine)  # 破折号在句首不分IP,破折号前有左符号右归
            CorpusLine = ContEndAddLabel(CorpusLine)  # 连续标句点号放在一个label中
            CorpusLine = HRLeftReduce(CorpusLine)  # 标句点号后有右半符号,右半符号左归 ，”这里的右半左归
            CorpusLine = ConR(CorpusLine)  # <>前后是标句点号,>后第一个标句点号不分句
            CorpusLine = SingleDash(CorpusLine)  # 1-2月，单个的破折号不分句
            IPList = CorpusLine.split('%%')
            IPList1 = []
            for IP in IPList:
                IP = IP.replace('\\\\', '')
                IP = IP.replace('?', '')
                if IP != '':
                    IP = LeftReduce(IP)
                    IP = ContEndAddLabel1(IP)
                    # IP = IP.replace('(w (w －)(w －))','(w －－)')
                    IPList1.append(IP)
            # print(IPList1)
            if len(IPList1):
                retlist = []
                ret_true = True
                for IP in IPList1:
                    IP = IP.strip()
                    if len(IP) <= 0:
                        continue
                    ret = build_tree(IP)
                    if ret.find('(BM ') >= 0:  # Brackets mismatch!
                        tmp_dict = {'fname': fInPath, 'lineNo': lineNo, 'type': "BM", 'IP': ret, 'w_line': CorpusLine0}
                        f_wrong.write('{}\n'.format(json.dumps(tmp_dict, ensure_ascii=False)))
                        ret_true = False
                        break
                    if ret.find('(wP ') >= 0:  # wrong predicate
                        tmp_dict = {'fname': fInPath, 'lineNo': lineNo, 'type': "wP", 'IP': ret, 'w_line': CorpusLine0}
                        f_wrong.write('{}\n'.format(json.dumps(tmp_dict, ensure_ascii=False)))
                        ret_true = False
                        break
                    if ret.find('(wDO ') >= 0:  # wrong double objects
                        tmp_dict = {'fname': fInPath, 'lineNo': lineNo, 'type': "wDO", 'IP': ret, 'w_line': CorpusLine0}
                        f_wrong.write('{}\n'.format(json.dumps(tmp_dict, ensure_ascii=False)))
                        ret_true = False
                        break
                    if ret.find('(wDS ') >= 0:  # wrong double subjects “我们[在部队高度分散的态势下，]各部(分别(展开了))独立自主的游击战斗”
                        tmp_dict = {'fname': fInPath, 'lineNo': lineNo, 'type': "wDO", 'IP': ret, 'w_line': CorpusLine0}
                        f_wrong.write('{}\n'.format(json.dumps(tmp_dict, ensure_ascii=False)))
                        ret_true = False
                        break
                    if ret.find('(Ow ') >= 0:  # other wrong
                        tmp_dict = {'fname': fInPath, 'lineNo': lineNo, 'type': "Ow", 'IP': ret, 'w_line': CorpusLine0}
                        f_wrong.write('{}\n'.format(json.dumps(tmp_dict, ensure_ascii=False)))
                        ret_true = False
                        break
                    if is_HLP(ret):
                        if ret.find('#') >= 0:
                            tmp_dict = {'fname': fInPath, 'lineNo': lineNo, 'type': "wDO", 'IP': ret,
                                        'w_line': CorpusLine0}
                            f_wrong.write('{}\n'.format(json.dumps(tmp_dict, ensure_ascii=False)))
                            ret_true = False
                            break
                        ret = ret.replace('NP', 'NP-HLP')
                        ret = ret.replace('VP-PRD', 'VP-HLP')
                        ret = ret.replace('NULL-AUX', 'NULL-HLP')
                    if ret == '':
                        continue
                    retlist.append('(IP ' + ret + ')')
                if ret_true:
                    ROOT = ''.join([add_other_labels(IP) for IP in retlist])
                    # ROOT = ''.join(retlist)
                    ROOT = simple_add_label(ROOT, 'ROOT')
                    # print(CorpusLine0)
                    # print(ROOT)

                    if ROOT.find('(wDS ') >= 0:  # wrong double subjects “我们[在部队高度分散的态势下，]各部(分别(展开了))独立自主的游击战斗”
                        tmp_dict = {'fname': fInPath, 'lineNo': lineNo, 'type': "wDS", 'IP': ROOT,
                                    'w_line': CorpusLine0}
                        f_wrong.write('{}\n'.format(json.dumps(tmp_dict, ensure_ascii=False)))
                    elif ROOT.find('(wS') >= 0:
                        tmp_dict = {'fname': fInPath, 'lineNo': lineNo, 'type': "wS", 'IP': ROOT,
                                    'w_line': CorpusLine0}
                        f_wrong.write('{}\n'.format(json.dumps(tmp_dict, ensure_ascii=False)))
                    elif label_isnot_all_right(load_trees(ROOT)[0]):  # wrong label
                        tmp_dict = {'fname': fInPath, 'lineNo': lineNo, 'type': "wL", 'IP': ROOT, 'w_line': CorpusLine0}
                        f_wrong.write('{}\n'.format(json.dumps(tmp_dict, ensure_ascii=False)))
                    # assert is_all_match(CorpusLine0, ROOT), 'the tree created doesn\'t match the original plain string !'
                    elif is_all_match(CorpusLine0, ROOT):
                        bi_tree = multi2bi.entry_multi2bi(ROOT)
                        if bi_tree.find('wrong in line') >= 0:
                            tmp_dict = {'fname': fInPath, 'lineNo': lineNo, 'type': "bi", 'IP': ROOT,
                                        'w_line': CorpusLine0}
                            f_wrong.write('{}\n'.format(json.dumps(tmp_dict, ensure_ascii=False)))
                        else:
                            fOut.write(ROOT + '\n')

                        return True
                    else:  # other wrong
                        tmp_dict = {'fname': fInPath, 'lineNo': lineNo, 'type': "Ow", 'IP': '', 'w_line': CorpusLine0}
                        f_wrong.write('{}\n'.format(json.dumps(tmp_dict, ensure_ascii=False)))
    return False
def QuestionMark(str1):
    def Double(matched):
        return str(matched.group()).replace('？', '－')
    def Single(matched):
        return str(matched.group()).replace('？', '·')
    if re.search(r'\\\\？\\\\？(\\\\？)*', str1):
        str1 = re.sub(r'\\\\？\\\\？(\\\\？)*', Double, str1)
    if re.search(r'\\\\？', str1):
        str1 = re.sub(r'\\\\？', Single, str1)
    return str1
def Replace(CorpusLine):
    StarStack = []
    CorpusLine = re.sub(r'\s+', r'', CorpusLine)
    CorpusLine = CorpusLine.replace('<<', '$')
    CorpusLine = CorpusLine.replace('>>', '&')
    CorpusLine = CorpusLine.replace('||', '#')
    CorpusLine = QuestionMark(CorpusLine)
    # # 修改转格式出现的半角问号
    # CorpusLine = re.sub(r'\\\\\?\s*\\\\\?', r'\\\\－\\\\－',CorpusLine)
    # CorpusLine = CorpusLine.replace('\\\\?|', '')
    # 统一将各种不同形式的破折号换成全角破折号
    CorpusLine = re.sub(r'[―—─━]', r'－', CorpusLine)

    if len(CorpusLine) < 2:
        return CorpusLine
    CorpusLineList = list(CorpusLine)
    for i in range(1, len(CorpusLineList)):
        if CorpusLineList[i - 1] == '*' and CorpusLineList[i] == '*':
            StarStack.append('*')
            if len(StarStack) % 2 == 1:
                CorpusLineList[i - 1] = '^'
                CorpusLineList[i] = '^'
    CorpusLine = ''.join(CorpusLineList)
    CorpusLine = CorpusLine.replace('^^', '^')
    CorpusLine = CorpusLine.replace('**', '*')

    return CorpusLine


def del_separator(CorpusLine):
    return re.sub(r'━{3,}', '', CorpusLine)


def ReadCorpus(id_root, fInPath, fOut, f_wrong,f_luan):
    # fin = codecs.open(fInPath, 'r', encoding='gbk')
    fin = codecs.open(fInPath, 'r', encoding='utf-8', errors='ignore')

    lineNo = 1
    for CorpusLine in fin:
        if re.findall(r'参考书目',CorpusLine):
            break
        if len(re.findall(r'[^\－\(\[\{\<\)\]\}\>\|\*\\\\u4e00-\u9fa5\s]{10,}', CorpusLine)) > 1 or (
                len(re.findall(r'[^\－\(\[\{\<\)\]\}\>\|\*\\\\u4e00-\u9fa5\s]{20,}', CorpusLine)) == 1 and len(
            CorpusLine) < 100) or re.findall(
            r'[^\－\(\[\{\<\)\]\}\>\|\*\\\\u4e00-\u9fa5\s]{20,}', CorpusLine):
            # print(CorpusLine)
            f_luan.write(CorpusLine + '\n')
        elif re.findall(r'[a-zA-Z0-9]',CorpusLine):#半角的都是错的
            f_luan.write(CorpusLine + '\n')
        elif re.findall(r'[áéικНЯПДБИигьУнвчымзоедкпЛтЭГля]',CorpusLine):#不删除□
            f_luan.write(CorpusLine + '\n')


        # if len(re.findall(r'[ａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺ]{10,}',CorpusLine))>1 and len(CorpusLine)<100:
        #     f_luan.write(CorpusLine+'\n')
        else:
            CorpusLine = re.sub(r"^\s*[0-9]+", '', CorpusLine)
            CorpusLine = CorpusLine.strip()  # 3、去掉首尾空格及换行，将所有行依次追加成一行。HINT:先做3以防止line[-1]识别成\n或\r
            CorpusLine = del_space(CorpusLine)
            CorpusLine = del_separator(CorpusLine)

            # if len(CorpusLine) < 2:
            #     return list(CorpusLine)
            if len(CorpusLine) > 1:
                SplitIP(lineNo, CorpusLine, fOut, fInPath, f_wrong)
                id_root += 1
            lineNo += 1
    return id_root


def is_last(mystr):
    is_last = True
    for key in coupled_anno_symbols:
        if mystr.find(key) >= 0:
            is_last = False
            break
    return is_last


def is_recursive_predicate(mystr):
    return True if mystr.find('(') >= 0 and mystr.find('(w') < 0 and mystr.find('((w') < 0 else False


def is_recursive(mystr):
    for a in open_brackets[1:]:
        if mystr.find(a) >= 0:
            return True
    return False


def is_phrase_separator(mystr):
    return True if mystr.find('|') >= 0 and mystr[0] == '{' and mystr[-1] == '}' else False


def is_simple_separator(mystr):
    return True if mystr.find('|') >= 0 and mystr.find('{') < 0 else False


def is_predicate(mystr):  #
    return True if (mystr[0] == '(' and mystr[-1] == ')') else False  # or (mystr[0]=='{' and mystr[-1]=='}') 不能写


def is_fuwei(mystr):
    return True if (mystr[0] == '{' and mystr[-1] == '}') else False


def is_con(mystr):
    return True if (mystr[0] == '<' and mystr[-1] == '>') else False


def is_aux(mystr):
    return True if (mystr[0] == '$' and mystr[-1] == '&') else False


def is_mod(mystr):
    return True if (mystr[0] == '[' and mystr[-1] == ']') else False


def is_ero(mystr):
    return True if (mystr[0] == '^' and mystr[-1] == '*') else False


def del_space(mystr):
    return re.sub('\s+', '', mystr)


def only_add_label(mystr, label):
    if len(mystr) <= 0:
        return '(Ow ' + mystr + ')'
    for anno in all_anno_symbols:
        if mystr.find(anno) >= 0:
            return '(Ow ' + mystr + ')'
    return '(' + label + ' ' + mystr + ')'


def add_label(mystr, label):
    if len(mystr.strip()) == 0:
        return ''
    if mystr[:3] == '(w ' or mystr[:4] == '((w ':
        return mystr
    if mystr == '()':
        return '(VP-PRD φ)'
    if is_predicate(mystr):
        mystr = mystr[1:-1]
        if is_recursive_predicate(mystr):
            pre_list = re.split(r'\(|\)', mystr)
            # assert len(pre_list) == 3, 'wrong predicate !'
            if len(pre_list) != 3 or len(re.findall(r'\(', mystr)) != 1:
                mystr = del_anno_syms(mystr)
                return "(wP " + mystr + ")"  # wrong predicate !
            for idx_tmp, tmp in enumerate(pre_list):
                if len(tmp) > 0 or idx_tmp == 1:
                    if idx_tmp == 0 and is_last(tmp) != True:  # 1. （A\\B(C)）2. （A<D>B(C)）3. （A<<D>>B(C)
                        pre_list[idx_tmp] = build_tree(tmp)
                        if is_all_punc(tmp):
                            pre_list[idx_tmp] = pre_list[idx_tmp].replace('NP', 'w')
                        else:
                            pre_list[idx_tmp] = pre_list[idx_tmp].replace('NP', 'NULL-MOD')
                    elif idx_tmp == 1:
                        if len(tmp) <= 0:
                            pre_list[idx_tmp] = '(VP-PRD φ)'
                        else:
                            pre_list[idx_tmp] = simple_add_label(pre_list[idx_tmp], 'VP-PRD')  # 谓词的序号一定为1
                    else:
                        pre_list[idx_tmp] = simple_add_label(pre_list[idx_tmp], 'NULL-MOD')
                        if is_all_punc(tmp):
                            pre_list[idx_tmp] = pre_list[idx_tmp].replace('NULL-MOD', 'w')
                        else:
                            pre_list[idx_tmp] = pre_list[idx_tmp].replace('NP', 'NULL-MOD')  # 其它给予修饰语标签

            mystr = ''.join(pre_list)

        return simple_add_label(mystr, 'VP-PRD')
    if is_fuwei(mystr) == True:
        mystr = mystr[1:-1]
        # mystr = build_tree(mystr)
        if is_last(mystr) == False:
            mystr = build_tree(mystr)
        return simple_add_label(mystr, 'VP')
    if is_mod(mystr) == True:
        mystr = mystr[1:-1]
        return only_add_label(mystr, 'NULL-MOD')
    if is_con(mystr) == True:
        mystr = mystr[1:-1]
        return only_add_label(mystr, 'NULL-CON')
    if is_aux(mystr) == True:
        mystr = mystr[1:-1]
        return only_add_label(mystr, 'NULL-AUX')
    if is_ero(mystr) == True:
        mystr = mystr[1:-1]
        return only_add_label(mystr, 'NULL-ERO')
    if mystr[0] in open_brackets:  # the original symbol
        mystr = mystr[1:-1]

    return simple_add_label(mystr, label)


def simple_add_label(mystr, label):
    if len(mystr.strip()) <= 0:
        return ''
    else:
        if len(mystr) > 2 and mystr[0] == '(' and mystr[-1] == ')' and mystr[1:-1].find('(') < 0:
            if len(mystr) > 4 and mystr[:4] != '(IP ':  # 只有一个子节点，且不是IP????????
                return mystr
        return '(' + label + ' ' + mystr + ')'


def insertStr(nPos, str_1, sub_str):
    # 把字符串转为 list
    str_list = list(str_1)
    str_list.insert(nPos, sub_str)
    # 将 list 转为 str
    str_2 = "".join(str_list)
    return str_2


def add_border(mystr, border):
    return mystr if mystr[0] in open_brackets else brackets_map[border] + mystr + border


def simple_add_border(mystr, border):
    return brackets_map[border] + mystr + border


def is_connectors(mystr):
    return True if mystr.find('<') >= 0 else False


def is_IP_connectors(mystr):
    return True if mystr.find('\\') >= 0 else False


def is_double_objects(mystr):
    return True if mystr.find('#') >= 0 else False


def add_sub_list(mystr, sub_row_list, label):
    if len(mystr) > 0:
        if mystr[-1] == '|':  # '宽松政策|'<---'４月２６日特稿|（７）|（伯南克\\？货币政策），＂伯南克(吝出)宽松政策|'
            mystr = mystr.replace('|', '')
        if is_phrase_separator(mystr):  # '你(要(知道)){(不是(练习))|字(就能(好))}。'
            mystr = ''.join(
                [simple_add_label(build_tree(phrase), label) for phrase in mystr[1:-1].split('|') if len(phrase)])
            mystr = simple_add_label(mystr, 'VP')
        # elif is_recursive(mystr[1:-1]):  # 非述语的递归（不含小括号）:'{(促进){(互利(投资))}}
        #     mystr = simple_add_label(build_tree(mystr[1:-1]), 'VP')  # add a label ?????
        else:
            mystr = add_label(mystr, label)
        sub_row_list.append(mystr)
    return sub_row_list


def combine_nodes(n1, n2, label):
    return simple_add_label(n1 + ' ' + n2, label)


def generate_new_list(idx1, mystr, idx2, sub_row_list):
    sub_row_list_new = []
    sub_row_list_new.extend(sub_row_list[:idx1])
    sub_row_list_new.append(mystr)
    sub_row_list_new.extend(sub_row_list[idx2:])
    return sub_row_list_new


def object_and_predicate(mystr):
    stack = []
    # is_true = True
    pre_id = 0
    open_id = -1
    sub_row_list = []
    for id, char in enumerate(mystr):
        if char in open_brackets:
            stack.append(char)
            if open_id < 0:
                open_id = id
        elif char in close_brackets:
            if len(stack) < 1:
                # assert is_true, 'Brackets mismatch!'
                # break
                return ["(BM " + mystr + ")"]
            elif brackets_map[char] == stack[-1]:
                stack.pop()
                if len(stack) == 0:
                    if open_id != pre_id:
                        # 狼吞虎咽地(吃完了)
                        if mystr[open_id - 1] in punc_set and pre_id == 0:
                            sub_row_list.append(mystr[pre_id:open_id])  # 未标注部分：狼吞虎咽地
                            sub_row_list.append(mystr[open_id:id + 1])  # 标注部分:(吃完了)
                            return sub_row_list
                    pre_id = id + 1
                    open_id = -1
            else:
                # is_true = False
                # assert is_true, 'Brackets mismatch!'
                # break
                return ["(BM " + mystr + ")"]

        else:
            continue
    if stack != []:
        # is_true = False
        # assert is_true, 'Brackets mismatch!'
        mystr = "(BM " + mystr + ")"
    return [mystr]


def get_label(mystr):
    return re.findall(r'^\((\S+)\s', mystr)[0]


def is_VP_node(mystr):
    return True if get_label(mystr).find('VP') >= 0 else False


def substitute_label(mystr, label):
    return mystr.replace(get_label(mystr), label)


def is_wrong_double_objects1(sub_tree, idx):  # 没有述语，也没有空述语
    if len(re.findall(r'#', sub_tree[idx])) > 1:  # 缺少空述语：(拥有))庄园||３７座、牧场||１２个、土地||３万多亩、大小牲口||上万头、农奴||３０００多人
        sub_tree[idx] = substitute_label(sub_tree[idx], "wDO")
        return True, ''.join(sub_tree)
    if idx <= 0 or idx + 1 >= len(sub_tree):  # O1前面没有成分或者后面没有O2
        sub_tree[idx] = substitute_label(sub_tree[idx], "wDO")
        return True, ''.join(sub_tree)
    if idx > 0 and not is_VP_node(sub_tree[idx - 1]):  # O1前面的成分不是述语VP成分
        sub_tree[idx - 1] = substitute_label(sub_tree[idx - 1], "wDO")
        return True, ''.join(sub_tree)
    return False, sub_tree


def is_wrong_double_objects2(sub_tree, idx):  # 没有述语，也没有空述语
    if len(re.findall(r'#', sub_tree[idx])) > 1:  # 缺少空述语：(拥有))庄园||３７座、牧场||１２个、土地||３万多亩、大小牲口||上万头、农奴||３０００多人
        sub_tree[idx] = substitute_label(sub_tree[idx], "wDO")
        return True, ''.join(sub_tree)
    if idx <= 0:  # O1||O2前面没有成分
        sub_tree[idx] = substitute_label(sub_tree[idx], "wDO")
        return True, ''.join(sub_tree)
    if not ((idx > 0 and is_VP_node(sub_tree[idx - 1])) or (
            idx > 2 and not is_VP_node(sub_tree[idx - 1]) and is_VP_node(sub_tree[idx - 3]))):  # O1前面的成分不是述语VP成分

        sub_tree[idx - 1] = substitute_label(sub_tree[idx - 1], "wDO")
        return True, ''.join(sub_tree)
    return False, sub_tree


def DO_with_auxiliary_word(sub_tree, idx):
    return True if idx > 2 and get_label(sub_tree[idx - 3]).find('VP') >= 0 and get_label(sub_tree[idx - 2]).find(
        'NP') >= 0 and get_label(sub_tree[idx - 1]).find('AUX') >= 0 and sub_tree[idx].find(' #') >= 0 else False


def build_tree(row):
    # 对于每一行数据，对配对的括号进行如下判定：若括号为左括号，入栈；若括号为右括号，判断是否跟栈尾括号对应，若对应，弹出栈尾元素。若所有括号均正确闭合，则最后栈为空。
    sub_row_list = []
    stack = []
    # is_true = True
    pre_id = 0
    open_id = -1
    if is_last(row):
        if row[-1] == '|':
            row = row.replace("|", "")
        if row.find('#') >= 0:
            return only_add_label(row, 'wDO')
        return simple_add_label(row, 'NP')  # 独词句?????
    else:
        for id, char in enumerate(row):
            if char in open_brackets:
                stack.append(char)
                if open_id < 0:
                    open_id = id
            elif char in close_brackets:
                if len(stack) < 1:
                    # is_true = False
                    # assert is_true, 'Brackets mismatch!'
                    # break
                    return "(BM " + row + ")"

                elif brackets_map[char] == stack[-1]:
                    stack.pop()
                    if len(stack) == 0:
                        if open_id != pre_id:
                            # 狼吞虎咽地(吃完了)
                            if is_all_punc(row[pre_id:open_id]):
                                sub_row_list.append(simple_add_label(row[pre_id:open_id], 'w'))
                            else:
                                sub_row_list.append(simple_add_label(row[pre_id:open_id],
                                                                     'NP'))  # 未标注部分：狼吞虎咽地#为什么是append，不是add_sub_list？？？
                            sub_row_list = add_sub_list(row[open_id:id + 1], sub_row_list, 'label')  # 标注部分:(吃完了)
                        else:
                            sub_row_list = add_sub_list(row[pre_id:id + 1], sub_row_list, 'label')  # 标注部分：{(启用)Ｍ５０３航线}
                        pre_id = id + 1
                        open_id = -1
                else:
                    # is_true = False
                    # assert is_true, 'Brackets mismatch!'
                    # break
                    return "(BM " + row + ")"
            else:
                if len(stack) == 0 and is_last(row[id:]) is True:  # IP尾部未标注部分：'{(启用)Ｍ５０３航线}'中的'Ｍ５０３航线'
                    sub_row_list = add_sub_list(row[id:], sub_row_list, 'NP')
                    break
                continue
        if stack:
            # is_true = False
            # assert is_true, 'Brackets mismatch!'
            return "(BM " + row + ")"
        sub_row_list_new = copy.deepcopy(sub_row_list)
        is_double_objects = False
        new_idx = 0
        # print(sub_row_list)
        for idx_tmp, sub_row in enumerate(sub_row_list):
            if sub_row == '(NP #)':  # 宾语1,2 为谓词性结构：(给予){东北(振兴)}||{(有力(支撑))}
                # sub_row = sub_row.replace('#', '')
                # assert idx_tmp > 0 and idx_tmp + 1 < len(sub_row_list), 'wrong double objects without predicate !'
                if idx_tmp - 2 < 0 or idx_tmp + 1 >= len(sub_row_list):
                    sub_row_list[idx_tmp] = substitute_label(sub_row, "wDO")
                    return ''.join(sub_row_list)

                sub_row_list_new[idx_tmp - 1] = sub_row_list_new[idx_tmp - 1].replace('VP', 'VP-OBJ', 1)
                sub_row_list_new[idx_tmp - 1] = add_other_labels(sub_row_list_new[idx_tmp - 1])
                sub_row_list_new[idx_tmp + 1] = sub_row_list_new[idx_tmp + 1].replace('VP', 'VP-OBJ', 1)
                sub_row_list_new[idx_tmp + 1] = add_other_labels(sub_row_list_new[idx_tmp + 1])
                sub_row_list_new.pop(idx_tmp)
                new_idx -= 1
                continue
            if len(re.findall(r'\(NP\S* #', sub_row)) > 0 and sub_row_list[idx_tmp - 1].find(
                    'VP') >= 0:  # 宾语1为谓词性结构,宾语2为体词性结构：(给予){东北(振兴)}||有力的支撑
                # sub_row = sub_row.replace('#', '')
                # assert idx_tmp > 0 and idx_tmp + 1 < len(sub_row_list), 'wrong double objects without predicate !'
                if idx_tmp - 2 < 0:
                    sub_row_list[idx_tmp] = substitute_label(sub_row, "wDO")
                    return ''.join(sub_row_list)
                sub_row_list_new[idx_tmp] = sub_row_list_new[idx_tmp].replace('#', '')
                sub_row_list_new[idx_tmp] = sub_row_list_new[idx_tmp].replace('NP', 'NP-OBJ')  # ??????
                sub_row_list_new[idx_tmp - 1] = sub_row_list_new[idx_tmp - 1].replace('VP', 'VP-OBJ', 1)  # ??????
                sub_row_list_new[idx_tmp - 1] = add_other_labels(sub_row_list_new[idx_tmp - 1])
                new_idx -= 1
                continue
            if len(sub_row) >= 2 and sub_row[-2] == '#':  # 假设宾语1是普通的字符串-体词，(label 人#)；宾语2是一个已识别的块-谓词,(label object2)
                sub_row = sub_row.replace('#', '')
                # assert idx_tmp > 0 and idx_tmp + 1 < len(sub_row_list), 'wrong double objects without predicate !'
                if idx_tmp <= 0 or idx_tmp + 1 >= len(sub_row_list):
                    sub_row_list[idx_tmp] = substitute_label(sub_row, "wDO")
                    return ''.join(sub_row_list)
                sub_row_list_new[idx_tmp] = sub_row_list_new[idx_tmp].replace('#', '')
                sub_row_list_new[idx_tmp] = sub_row_list_new[idx_tmp].replace('NP', 'NP-OBJ')
                # mystr = combine_nodes(sub_row_list[idx_tmp - 1], sub_row, 'VP-PRD')
                sub_row_list_new[idx_tmp + 1] = sub_row_list_new[idx_tmp + 1].replace('VP', 'VP-OBJ', 1)
                sub_row_list_new[idx_tmp + 1] = add_other_labels(sub_row_list_new[idx_tmp + 1])
                # mystr = combine_nodes(mystr, sub_row_list[idx_tmp + 1], 'VP-PRD')
                # mystr = add_other_labels(mystr)
                # sub_row_list_new = generate_new_list(new_idx - 1, mystr, new_idx + 2, sub_row_list_new)
                new_idx -= 1
                continue
            elif sub_row.find('#') >= 0:  # 假设宾语1是体词；宾语2也是体词。则两者被识别为一个块，(label 矿产金生产#４０吨)
                is_wDO, sub_row_str = is_wrong_double_objects2(sub_row_list, idx_tmp)
                if is_wDO:
                    return sub_row_str

                if DO_with_auxiliary_word(sub_row_list, idx_tmp):  # (VP (VP (VP v obj1) aux) obj2)
                    sub_row_list_new[idx_tmp - 2] = sub_row_list_new[idx_tmp - 2].replace('NP', 'NP-OBJ')
                    sub_row_list_new[idx_tmp] = sub_row_list_new[idx_tmp].replace('#', '')  # delete '#'
                    sub_row_list_new[idx_tmp] = sub_row_list_new[idx_tmp].replace('NP', 'NP-OBJ')
                    new_idx -= 2
                else:
                    object1 = sub_row[sub_row.find(' ') + 1:sub_row.find('#')]
                    object2 = sub_row[sub_row.find('#') + 1:-1]
                    object1 = simple_add_label(object1, 'NP-OBJ')
                    object2 = simple_add_label(object2, 'NP-OBJ')
                    # mystr = combine_nodes(sub_row_list[idx_tmp - 1], object1, 'VP-PRD')
                    # mystr = combine_nodes(mystr, object2, 'VP-PRD')
                    # sub_row_list_new = generate_new_list(idx_tmp - 1, mystr, idx_tmp + 1, sub_row_list_new)

                    sub_row_list_new[idx_tmp] = object1 + ' ' + object2
                    # sub_row_list_new = generate_new_list(new_idx + 1, object2, new_idx + 1, sub_row_list_new)

                    new_idx -= 1
                    is_double_objects = True
                    # break

            new_idx += 1
        sent = ' '.join(sub_row_list_new)

    if row[:2] != '(w':
        assert row != sent, row + '\n' + sent
    return sent


class TreebankNode(object):
    pass


class InternalTreebankNode(TreebankNode):
    def __init__(self, label, children):
        assert isinstance(label, str)
        self.label = label

        assert isinstance(children, collections.abc.Sequence)
        assert all(isinstance(child, TreebankNode) for child in children)
        assert children
        self.children = tuple(children)

    def linearize(self):
        return "({} {})".format(
            self.label, " ".join(child.linearize() for child in self.children))

    def leaves(self):
        for child in self.children:
            yield from child.leaves()

    def convert(self, index=0):
        tree = self
        sublabels = [self.label]

        while len(tree.children) == 1 and isinstance(
                tree.children[0], InternalTreebankNode):
            tree = tree.children[0]
            sublabels.append(tree.label)

        children = []
        for child in tree.children:
            children.append(child.convert(index=index))
            index = children[-1].right

        return InternalParseNode(tuple(sublabels), children)


class LeafTreebankNode(TreebankNode):
    def __init__(self, tag, word):
        assert isinstance(tag, str)
        self.tag = tag

        assert isinstance(word, str)
        self.word = word

    def linearize(self):
        return "({} {})".format(self.tag, self.word)

    def leaves(self):
        yield self


def load_trees(treeStr):
    tokens = treeStr.replace("(", " ( ").replace(")", " ) ").split()

    def helper(index):
        trees = []

        while index < len(tokens) and tokens[index] == "(":
            paren_count = 0
            while tokens[index] == "(":
                index += 1
                paren_count += 1

            label = tokens[index]
            index += 1

            if tokens[index] == "(":
                children, index = helper(index)
                trees.append(InternalTreebankNode(label, children))
            else:
                word = tokens[index]
                index += 1
                trees.append(LeafTreebankNode(label, word))

            while paren_count > 0:
                assert tokens[index] == ")"
                index += 1
                paren_count -= 1

        return trees, index

    trees, index = helper(0)
    assert index == len(tokens)
    return trees


def del_anno_syms(mystr):
    for k in original_anno_symbols:
        mystr = mystr.replace(k, '')
    mystr = re.sub(r'\s+', '', mystr)
    return mystr


def get_plain_text(mystr):
    mystr = ''.join([leaf.word for leaf in load_trees(mystr)[0].leaves()])
    mystr = re.sub(r'φ', '', mystr)
    mystr = re.sub(r'\s+', '', mystr)
    return mystr


def is_all_match(mystr, treeStr):
    is_match = False
    mystr = del_anno_syms(mystr)
    treeStr = get_plain_text(treeStr)
    # if treeStr.find("#") >= 0:
    #     treeStr=treeStr.replace("#","")  # ?????
    if mystr == treeStr:
        is_match = True
    return is_match


def main():
    inpFile = './t.txt'
    outFile = './t.out'
    luanFile = './l.out'
    f_wrong = open('./wrong.json', 'w')
    fOut = codecs.open(outFile, 'w', encoding='utf-8', errors='ignore')
    f_luan = codecs.open(luanFile, 'w', encoding='utf-8', errors='ignore')
    ReadCorpus(0, inpFile, fOut, f_wrong, f_luan)


if __name__ == '__main__':
    main()