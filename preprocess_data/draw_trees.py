from nltk import Tree
s = '(ROOT (IP (NP-HLP (x （) (n 小标题) (x ）))))'
t = Tree.fromstring(s)
t.draw()