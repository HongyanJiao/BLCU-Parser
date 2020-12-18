from nltk import Tree
# s = '(ROOT (IP (NULL-MOD 后来，) (VP-SBJ (NP-SBJ 机场建设) (VP-PRD 征用) (NP-OBJ 农田)) (VP-PRD 引起) (VP-OBJ (NP-SBJ 农民) (VP-PRD (NULL-MOD 强烈) (VP-PRD 反对))) (w ，))(IP (VP-PRD (NULL-MOD 又) (VP-PRD 是)) (NP-OBJ 他) (VP-PRD (NULL-MOD 耐心细致地) (VP-PRD 做通了)) (NP-OBJ 农民工作) (w 。)))'
s = '(ROOT (IP (NP-SBJ (ns 中国) (n 特色) (n 大国) (n 外交) (w ，)) (VP-PRD (vn 诠释)) (NP-OBJ (ns 中国) (n 格局) (u 的) (a 宏大)) (w (w 。))))'
t = Tree.fromstring(s)
# t.draw()
print('”，“'.join(t.leaves()))