import numpy as np

def decode(force_gold, sentence_len, label_scores_chart, is_train, gold, label_vocab):
    NEG_INF = -np.inf
    label_scores_chart_copy = label_scores_chart.copy() # 编码层输出的表
    value_chart = np.zeros((sentence_len+1, sentence_len+1), dtype=np.float32)
    # value_chart = label_scores_chart.copy()
    split_idx_chart = np.zeros((sentence_len+1, sentence_len+1), dtype=np.int32)
    best_label_chart = np.zeros((sentence_len+1, sentence_len+1), dtype=np.int32)
    #get ground truth oracle_label_chart(label_id), oracle_split_chart(split_id)
    if is_train or force_gold:
        oracle_label_chart = np.zeros((sentence_len+1, sentence_len+1), dtype=np.int32)
        oracle_split_chart = np.zeros((sentence_len+1, sentence_len+1), dtype=np.int32)
        for length in range(1, sentence_len + 1):
            for left in range(0, sentence_len + 1 - length):
                right = left + length
                oracle_label_chart[left, right] = label_vocab.index(gold.oracle_label(left, right))
                if length == 1: # length=1，span是词，终止条件
                    continue
                oracle_splits = gold.oracle_splits(left, right)
                oracle_split_chart[left, right] = min(oracle_splits)
    # get ground truth done
    # oracle_label_chart
    # oracle_split_chart
    # 得分 （label+split）value_chart，
    # 切分点 split_idx_chart，
    # label_id: best_label_chart
    # All fully binarized trees have the same number of nodes
    for length in range(1, sentence_len + 1):
        for left in range(0, sentence_len + 1 - length):
            right = left + length
            # 遍历每一个span
            if is_train or force_gold:
                # 若有答案，记录 label_id
                oracle_label_index = oracle_label_chart[left, right]

            if force_gold:
                label_score = label_scores_chart_copy[left, right, oracle_label_index]
                best_label_chart[left, right] = oracle_label_index

            else:
                if is_train:
                    # augment: here we subtract 1 from the oracle label
                    # 训练时的增强：从预测标签对应的值中减去1
                    label_scores_chart_copy[left, right, oracle_label_index] -= 1

                # We do argmax ourselves to make sure it compiles to pure C
                # 遍历求argmax，以便编译为C， 而不是使用numpy
                if length < sentence_len:
                    argmax_label_index = 0
                else:
                    # Not-a-span label is not allowed at the root of the tree
                    argmax_label_index = 1

                label_score = label_scores_chart_copy[left, right, argmax_label_index]
                for label_index_iter in range(1, label_scores_chart_copy.shape[2]):
                    if label_scores_chart_copy[left, right, label_index_iter] > label_score:
                        argmax_label_index = label_index_iter
                        label_score = label_scores_chart_copy[left, right, label_index_iter]
                best_label_chart[left, right] = argmax_label_index
                # best_label_chart 存储span对应得分最高的label_index
                if is_train:
                    # augment: here we add 1 to all label scores
                    # 先减1，再加1, 增强
                    label_score += 1

            # if length == 1:
            value_chart[left, right] = label_score
                # continue
    # def get_label(left, right):
    #     length = right - left
    #     if length < sentence_len:
    #         argmax_label_index = 0
    #     else:
    #         argmax_label_index = 1
    #     label_score = label_scores_chart_copy[left, right, argmax_label_index]
    #     for label_index_iter in range(1, label_scores_chart_copy.shape[2]):
    #         if label_scores_chart_copy[left, right, label_index_iter] > label_score:
    #             argmax_label_index = label_index_iter
    #             label_score = label_scores_chart_copy[left, right, label_index_iter]
    #     if is_train:
    #         label_score += 1
    #     return argmax_label_index, label_score
    def get_split(left, right):
        if force_gold:
            best_split = oracle_split_chart[left, right]
        else:
            best_split = left + 1  # 默认按最左切分 leftmost
            split_val = NEG_INF
            for split_idx in range(left + 1, right):
                max_split_val = value_chart[left, split_idx] + value_chart[split_idx, right]
                if max_split_val > split_val:
                    split_val = max_split_val
                    best_split = split_idx
        # label得分和左右两边的split得分
        # value_chart[left, right] = label_score + value_chart[left, best_split] + value_chart[best_split, right]
        split_idx_chart[left, right] = best_split

        return best_split

    num_tree_nodes = 2 * sentence_len - 1
    included_i = np.empty(num_tree_nodes, dtype=np.int32)
    included_j = np.empty(num_tree_nodes, dtype=np.int32)
    included_label = np.empty(num_tree_nodes, dtype=np.int32)

    idx = 0
    stack_idx = 1
    # technically, the maximum stack depth is smaller than this
    stack_i = np.empty(num_tree_nodes + 5, dtype=np.int32)
    stack_j = np.empty(num_tree_nodes + 5, dtype=np.int32)
    # stack_i 从左到右
    # stack_j 从右到左
    stack_i[1] = 0
    stack_j[1] = sentence_len

    while stack_idx > 0:
        i = stack_i[stack_idx]
        j = stack_j[stack_idx]
        stack_idx -= 1
        included_i[idx] = i
        included_j[idx] = j
        included_label[idx] = best_label_chart[i, j]
        idx += 1
        if i + 1 < j:  # 非叶子节点
            k = get_split(i, j)
            stack_idx += 1
            stack_i[stack_idx] = k
            stack_j[stack_idx] = j
            stack_idx += 1
            stack_i[stack_idx] = i
            stack_j[stack_idx] = k

    running_total = 0.0
    for idx in range(num_tree_nodes):
        running_total += label_scores_chart[included_i[idx], included_j[idx], included_label[idx]]

    score = value_chart[0, sentence_len]
    augment_amount = round(score - running_total)  # 总体增强差值
    # 得分，左边界，右边界，label，增量
    return score, included_i.astype(int), included_j.astype(int), included_label.astype(int), augment_amount
if __name__=='__main__':
    import trees
    import vocabulary
    test_str = '(ROOT (IP (NP-HLP (x （) (n 小标题) (x ）))))'
    # test_sentences = '（小标题）'
    test_treebank = trees.tree_from_str(test_str)
    test_parse = test_treebank.convert()

    label_vocab = vocabulary.Vocabulary()
    label_vocab.index(())
    label_list = ['ROOT', 'IP', 'NP-HLP', 'VP-SBJ', 'VP-OBJ', 'NP-SBJ', 'NP-OBJ']
    for i in label_list:
        label_vocab.index(i)
    nodes = [test_parse]
    while nodes:
        node = nodes.pop()
        if isinstance(node, trees.InternalParseNode):
            label_vocab.index(node.label)
            nodes.extend(reversed(node.children))
    label_vocab.index(())
    label_vocab.freeze()
    print("label_vocab_size {:,}.".format(label_vocab.size))
    label_scores_chart_np = np.random.random(size=[4, 4, label_vocab.size])
    decode(force_gold=False, sentence_len=3, label_scores_chart=label_scores_chart_np,
           is_train=True, gold=test_parse, label_vocab=label_vocab)
    decode(force_gold=True, sentence_len=3, label_scores_chart=label_scores_chart_np,
           is_train=True, gold=test_parse, label_vocab=label_vocab)
