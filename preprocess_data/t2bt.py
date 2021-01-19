from nltk import Tree
from nltk import combinations
from functools import reduce

def binarize(tree):
    if isinstance(tree, str):
        return tree
    elif len(tree) == 1:
        label = tree.label()
        return Tree(label, (binarize(tree[0]),''))
    else:
        label = tree.label()
        return reduce(lambda x, y: Tree(label, (binarize(x), binarize(y))),tree)
        # Φ
        #return reduce(lambda x, y: Tree(label, (binarize(x), binarize(y))), tree)
# t = Tree.fromstring('(ROOT (IP (NP-SBJ (ns 中国) (n 特色) (n 大国) (n 外交) (w ，)) (VP-PRD (vn 诠释)) (NP-OBJ (ns 中国) (n 格局) (u 的) (a 宏大)) (w (w 。))))')
#t=t.reverse()
# t.draw()
s = '(IP (NP-SBJ (ns 中国) (n 特色) (n 大国) (n 外交) (w ，)))'
t = Tree.fromstring(s)
t.chomsky_normal_form()

# bt = binarize(t)
#
string = str(t).replace('\n','')
s1=' '.join(filter(lambda x: x, string.split(' ')))
ret=s1.replace(' )',')')
print(ret)
# ret= Tree.fromstring(ret)
# ret.draw()




