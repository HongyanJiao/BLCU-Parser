import functools

import numpy as np

import torch
import torch.nn as nn
import torch.nn.init as init
import sys
# DTYPE = torch.uint8 if float(sys.version[:3]) < 3.7 else torch.bool
DTYPE = torch.bool
use_cuda = torch.cuda.is_available()
if use_cuda:
    torch_t = torch.cuda
    def from_numpy(ndarray):
        return torch.from_numpy(ndarray).pin_memory().cuda(async=True)
else:
    print("Not using CUDA!")
    torch_t = torch
    from torch import from_numpy

import pyximport
pyximport.install(setup_args={"include_dirs": np.get_include()})
import chart_helper
#import chart_decoder as chart_helper
import nkutil

import trees

START = "<START>"
STOP = "<STOP>"
UNK = "<UNK>"

TAG_UNK = "UNK"

# Assumes that these control characters are not present in treebank text
CHAR_UNK = "\0"
CHAR_START_SENTENCE = "\1"
CHAR_START_WORD = "\2"
CHAR_STOP_WORD = "\3"
CHAR_STOP_SENTENCE = "\4"

BERT_TOKEN_MAPPING = {
    "-LRB-": "(",
    "-RRB-": ")",
    "-LCB-": "{",
    "-RCB-": "}",
    "-LSB-": "[",
    "-RSB-": "]",
    "``": '"',
    "''": '"',
    "`": "'",
    '«': '"',
    '»': '"',
    '‘': "'",
    '’': "'",
    '“': '"',
    '”': '"',
    '„': '"',
    '‹': "'",
    '›': "'",
    "\u2013": "--", # en dash
    "\u2014": "--", # em dash
    }

# %%

class BatchIndices:
    """
    Batch indices container class (used to implement packed batches)
    """
    def __init__(self, batch_idxs_np):
        self.batch_idxs_np = batch_idxs_np
        # Note that the torch copy will be on GPU if use_cuda is set
        self.batch_idxs_torch = from_numpy(batch_idxs_np)

        self.batch_size = int(1 + np.max(batch_idxs_np))

        batch_idxs_np_extra = np.concatenate([[-1], batch_idxs_np, [-1]])
        self.boundaries_np = np.nonzero(batch_idxs_np_extra[1:] != batch_idxs_np_extra[:-1])[0]
        self.seq_lens_np = self.boundaries_np[1:] - self.boundaries_np[:-1]
        assert len(self.seq_lens_np) == self.batch_size
        self.max_len = int(np.max(self.boundaries_np[1:] - self.boundaries_np[:-1]))

# %%

class FeatureDropoutFunction(torch.autograd.function.InplaceFunction):
    @classmethod
    def forward(cls, ctx, input, batch_idxs, p=0.5, train=False, inplace=False):
        if p < 0 or p > 1:
            raise ValueError("dropout probability has to be between 0 and 1, "
                             "but got {}".format(p))

        ctx.p = p
        ctx.train = train
        ctx.inplace = inplace

        if ctx.inplace:
            ctx.mark_dirty(input)
            output = input
        else:
            output = input.clone()

        if ctx.p > 0 and ctx.train:
            ctx.noise = input.new().resize_(batch_idxs.batch_size, input.size(1))
            if ctx.p == 1:
                ctx.noise.fill_(0)
            else:
                ctx.noise.bernoulli_(1 - ctx.p).div_(1 - ctx.p)
            ctx.noise = ctx.noise[batch_idxs.batch_idxs_torch, :]
            output.mul_(ctx.noise)

        return output

    @staticmethod
    def backward(ctx, grad_output):
        if ctx.p > 0 and ctx.train:
            return grad_output.mul(ctx.noise), None, None, None, None
        else:
            return grad_output, None, None, None, None

class FeatureDropout(nn.Module):
    """
    Feature-level dropout: takes an input of size len x num_features and drops
    each feature with probabibility p. A feature is dropped across the full
    portion of the input that corresponds to a single batch element.
    """
    def __init__(self, p=0.5, inplace=False):
        super().__init__()
        if p < 0 or p > 1:
            raise ValueError("dropout probability has to be between 0 and 1, "
                             "but got {}".format(p))
        self.p = p
        self.inplace = inplace

    def forward(self, input, batch_idxs):
        return FeatureDropoutFunction.apply(input, batch_idxs, self.p, self.training, self.inplace)

# %%

class LayerNormalization(nn.Module):
    def __init__(self, d_hid, eps=1e-3, affine=True):
        super(LayerNormalization, self).__init__()

        self.eps = eps
        self.affine = affine
        if self.affine:
            self.a_2 = nn.Parameter(torch.ones(d_hid), requires_grad=True)
            self.b_2 = nn.Parameter(torch.zeros(d_hid), requires_grad=True)

    def forward(self, z):
        if z.size(-1) == 1:
            return z

        mu = torch.mean(z, keepdim=True, dim=-1)
        sigma = torch.std(z, keepdim=True, dim=-1)
        ln_out = (z - mu.expand_as(z)) / (sigma.expand_as(z) + self.eps)
        if self.affine:
            ln_out = ln_out * self.a_2.expand_as(ln_out) + self.b_2.expand_as(ln_out)

        # NOTE(nikita): the t2t code does the following instead, with eps=1e-6
        # However, I currently have no reason to believe that this difference in
        # implementation matters.
        # mu = torch.mean(z, keepdim=True, dim=-1)
        # variance = torch.mean((z - mu.expand_as(z))**2, keepdim=True, dim=-1)
        # ln_out = (z - mu.expand_as(z)) * torch.rsqrt(variance + self.eps).expand_as(z)
        # ln_out = ln_out * self.a_2.expand_as(ln_out) + self.b_2.expand_as(ln_out)

        return ln_out

# %%

class ScaledDotProductAttention(nn.Module):
    def __init__(self, d_model, attention_dropout=0.1):
        super(ScaledDotProductAttention, self).__init__()
        self.temper = d_model ** 0.5
        self.dropout = nn.Dropout(attention_dropout)
        self.softmax = nn.Softmax(dim=-1)

    def forward(self, q, k, v, attn_mask=None):
        # q: [batch, slot, feat]
        # k: [batch, slot, feat]
        # v: [batch, slot, feat]

        attn = torch.bmm(q, k.transpose(1, 2)) / self.temper

        if attn_mask is not None:
            assert attn_mask.size() == attn.size(), \
                    'Attention mask shape {} mismatch ' \
                    'with Attention logit tensor shape ' \
                    '{}.'.format(attn_mask.size(), attn.size())

            attn.data.masked_fill_(attn_mask, -float('inf'))

        attn = self.softmax(attn)
        # Note that this makes the distribution not sum to 1. At some point it
        # may be worth researching whether this is the right way to apply
        # dropout to the attention.
        # Note that the t2t code also applies dropout in this manner
        attn = self.dropout(attn)
        output = torch.bmm(attn, v)

        return output, attn

# %%
class LabelAttention(nn.Module):
    """
    Single-head Attention layer for label-specific representations
    """

    def __init__(self, hparams, d_model, d_k, d_v, d_l, d_proj, use_resdrop=True, q_as_matrix=False,
                 residual_dropout=0.1, attention_dropout=0.1, d_positional=None):
        super(LabelAttention, self).__init__()
        self.hparams = hparams
        self.d_k = d_k
        self.d_v = d_v
        self.d_l = d_l  # Number of Labels
        self.d_model = d_model  # Model Dimensionality
        self.d_proj = d_proj  # Projection dimension of each label output
        self.use_resdrop = use_resdrop  # Using Residual Dropout?
        self.q_as_matrix = q_as_matrix  # Using a Matrix of Q to be multiplied with input instead of learned q vectors
        self.combine_as_self = hparams.lal_combine_as_self  # Using the Combination Method of Self-Attention

        if d_positional is None:
            self.partitioned = False
        else:
            self.partitioned = True

        if self.partitioned:
            self.d_content = d_model - d_positional
            self.d_positional = d_positional

            if self.q_as_matrix:
                self.w_qs1 = nn.Parameter(torch_t.FloatTensor(self.d_l, self.d_content, d_k // 2), requires_grad=True)
            else:
                self.w_qs1 = nn.Parameter(torch_t.FloatTensor(self.d_l, d_k // 2), requires_grad=True)
            self.w_ks1 = nn.Parameter(torch_t.FloatTensor(self.d_l, self.d_content, d_k // 2), requires_grad=True)
            self.w_vs1 = nn.Parameter(torch_t.FloatTensor(self.d_l, self.d_content, d_v // 2), requires_grad=True)

            if self.q_as_matrix:
                self.w_qs2 = nn.Parameter(torch_t.FloatTensor(self.d_l, self.d_positional, d_k // 2),
                                          requires_grad=True)
            else:
                self.w_qs2 = nn.Parameter(torch_t.FloatTensor(self.d_l, d_k // 2), requires_grad=True)
            self.w_ks2 = nn.Parameter(torch_t.FloatTensor(self.d_l, self.d_positional, d_k // 2), requires_grad=True)
            self.w_vs2 = nn.Parameter(torch_t.FloatTensor(self.d_l, self.d_positional, d_v // 2), requires_grad=True)

            init.xavier_normal_(self.w_qs1)
            init.xavier_normal_(self.w_ks1)
            init.xavier_normal_(self.w_vs1)

            init.xavier_normal_(self.w_qs2)
            init.xavier_normal_(self.w_ks2)
            init.xavier_normal_(self.w_vs2)
        else:
            if self.q_as_matrix:
                self.w_qs = nn.Parameter(torch_t.FloatTensor(self.d_l, d_model, d_k), requires_grad=True)
            else:
                self.w_qs = nn.Parameter(torch_t.FloatTensor(self.d_l, d_k), requires_grad=True)
            self.w_ks = nn.Parameter(torch_t.FloatTensor(self.d_l, d_model, d_k), requires_grad=True)
            self.w_vs = nn.Parameter(torch_t.FloatTensor(self.d_l, d_model, d_v), requires_grad=True)

            init.xavier_normal_(self.w_qs)
            init.xavier_normal_(self.w_ks)
            init.xavier_normal_(self.w_vs)

        self.attention = ScaledDotProductAttention(d_model, attention_dropout=attention_dropout)
        if self.combine_as_self:
            self.layer_norm = LayerNormalization(d_model)
        else:
            self.layer_norm = LayerNormalization(self.d_proj)

        if not self.partitioned:
            # The lack of a bias term here is consistent with the t2t code, though
            # in my experiments I have never observed this making a difference.
            if self.combine_as_self:
                self.proj = nn.Linear(self.d_l * d_v, d_model, bias=False)
            else:
                self.proj = nn.Linear(d_v, d_model, bias=False)  # input dimension does not match, should be d_l * d_v
        else:
            if self.combine_as_self:
                self.proj1 = nn.Linear(self.d_l * (d_v // 2), self.d_content, bias=False)
                self.proj2 = nn.Linear(self.d_l * (d_v // 2), self.d_positional, bias=False)
            else:
                self.proj1 = nn.Linear(d_v // 2, self.d_content, bias=False)
                self.proj2 = nn.Linear(d_v // 2, self.d_positional, bias=False)
        if not self.combine_as_self:
            self.reduce_proj = nn.Linear(d_model, self.d_proj, bias=False)

        self.residual_dropout = FeatureDropout(residual_dropout)

    def split_qkv_packed(self, inp, k_inp=None):
        len_inp = inp.size(0)
        v_inp_repeated = inp.repeat(self.d_l, 1).view(self.d_l, -1, inp.size(-1))  # d_l x len_inp x d_model
        if k_inp is None:
            k_inp_repeated = v_inp_repeated
        else:
            k_inp_repeated = k_inp.repeat(self.d_l, 1).view(self.d_l, -1, k_inp.size(-1))  # d_l x len_inp x d_model

        if not self.partitioned:
            if self.q_as_matrix:
                q_s = torch.bmm(k_inp_repeated, self.w_qs)  # d_l x len_inp x d_k
            else:
                q_s = self.w_qs.unsqueeze(1)  # d_l x 1 x d_k
            k_s = torch.bmm(k_inp_repeated, self.w_ks)  # d_l x len_inp x d_k
            v_s = torch.bmm(v_inp_repeated, self.w_vs)  # d_l x len_inp x d_v
        else:
            if self.q_as_matrix:
                q_s = torch.cat([
                    torch.bmm(k_inp_repeated[:, :, :self.d_content], self.w_qs1),
                    torch.bmm(k_inp_repeated[:, :, self.d_content:], self.w_qs2),
                ], -1)
            else:
                q_s = torch.cat([
                    self.w_qs1.unsqueeze(1),
                    self.w_qs2.unsqueeze(1),
                ], -1)
            k_s = torch.cat([
                torch.bmm(k_inp_repeated[:, :, :self.d_content], self.w_ks1),
                torch.bmm(k_inp_repeated[:, :, self.d_content:], self.w_ks2),
            ], -1)
            v_s = torch.cat([
                torch.bmm(v_inp_repeated[:, :, :self.d_content], self.w_vs1),
                torch.bmm(v_inp_repeated[:, :, self.d_content:], self.w_vs2),
            ], -1)
        return q_s, k_s, v_s

    def pad_and_rearrange(self, q_s, k_s, v_s, batch_idxs):
        # Input is padded representation: n_head x len_inp x d
        # Output is packed representation: (n_head * mb_size) x len_padded x d
        # (along with masks for the attention and output)
        n_head = self.d_l
        d_k, d_v = self.d_k, self.d_v

        len_padded = batch_idxs.max_len
        mb_size = batch_idxs.batch_size
        if self.q_as_matrix:
            q_padded = q_s.new_zeros((n_head, mb_size, len_padded, d_k))
        else:
            q_padded = q_s.repeat(mb_size, 1, 1)  # (d_l * mb_size) x 1 x d_k
        k_padded = k_s.new_zeros((n_head, mb_size, len_padded, d_k))
        v_padded = v_s.new_zeros((n_head, mb_size, len_padded, d_v))
        invalid_mask = q_s.new_ones((mb_size, len_padded), dtype=DTYPE)

        for i, (start, end) in enumerate(zip(batch_idxs.boundaries_np[:-1], batch_idxs.boundaries_np[1:])):
            if self.q_as_matrix:
                q_padded[:, i, :end - start, :] = q_s[:, start:end, :]
            k_padded[:, i, :end - start, :] = k_s[:, start:end, :]
            v_padded[:, i, :end - start, :] = v_s[:, start:end, :]
            invalid_mask[i, :end - start].fill_(False)

        if self.q_as_matrix:
            q_padded = q_padded.view(-1, len_padded, d_k)
            attn_mask = invalid_mask.unsqueeze(1).expand(mb_size, len_padded, len_padded).repeat(n_head, 1, 1)
        else:
            attn_mask = invalid_mask.unsqueeze(1).repeat(n_head, 1, 1)

        output_mask = (~invalid_mask).repeat(n_head, 1)

        return (
            q_padded,
            k_padded.view(-1, len_padded, d_k),
            v_padded.view(-1, len_padded, d_v),
            attn_mask,
            output_mask,
        )

    def combine_v(self, outputs):
        # Combine attention information from the different labels
        d_l = self.d_l
        outputs = outputs.view(d_l, -1, self.d_v)  # d_l x len_inp x d_v

        if not self.partitioned:
            # Switch from d_l x len_inp x d_v to len_inp x d_l x d_v
            if self.combine_as_self:
                outputs = torch.transpose(outputs, 0, 1).contiguous().view(-1, d_l * self.d_v)
            else:
                outputs = torch.transpose(outputs, 0, 1)  # .contiguous() #.view(-1, d_l * self.d_v)
            # Project back to residual size
            outputs = self.proj(outputs)  # Becomes len_inp x d_l x d_model
        else:
            d_v1 = self.d_v // 2
            outputs1 = outputs[:, :, :d_v1]
            outputs2 = outputs[:, :, d_v1:]
            if self.combine_as_self:
                outputs1 = torch.transpose(outputs1, 0, 1).contiguous().view(-1, d_l * d_v1)
                outputs2 = torch.transpose(outputs2, 0, 1).contiguous().view(-1, d_l * d_v1)
            else:
                outputs1 = torch.transpose(outputs1, 0, 1)  # .contiguous() #.view(-1, d_l * d_v1)
                outputs2 = torch.transpose(outputs2, 0, 1)  # .contiguous() #.view(-1, d_l * d_v1)
            outputs = torch.cat([
                self.proj1(outputs1),
                self.proj2(outputs2),
            ], -1)  # .contiguous()

        return outputs

    def forward(self, inp, batch_idxs, k_inp=None):
        residual = inp  # len_inp x d_model
        len_inp = inp.size(0)

        # While still using a packed representation, project to obtain the
        # query/key/value for each head
        q_s, k_s, v_s = self.split_qkv_packed(inp, k_inp=k_inp)
        # d_l x len_inp x d_k
        # q_s is d_l x 1 x d_k

        # Switch to padded representation, perform attention, then switch back
        q_padded, k_padded, v_padded, attn_mask, output_mask = self.pad_and_rearrange(q_s, k_s, v_s, batch_idxs)
        # q_padded, k_padded, v_padded: (d_l * batch_size) x max_len x d_kv
        # q_s is (d_l * batch_size) x 1 x d_kv

        outputs_padded, attns_padded = self.attention(
            q_padded, k_padded, v_padded,
            attn_mask=attn_mask,
        )
        # outputs_padded: (d_l * batch_size) x max_len x d_kv
        # in LAL: (d_l * batch_size) x 1 x d_kv
        # on the best model, this is one value vector per label that is repeated max_len times
        if not self.q_as_matrix:
            outputs_padded = outputs_padded.repeat(1, output_mask.size(-1), 1)
        outputs = outputs_padded[output_mask]
        # outputs: (d_l * len_inp) x d_kv or LAL: (d_l * len_inp) x d_kv
        # output_mask: (d_l * batch_size) x max_len
        torch.cuda.empty_cache()
        outputs = self.combine_v(outputs)
        # outputs: len_inp x d_l x d_model, whereas a normal self-attention layer gets len_inp x d_model
        if self.use_resdrop:
            if self.combine_as_self:
                outputs = self.residual_dropout(outputs, batch_idxs)
            else:
                outputs = torch.cat(
                    [self.residual_dropout(outputs[:, i, :], batch_idxs).unsqueeze(1) for i in range(self.d_l)], 1)
        if self.combine_as_self:
            outputs = self.layer_norm(outputs + inp)
        else:
            for l in range(self.d_l):
                outputs[:, l, :] = outputs[:, l, :] + inp

            outputs = self.reduce_proj(outputs)  # len_inp x d_l x d_proj
            outputs = self.layer_norm(outputs)  # len_inp x d_l x d_proj
            outputs = outputs.view(len_inp, -1).contiguous()  # len_inp x (d_l * d_proj)

        return outputs, attns_padded
class MultiHeadAttention(nn.Module):
    """
    Multi-head attention module
    """

    def __init__(self, n_head, d_model, d_k, d_v, residual_dropout=0.1, attention_dropout=0.1, d_positional=None):
        super(MultiHeadAttention, self).__init__()

        self.n_head = n_head
        self.d_k = d_k
        self.d_v = d_v

        if d_positional is None:
            self.partitioned = False
        else:
            self.partitioned = True

        if self.partitioned:
            self.d_content = d_model - d_positional
            self.d_positional = d_positional

            self.w_qs1 = nn.Parameter(torch_t.FloatTensor(n_head, self.d_content, d_k // 2))
            self.w_ks1 = nn.Parameter(torch_t.FloatTensor(n_head, self.d_content, d_k // 2))
            self.w_vs1 = nn.Parameter(torch_t.FloatTensor(n_head, self.d_content, d_v // 2))

            self.w_qs2 = nn.Parameter(torch_t.FloatTensor(n_head, self.d_positional, d_k // 2))
            self.w_ks2 = nn.Parameter(torch_t.FloatTensor(n_head, self.d_positional, d_k // 2))
            self.w_vs2 = nn.Parameter(torch_t.FloatTensor(n_head, self.d_positional, d_v // 2))

            init.xavier_normal_(self.w_qs1)
            init.xavier_normal_(self.w_ks1)
            init.xavier_normal_(self.w_vs1)

            init.xavier_normal_(self.w_qs2)
            init.xavier_normal_(self.w_ks2)
            init.xavier_normal_(self.w_vs2)
        else:
            self.w_qs = nn.Parameter(torch_t.FloatTensor(n_head, d_model, d_k))
            self.w_ks = nn.Parameter(torch_t.FloatTensor(n_head, d_model, d_k))
            self.w_vs = nn.Parameter(torch_t.FloatTensor(n_head, d_model, d_v))

            init.xavier_normal_(self.w_qs)
            init.xavier_normal_(self.w_ks)
            init.xavier_normal_(self.w_vs)

        self.attention = ScaledDotProductAttention(d_model, attention_dropout=attention_dropout)
        self.layer_norm = LayerNormalization(d_model)

        if not self.partitioned:
            # The lack of a bias term here is consistent with the t2t code, though
            # in my experiments I have never observed this making a difference.
            self.proj = nn.Linear(n_head*d_v, d_model, bias=False)
        else:
            self.proj1 = nn.Linear(n_head*(d_v//2), self.d_content, bias=False)
            self.proj2 = nn.Linear(n_head*(d_v//2), self.d_positional, bias=False)

        self.residual_dropout = FeatureDropout(residual_dropout)

    def split_qkv_packed(self, inp, qk_inp=None):
        v_inp_repeated = inp.repeat(self.n_head, 1).view(self.n_head, -1, inp.size(-1)) # n_head x len_inp x d_model
        if qk_inp is None:
            qk_inp_repeated = v_inp_repeated
        else:
            qk_inp_repeated = qk_inp.repeat(self.n_head, 1).view(self.n_head, -1, qk_inp.size(-1))

        if not self.partitioned:
            q_s = torch.bmm(qk_inp_repeated, self.w_qs) # n_head x len_inp x d_k
            k_s = torch.bmm(qk_inp_repeated, self.w_ks) # n_head x len_inp x d_k
            v_s = torch.bmm(v_inp_repeated, self.w_vs) # n_head x len_inp x d_v
        else:
            q_s = torch.cat([
                torch.bmm(qk_inp_repeated[:,:,:self.d_content], self.w_qs1),
                torch.bmm(qk_inp_repeated[:,:,self.d_content:], self.w_qs2),
                ], -1)
            k_s = torch.cat([
                torch.bmm(qk_inp_repeated[:,:,:self.d_content], self.w_ks1),
                torch.bmm(qk_inp_repeated[:,:,self.d_content:], self.w_ks2),
                ], -1)
            v_s = torch.cat([
                torch.bmm(v_inp_repeated[:,:,:self.d_content], self.w_vs1),
                torch.bmm(v_inp_repeated[:,:,self.d_content:], self.w_vs2),
                ], -1)
        return q_s, k_s, v_s

    def pad_and_rearrange(self, q_s, k_s, v_s, batch_idxs):
        # Input is padded representation: n_head x len_inp x d
        # Output is packed representation: (n_head * mb_size) x len_padded x d
        # (along with masks for the attention and output)
        n_head = self.n_head
        d_k, d_v = self.d_k, self.d_v

        len_padded = batch_idxs.max_len
        mb_size = batch_idxs.batch_size
        q_padded = q_s.new_zeros((n_head, mb_size, len_padded, d_k))
        k_padded = k_s.new_zeros((n_head, mb_size, len_padded, d_k))
        v_padded = v_s.new_zeros((n_head, mb_size, len_padded, d_v))
        invalid_mask = q_s.new_ones((mb_size, len_padded), dtype=DTYPE)

        for i, (start, end) in enumerate(zip(batch_idxs.boundaries_np[:-1], batch_idxs.boundaries_np[1:])):
            q_padded[:,i,:end-start,:] = q_s[:,start:end,:]
            k_padded[:,i,:end-start,:] = k_s[:,start:end,:]
            v_padded[:,i,:end-start,:] = v_s[:,start:end,:]
            invalid_mask[i, :end-start].fill_(False)

        return(
            q_padded.view(-1, len_padded, d_k),
            k_padded.view(-1, len_padded, d_k),
            v_padded.view(-1, len_padded, d_v),
            invalid_mask.unsqueeze(1).expand(mb_size, len_padded, len_padded).repeat(n_head, 1, 1),
            (~invalid_mask).repeat(n_head, 1),
            )

    def combine_v(self, outputs):
        # Combine attention information from the different heads
        n_head = self.n_head
        outputs = outputs.view(n_head, -1, self.d_v)

        if not self.partitioned:
            # Switch from n_head x len_inp x d_v to len_inp x (n_head * d_v)
            outputs = torch.transpose(outputs, 0, 1).contiguous().view(-1, n_head * self.d_v)

            # Project back to residual size
            outputs = self.proj(outputs)
        else:
            d_v1 = self.d_v // 2
            outputs1 = outputs[:,:,:d_v1]
            outputs2 = outputs[:,:,d_v1:]
            outputs1 = torch.transpose(outputs1, 0, 1).contiguous().view(-1, n_head * d_v1)
            outputs2 = torch.transpose(outputs2, 0, 1).contiguous().view(-1, n_head * d_v1)
            outputs = torch.cat([
                self.proj1(outputs1),
                self.proj2(outputs2),
                ], -1)

        return outputs

    def forward(self, inp, batch_idxs, qk_inp=None):
        residual = inp

        # While still using a packed representation, project to obtain the
        # query/key/value for each head
        q_s, k_s, v_s = self.split_qkv_packed(inp, qk_inp=qk_inp)

        # Switch to padded representation, perform attention, then switch back
        q_padded, k_padded, v_padded, attn_mask, output_mask = self.pad_and_rearrange(q_s, k_s, v_s, batch_idxs)

        outputs_padded, attns_padded = self.attention(
            q_padded, k_padded, v_padded,
            attn_mask=attn_mask,
            )
        outputs = outputs_padded[output_mask]
        outputs = self.combine_v(outputs)

        outputs = self.residual_dropout(outputs, batch_idxs)

        return self.layer_norm(outputs + residual), attns_padded

# %%

class PositionwiseFeedForward(nn.Module):
    """
    A position-wise feed forward module.

    Projects to a higher-dimensional space before applying ReLU, then projects
    back.
    """

    def __init__(self, d_hid=128, d_ff=128, relu_dropout=0.1, residual_dropout=0.1):
        super(PositionwiseFeedForward, self).__init__()
        self.w_1 = nn.Linear(d_hid, d_ff)
        self.w_2 = nn.Linear(d_ff, d_hid)

        self.layer_norm = LayerNormalization(d_hid)
        # The t2t code on github uses relu dropout, even though the transformer
        # paper describes residual dropout only. We implement relu dropout
        # because we always have the option to set it to zero.
        self.relu_dropout = FeatureDropout(relu_dropout)
        self.residual_dropout = FeatureDropout(residual_dropout)
        self.relu = nn.ReLU()


    def forward(self, x, batch_idxs):
        residual = x

        output = self.w_1(x)
        output = self.relu_dropout(self.relu(output), batch_idxs)
        output = self.w_2(output)

        output = self.residual_dropout(output, batch_idxs)
        return self.layer_norm(output + residual)

# %%

class PartitionedPositionwiseFeedForward(nn.Module):
    def __init__(self, d_hid, d_ff, d_positional, relu_dropout=0.1, residual_dropout=0.1):
        super().__init__()
        self.d_content = d_hid - d_positional
        self.w_1c = nn.Linear(self.d_content, d_ff//2)
        self.w_1p = nn.Linear(d_positional, d_ff//2)
        self.w_2c = nn.Linear(d_ff//2, self.d_content)
        self.w_2p = nn.Linear(d_ff//2, d_positional)
        self.layer_norm = LayerNormalization(d_hid)
        # The t2t code on github uses relu dropout, even though the transformer
        # paper describes residual dropout only. We implement relu dropout
        # because we always have the option to set it to zero.
        self.relu_dropout = FeatureDropout(relu_dropout)
        self.residual_dropout = FeatureDropout(residual_dropout)
        self.relu = nn.ReLU()

    def forward(self, x, batch_idxs):
        residual = x
        xc = x[:, :self.d_content]
        xp = x[:, self.d_content:]

        outputc = self.w_1c(xc)
        outputc = self.relu_dropout(self.relu(outputc), batch_idxs)
        outputc = self.w_2c(outputc)

        outputp = self.w_1p(xp)
        outputp = self.relu_dropout(self.relu(outputp), batch_idxs)
        outputp = self.w_2p(outputp)

        output = torch.cat([outputc, outputp], -1)

        output = self.residual_dropout(output, batch_idxs)
        return self.layer_norm(output + residual)

# %%

class MultiLevelEmbedding(nn.Module):
    def __init__(self,
            num_embeddings_list,
            d_embedding,
            d_positional=None,
            max_len=300,
            normalize=True,
            dropout=0.1,
            timing_dropout=0.0,
            emb_dropouts_list=None,
            extra_content_dropout=None,
            **kwargs):
        super().__init__()

        self.d_embedding = d_embedding
        self.partitioned = d_positional is not None

        if self.partitioned:
            self.d_positional = d_positional
            self.d_content = self.d_embedding - self.d_positional
        else:
            self.d_positional = self.d_embedding
            self.d_content = self.d_embedding

        if emb_dropouts_list is None:
            emb_dropouts_list = [0.0] * len(num_embeddings_list)
        assert len(emb_dropouts_list) == len(num_embeddings_list)

        embs = []
        emb_dropouts = []
        for i, (num_embeddings, emb_dropout) in enumerate(zip(num_embeddings_list, emb_dropouts_list)):
            emb = nn.Embedding(num_embeddings, self.d_content, **kwargs)
            embs.append(emb)
            emb_dropout = FeatureDropout(emb_dropout)
            emb_dropouts.append(emb_dropout)
        self.embs = nn.ModuleList(embs)
        self.emb_dropouts = nn.ModuleList(emb_dropouts)

        if extra_content_dropout is not None:
            self.extra_content_dropout = FeatureDropout(extra_content_dropout)
        else:
            self.extra_content_dropout = None

        if normalize:
            self.layer_norm = LayerNormalization(d_embedding)
        else:
            self.layer_norm = lambda x: x

        self.dropout = FeatureDropout(dropout)
        self.timing_dropout = FeatureDropout(timing_dropout)

        # Learned embeddings
        self.position_table = nn.Parameter(torch_t.FloatTensor(max_len, self.d_positional))
        init.normal_(self.position_table)

    def forward(self, xs, batch_idxs, extra_content_annotations=None):
        content_annotations = [
            emb_dropout(emb(x), batch_idxs)
            for x, emb, emb_dropout in zip(xs, self.embs, self.emb_dropouts)
            ]
        content_annotations = sum(content_annotations)
        if extra_content_annotations is not None:
            if self.extra_content_dropout is not None:
                content_annotations += self.extra_content_dropout(extra_content_annotations, batch_idxs)
            else:
                content_annotations += extra_content_annotations

        timing_signal = torch.cat([self.position_table[:seq_len,:] for seq_len in batch_idxs.seq_lens_np], dim=0)
        timing_signal = self.timing_dropout(timing_signal, batch_idxs)

        # Combine the content and timing signals
        if self.partitioned:
            annotations = torch.cat([content_annotations, timing_signal], 1)
        else:
            annotations = content_annotations + timing_signal

        # TODO(nikita): reconsider the use of layernorm here
        annotations = self.layer_norm(self.dropout(annotations, batch_idxs))

        return annotations, timing_signal, batch_idxs

# %%

class CharacterLSTM(nn.Module):
    def __init__(self, num_embeddings, d_embedding, d_out,
            char_dropout=0.0,
            normalize=False,
            **kwargs):
        super().__init__()

        self.d_embedding = d_embedding
        self.d_out = d_out

        self.lstm = nn.LSTM(self.d_embedding, self.d_out // 2, num_layers=1, bidirectional=True)

        self.emb = nn.Embedding(num_embeddings, self.d_embedding, **kwargs)
        #TODO(nikita): feature-level dropout?
        self.char_dropout = nn.Dropout(char_dropout)

        if normalize:
            print("This experiment: layer-normalizing after character LSTM")
            self.layer_norm = LayerNormalization(self.d_out, affine=False)
        else:
            self.layer_norm = lambda x: x

    def forward(self, chars_padded_np, word_lens_np, batch_idxs):
        # copy to ensure nonnegative stride for successful transfer to pytorch
        decreasing_idxs_np = np.argsort(word_lens_np)[::-1].copy()
        decreasing_idxs_torch = from_numpy(decreasing_idxs_np)

        chars_padded = from_numpy(chars_padded_np[decreasing_idxs_np])
        word_lens = from_numpy(word_lens_np[decreasing_idxs_np])

        inp_sorted = nn.utils.rnn.pack_padded_sequence(chars_padded, word_lens_np[decreasing_idxs_np], batch_first=True)
        inp_sorted_emb = nn.utils.rnn.PackedSequence(
            self.char_dropout(self.emb(inp_sorted.data)),
            inp_sorted.batch_sizes)
        _, (lstm_out, _) = self.lstm(inp_sorted_emb)

        lstm_out = torch.cat([lstm_out[0], lstm_out[1]], -1)

        # Undo sorting by decreasing word length
        res = torch.zeros_like(lstm_out)
        res.index_copy_(0, decreasing_idxs_torch, lstm_out)

        res = self.layer_norm(res)
        return res


def get_bert(bert_model, bert_do_lower_case):
    # Avoid a hard dependency on BERT by only importing it if it's being used
    from pytorch_pretrained_bert import BertTokenizer, BertModel
    if bert_model.endswith('.tar.gz'):
        tokenizer = BertTokenizer.from_pretrained(bert_model.replace('.tar.gz', '-vocab.txt'), do_lower_case=bert_do_lower_case)
    else:
        tokenizer = BertTokenizer.from_pretrained(bert_model, do_lower_case=bert_do_lower_case)
    bert = BertModel.from_pretrained(bert_model)
    return tokenizer, bert
def get_bert_backup(bert_model, bert_do_lower_case):
    # Avoid a hard dependency on BERT by only importing it if it's being used
    from transformers import BertTokenizer, BertModel
    if bert_model.endswith('.tar.gz'):
        tokenizer = BertTokenizer.from_pretrained(bert_model.replace('.tar.gz', '-vocab.txt'), do_lower_case=bert_do_lower_case)
    else:
        tokenizer = BertTokenizer.from_pretrained(bert_model, do_lower_case=bert_do_lower_case)
    bert = BertModel.from_pretrained(bert_model)
    return tokenizer, bert

# %%

class Encoder(nn.Module):
    def __init__(self, hparams, embedding,
                     num_layers=1, num_heads=2,
                     d_kv = 32, d_ff=1024,
                     d_l=112,
                     d_positional=None,
                     num_layers_position_only=0,
                     relu_dropout=0.1, residual_dropout=0.1, attention_dropout=0.1,
                     use_lal=True,
                     lal_d_kv=128,
                     lal_d_proj=128,
                     lal_resdrop=True,
                     lal_pwff=True,
                     lal_q_as_matrix=False,
                     lal_partitioned=True):

        super().__init__()
        # Don't assume ownership of the embedding as a submodule.
        # TODO(nikita): what's the right thing to do here?
        self.embedding_container = [embedding]
        d_model = embedding.d_embedding
        self.hparams = hparams

        d_k = d_v = d_kv

        self.stacks = []

        for i in range(num_layers):
            attn = MultiHeadAttention(num_heads, d_model, d_k, d_v, residual_dropout=residual_dropout, attention_dropout=attention_dropout, d_positional=d_positional)


            if d_positional is None:
                ff = PositionwiseFeedForward(d_model, d_ff, relu_dropout=relu_dropout, residual_dropout=residual_dropout)
            else:
                ff = PartitionedPositionwiseFeedForward(d_model, d_ff, d_positional, relu_dropout=relu_dropout, residual_dropout=residual_dropout)

            self.add_module(f"attn_{i}", attn)
            self.add_module(f"ff_{i}", ff)
            self.stacks.append((attn, ff))

        if use_lal:
            lal_d_positional = d_positional if lal_partitioned else None
            attn = LabelAttention(hparams, d_model, lal_d_kv, lal_d_kv, d_l, lal_d_proj, use_resdrop=lal_resdrop,
                                  q_as_matrix=lal_q_as_matrix,
                                  residual_dropout=residual_dropout, attention_dropout=attention_dropout,
                                  d_positional=lal_d_positional)
            ff_dim = lal_d_proj * d_l
            if hparams.lal_combine_as_self:
                ff_dim = d_model
            if lal_pwff:
                if d_positional is None or not lal_partitioned:
                    ff = PositionwiseFeedForward(ff_dim, d_ff, relu_dropout=relu_dropout,
                                                 residual_dropout=residual_dropout)
                else:
                    ff = PartitionedPositionwiseFeedForward(ff_dim, d_ff, d_positional, relu_dropout=relu_dropout,
                                                            residual_dropout=residual_dropout)
            else:
                ff = None

            self.add_module(f"attn_{num_layers}", attn)
            self.add_module(f"ff_{num_layers}", ff)
            self.stacks.append((attn, ff))

        self.num_layers_position_only = num_layers_position_only
        if self.num_layers_position_only > 0:
            assert d_positional is None, "num_layers_position_only and partitioned are incompatible"

    def forward(self, xs, batch_idxs, extra_content_annotations=None):
        emb = self.embedding_container[0]
        res, timing_signal, batch_idxs = emb(xs, batch_idxs, extra_content_annotations=extra_content_annotations)

        for i, (attn, ff) in enumerate(self.stacks):
            if i >= self.num_layers_position_only:
                res, current_attns = attn(res, batch_idxs)
            else:
                res, current_attns = attn(res, batch_idxs, qk_inp=timing_signal)
            res = ff(res, batch_idxs)

        return res, current_attns#batch_idxs

# %%

class NKChartParser(nn.Module):
    # We never actually call forward() end-to-end as is typical for pytorch
    # modules, but this inheritance brings in good stuff like state dict
    # management.
    def __init__(
            self,
            tag_vocab,
            word_vocab,
            label_vocab,
            char_vocab,
            hparams,
    ):
        super().__init__()
        self.spec = locals()
        self.spec.pop("self")
        self.spec.pop("__class__")
        self.spec['hparams'] = hparams.to_dict()

        self.tag_vocab = tag_vocab
        self.word_vocab = word_vocab
        self.label_vocab = label_vocab
        self.char_vocab = char_vocab

        self.d_model = hparams.d_model
        self.partitioned = hparams.partitioned
        self.d_content = (self.d_model // 2) if self.partitioned else self.d_model
        self.d_positional = (hparams.d_model // 2) if self.partitioned else None
        # add label attention
        self.use_lal = hparams.use_lal
        if self.use_lal:
            self.lal_d_kv = hparams.lal_d_kv
            self.lal_d_proj = hparams.lal_d_proj
            self.lal_resdrop = hparams.lal_resdrop
            self.lal_pwff = hparams.lal_pwff
            self.lal_q_as_matrix = hparams.lal_q_as_matrix
            self.lal_partitioned = hparams.lal_partitioned
            self.lal_combine_as_self = hparams.lal_combine_as_self

        self.contributions = False

        num_embeddings_map = {
            'tags': tag_vocab.size,
            'words': word_vocab.size,
            'chars': char_vocab.size,
        }
        emb_dropouts_map = {
            'tags': hparams.tag_emb_dropout,
            'words': hparams.word_emb_dropout,
        }

        self.emb_types = []
        if hparams.use_tags:
            self.emb_types.append('tags')
        if hparams.use_words:
            self.emb_types.append('words')

        self.use_tags = hparams.use_tags

        self.morpho_emb_dropout = None
        if hparams.use_chars_lstm or hparams.use_elmo or hparams.use_bert or hparams.use_bert_only:
            self.morpho_emb_dropout = hparams.morpho_emb_dropout
        else:
            assert self.emb_types, "Need at least one of: use_tags, use_words, use_chars_lstm, use_elmo, use_bert, use_bert_only"

        self.char_encoder = None
        self.bert = None
        if hparams.use_chars_lstm:
            assert not hparams.use_elmo, "use_chars_lstm and use_elmo are mutually exclusive"
            assert not hparams.use_bert, "use_chars_lstm and use_bert are mutually exclusive"
            assert not hparams.use_bert_only, "use_chars_lstm and use_bert_only are mutually exclusive"
            self.char_encoder = CharacterLSTM(
                num_embeddings_map['chars'],
                hparams.d_char_emb,
                self.d_content,
                char_dropout=hparams.char_lstm_input_dropout,
            )
        elif hparams.use_bert or hparams.use_bert_only:
            self.bert_tokenizer, self.bert = get_bert(hparams.bert_model, hparams.bert_do_lower_case)
            if hparams.bert_transliterate:
                from transliterate import TRANSLITERATIONS
                self.bert_transliterate = TRANSLITERATIONS[hparams.bert_transliterate]
            else:
                self.bert_transliterate = None

            d_bert_annotations = self.bert.pooler.dense.in_features
            self.bert_max_len = self.bert.embeddings.position_embeddings.num_embeddings

            if hparams.use_bert_only:
                self.project_bert = nn.Linear(d_bert_annotations, hparams.d_model, bias=False)
            else:
                self.project_bert = nn.Linear(d_bert_annotations, self.d_content, bias=False)

        if not hparams.use_bert_only:
            self.embedding = MultiLevelEmbedding(
                [num_embeddings_map[emb_type] for emb_type in self.emb_types],
                hparams.d_model,
                d_positional=self.d_positional,
                dropout=hparams.embedding_dropout,
                timing_dropout=hparams.timing_dropout,
                emb_dropouts_list=[emb_dropouts_map[emb_type] for emb_type in self.emb_types],
                extra_content_dropout=self.morpho_emb_dropout,
                max_len=hparams.sentence_max_len,
            )
            self.encoder = Encoder(
                hparams,
                self.embedding,
                num_layers=hparams.num_layers,
                num_heads=hparams.num_heads,
                d_kv=hparams.d_kv,
                d_ff=hparams.d_ff,
                d_l= label_vocab.size - 2,
                d_positional=self.d_positional,
                relu_dropout=hparams.relu_dropout,
                residual_dropout=hparams.residual_dropout,
                attention_dropout=hparams.attention_dropout,
                use_lal=hparams.use_lal,
                lal_d_kv=hparams.lal_d_kv,
                lal_d_proj=hparams.lal_d_proj,
                lal_resdrop=hparams.lal_resdrop,
                lal_pwff=hparams.lal_pwff,
                lal_q_as_matrix=hparams.lal_q_as_matrix,
                lal_partitioned=hparams.lal_partitioned,
            )
        else:
            self.embedding = None
            self.encoder = None
        annotation_dim = ((label_vocab.size - 2) * self.lal_d_proj) if (
                    self.use_lal and not self.lal_combine_as_self) else hparams.d_model
        hparams.annotation_dim = annotation_dim
        self.f_label = nn.Sequential(
            nn.Linear(annotation_dim, hparams.d_label_hidden),
            LayerNormalization(hparams.d_label_hidden),
            nn.ReLU(),
            nn.Linear(hparams.d_label_hidden, label_vocab.size - 1),
            )

        if hparams.predict_tags:
            assert not hparams.use_tags, "use_tags and predict_tags are mutually exclusive"
            self.f_tag = nn.Sequential(
                nn.Linear(hparams.d_model, hparams.d_tag_hidden),
                LayerNormalization(hparams.d_tag_hidden),
                nn.ReLU(),
                nn.Linear(hparams.d_tag_hidden, tag_vocab.size),
                )
            self.tag_loss_scale = hparams.tag_loss_scale
        else:
            self.f_tag = None

        if use_cuda:
            self.cuda()

    @property
    def model(self):
        return self.state_dict()

    @classmethod
    def from_spec(cls, spec, model):
        spec = spec.copy()
        hparams = spec['hparams']
        if 'use_chars_concat' in hparams and hparams['use_chars_concat']:
            raise NotImplementedError("Support for use_chars_concat has been removed")
        if 'sentence_max_len' not in hparams:
            hparams['sentence_max_len'] = 300
        if 'use_elmo' not in hparams:
            hparams['use_elmo'] = False
        if 'elmo_dropout' not in hparams:
            hparams['elmo_dropout'] = 0.5
        if 'use_bert' not in hparams:
            hparams['use_bert'] = False
        if 'use_bert_only' not in hparams:
            hparams['use_bert_only'] = False
        if 'predict_tags' not in hparams:
            hparams['predict_tags'] = False
        if 'bert_transliterate' not in hparams:
            hparams['bert_transliterate'] = ""

        spec['hparams'] = nkutil.HParams(**hparams)
        res = cls(**spec)
        if use_cuda:
            res.cpu()
        if not hparams['use_elmo']:
            res.load_state_dict(model)
        else:
            state = {k: v for k,v in res.state_dict().items() if k not in model}
            state.update(model)
            res.load_state_dict(state)
        if use_cuda:
            res.cuda()
        return res

    def split_batch(self, sentences, golds, subbatch_max_tokens=3000):
        if self.bert is not None:
            lens = [
                len(self.bert_tokenizer.tokenize(' '.join([word for (_, word) in sentence]))) + 2
                for sentence in sentences
            ]
        else:
            lens = [len(sentence) + 2 for sentence in sentences]

        lens = np.asarray(lens, dtype=int)
        lens_argsort = np.argsort(lens).tolist()

        num_subbatches = 0
        subbatch_size = 1
        while lens_argsort:
            if (subbatch_size == len(lens_argsort)) or (subbatch_size * lens[lens_argsort[subbatch_size]] > subbatch_max_tokens):
                yield [sentences[i] for i in lens_argsort[:subbatch_size]], [golds[i] for i in lens_argsort[:subbatch_size]]
                lens_argsort = lens_argsort[subbatch_size:]
                num_subbatches += 1
                subbatch_size = 1
            else:
                subbatch_size += 1

    def parse(self, sentence, gold=None):
        tree_list, loss_list = self.parse_batch([sentence], [gold] if gold is not None else None)
        return tree_list[0], loss_list[0]

    def parse_batch(self, sentences, golds=None, return_label_scores_charts=False):
        is_train = golds is not None
        self.train(is_train)
        torch.set_grad_enabled(is_train)

        if golds is None:
            golds = [None] * len(sentences)

        packed_len = sum([(len(sentence) + 2) for sentence in sentences])

        i = 0
        tag_idxs = np.zeros(packed_len, dtype=int)
        word_idxs = np.zeros(packed_len, dtype=int)
        batch_idxs = np.zeros(packed_len, dtype=int)
        for snum, sentence in enumerate(sentences):
            for (tag, word) in [(START, START)] + sentence + [(STOP, STOP)]:
                tag_idxs[i] = 0 if (not self.use_tags and self.f_tag is None) else self.tag_vocab.index_or_unk(tag, TAG_UNK)
                if word not in (START, STOP):
                    count = self.word_vocab.count(word)
                    if not count or (is_train and np.random.rand() < 1 / (1 + count)):
                        word = UNK
                word_idxs[i] = self.word_vocab.index(word)
                batch_idxs[i] = snum
                i += 1
        assert i == packed_len

        batch_idxs = BatchIndices(batch_idxs)

        emb_idxs_map = {
            'tags': tag_idxs,
            'words': word_idxs,
        }
        emb_idxs = [
            from_numpy(emb_idxs_map[emb_type])
            for emb_type in self.emb_types
            ]

        if is_train and self.f_tag is not None:
            gold_tag_idxs = from_numpy(emb_idxs_map['tags'])

        extra_content_annotations = None
        if self.char_encoder is not None:
            assert isinstance(self.char_encoder, CharacterLSTM)
            max_word_len = max([max([len(word) for tag, word in sentence]) for sentence in sentences])
            # Add 2 for start/stop tokens
            max_word_len = max(max_word_len, 3) + 2
            char_idxs_encoder = np.zeros((packed_len, max_word_len), dtype=int)
            word_lens_encoder = np.zeros(packed_len, dtype=int)

            i = 0
            for snum, sentence in enumerate(sentences):
                for wordnum, (tag, word) in enumerate([(START, START)] + sentence + [(STOP, STOP)]):
                    j = 0
                    char_idxs_encoder[i, j] = self.char_vocab.index(CHAR_START_WORD)
                    j += 1
                    if word in (START, STOP):
                        char_idxs_encoder[i, j:j+3] = self.char_vocab.index(
                            CHAR_START_SENTENCE if (word == START) else CHAR_STOP_SENTENCE
                            )
                        j += 3
                    else:
                        for char in word:
                            char_idxs_encoder[i, j] = self.char_vocab.index_or_unk(char, CHAR_UNK)
                            j += 1
                    char_idxs_encoder[i, j] = self.char_vocab.index(CHAR_STOP_WORD)
                    word_lens_encoder[i] = j + 1
                    i += 1
            assert i == packed_len

            extra_content_annotations = self.char_encoder(char_idxs_encoder, word_lens_encoder, batch_idxs)

        elif self.bert is not None:
            all_input_ids = np.zeros((len(sentences), self.bert_max_len), dtype=int)
            all_input_mask = np.zeros((len(sentences), self.bert_max_len), dtype=int)
            all_word_start_mask = np.zeros((len(sentences), self.bert_max_len), dtype=int)
            all_word_end_mask = np.zeros((len(sentences), self.bert_max_len), dtype=int)

            subword_max_len = 0
            for snum, sentence in enumerate(sentences):
                tokens = []
                word_start_mask = []
                word_end_mask = []

                tokens.append("[CLS]")
                word_start_mask.append(1)
                word_end_mask.append(1)

                if self.bert_transliterate is None:
                    cleaned_words = []
                    for _, word in sentence:
                        word = BERT_TOKEN_MAPPING.get(word, word)
                        # This un-escaping for / and * was not yet added for the
                        # parser version in https://arxiv.org/abs/1812.11760v1
                        # and related model releases (e.g. benepar_en2)
                        word = word.replace('\\/', '/').replace('\\*', '*')
                        # Mid-token punctuation occurs in biomedical text
                        word = word.replace('-LSB-', '[').replace('-RSB-', ']')
                        word = word.replace('-LRB-', '(').replace('-RRB-', ')')
                        if word == "n't" and cleaned_words:
                            cleaned_words[-1] = cleaned_words[-1] + "n"
                            word = "'t"
                        cleaned_words.append(word)
                else:
                    # When transliterating, assume that the token mapping is
                    # taken care of elsewhere
                    cleaned_words = [self.bert_transliterate(word) for _, word in sentence]

                for word in cleaned_words:
                    word_tokens = self.bert_tokenizer.tokenize(word)
                    for _ in range(len(word_tokens)):
                        word_start_mask.append(0)
                        word_end_mask.append(0)
                    word_start_mask[len(tokens)] = 1
                    word_end_mask[-1] = 1
                    tokens.extend(word_tokens)
                tokens.append("[SEP]")
                word_start_mask.append(1)
                word_end_mask.append(1)

                input_ids = self.bert_tokenizer.convert_tokens_to_ids(tokens)

                # The mask has 1 for real tokens and 0 for padding tokens. Only real
                # tokens are attended to.
                input_mask = [1] * len(input_ids)

                subword_max_len = max(subword_max_len, len(input_ids))

                all_input_ids[snum, :len(input_ids)] = input_ids
                all_input_mask[snum, :len(input_mask)] = input_mask
                all_word_start_mask[snum, :len(word_start_mask)] = word_start_mask
                all_word_end_mask[snum, :len(word_end_mask)] = word_end_mask

            all_input_ids = from_numpy(np.ascontiguousarray(all_input_ids[:, :subword_max_len]))
            all_input_mask = from_numpy(np.ascontiguousarray(all_input_mask[:, :subword_max_len]))
            all_word_start_mask = from_numpy(np.ascontiguousarray(all_word_start_mask[:, :subword_max_len]))
            all_word_end_mask = from_numpy(np.ascontiguousarray(all_word_end_mask[:, :subword_max_len]))
            all_encoder_layers, _ = self.bert(all_input_ids, attention_mask=all_input_mask)
            del _
            features = all_encoder_layers[-1]

            if self.encoder is not None:
                features_packed = features.masked_select(all_word_end_mask.to(DTYPE).unsqueeze(-1)).reshape(-1, features.shape[-1])

                # For now, just project the features from the last word piece in each word
                extra_content_annotations = self.project_bert(features_packed)

        if self.encoder is not None:
            annotations, self.current_attns = self.encoder(emb_idxs, batch_idxs, extra_content_annotations=extra_content_annotations)

            if self.partitioned and not self.use_lal:
                # Rearrange the annotations to ensure that the transition to
                # fenceposts captures an even split between position and content.
                # TODO(nikita): try alternatives, such as omitting position entirely
                annotations = torch.cat([
                    annotations[:, 0::2],
                    annotations[:, 1::2],
                ], 1)
            if self.use_lal and not self.lal_combine_as_self:
                half_dim = self.lal_d_proj // 2
                d_l = self.label_vocab.size - 1
                fencepost_annotations = torch.cat(
                    [annotations[:-1, (i * self.lal_d_proj):(i * self.lal_d_proj + half_dim)] for i in range(d_l)]
                    + [annotations[1:, (i * self.lal_d_proj + half_dim):((i + 1) * self.lal_d_proj)] for i in
                       range(d_l)], 1)
            else:
                fencepost_annotations = torch.cat([
                    annotations[:-1, :self.d_model // 2],
                    annotations[1:, self.d_model // 2:],
                ], 1)

            if self.f_tag is not None:
                tag_annotations = annotations

            # fencepost_annotations = torch.cat([
            #     annotations[:-1, :self.d_model//2],
            #     annotations[1:, self.d_model//2:],
            #     ], 1)
            fencepost_annotations_start = fencepost_annotations
            fencepost_annotations_end = fencepost_annotations
        else:
            assert self.bert is not None
            features = self.project_bert(features)
            fencepost_annotations_start = features.masked_select(all_word_start_mask.to(DTYPE).unsqueeze(-1)).reshape(-1, features.shape[-1])
            fencepost_annotations_end = features.masked_select(all_word_end_mask.to(DTYPE).unsqueeze(-1)).reshape(-1, features.shape[-1])
            if self.f_tag is not None:
                tag_annotations = fencepost_annotations_end

        if self.f_tag is not None:
            tag_logits = self.f_tag(tag_annotations)
            if is_train:
                tag_loss = self.tag_loss_scale * nn.functional.cross_entropy(tag_logits, gold_tag_idxs, reduction='sum')

        # Note that the subtraction above creates fenceposts at sentence
        # boundaries, which are not used by our parser. Hence subtract 1
        # when creating fp_endpoints
        fp_startpoints = batch_idxs.boundaries_np[:-1]
        fp_endpoints = batch_idxs.boundaries_np[1:] - 1

        # Just return the charts, for ensembling
        if return_label_scores_charts:
            charts = []
            for i, (start, end) in enumerate(zip(fp_startpoints, fp_endpoints)):
                chart = self.label_scores_from_annotations(fencepost_annotations_start[start:end,:], fencepost_annotations_end[start:end,:])
                charts.append(chart.cpu().data.numpy())
            return charts

        if not is_train:
            trees = []
            scores = []
            if self.f_tag is not None:
                # Note that tag_logits includes tag predictions for start/stop tokens
                tag_idxs = torch.argmax(tag_logits, -1).cpu()
                per_sentence_tag_idxs = torch.split_with_sizes(tag_idxs, [len(sentence) + 2 for sentence in sentences])
                per_sentence_tags = [[self.tag_vocab.value(idx) for idx in idxs[1:-1]] for idxs in per_sentence_tag_idxs]

            for i, (start, end) in enumerate(zip(fp_startpoints, fp_endpoints)):
                sentence = sentences[i]
                if self.f_tag is not None:
                    sentence = list(zip(per_sentence_tags[i], [x[1] for x in sentence]))
                tree, score = self.parse_from_annotations(fencepost_annotations_start[start:end,:], fencepost_annotations_end[start:end,:], sentence, golds[i])
                trees.append(tree)
                scores.append(score)
            return trees, scores

        # During training time, the forward pass needs to be computed for every
        # cell of the chart, but the backward pass only needs to be computed for
        # cells in either the predicted or the gold parse tree. It's slightly
        # faster to duplicate the forward pass for a subset of the chart than it
        # is to perform a backward pass that doesn't take advantage of sparsity.
        # Since this code is not undergoing algorithmic changes, it makes sense
        # to include the optimization even though it may only be a 10% speedup.
        # Note that no dropout occurs in the label portion of the network
        pis = []
        pjs = []
        plabels = []
        paugment_total = 0.0
        num_p = 0
        gis = []
        gjs = []
        glabels = []
        with torch.no_grad():
            for i, (start, end) in enumerate(zip(fp_startpoints, fp_endpoints)):
                p_i, p_j, p_label, p_augment, g_i, g_j, g_label = self.parse_from_annotations(fencepost_annotations_start[start:end,:], fencepost_annotations_end[start:end,:], sentences[i], golds[i])
                paugment_total += p_augment
                num_p += p_i.shape[0]
                pis.append(p_i + start)
                pjs.append(p_j + start)
                gis.append(g_i + start)
                gjs.append(g_j + start)
                plabels.append(p_label)
                glabels.append(g_label)

        cells_i = from_numpy(np.concatenate(pis + gis))
        cells_j = from_numpy(np.concatenate(pjs + gjs))
        cells_label = from_numpy(np.concatenate(plabels + glabels))

        cells_label_scores = self.f_label(fencepost_annotations_end[cells_j] - fencepost_annotations_start[cells_i])
        cells_label_scores = torch.cat([
                    cells_label_scores.new_zeros((cells_label_scores.size(0), 1)),
                    cells_label_scores
                    ], 1)
        cells_scores = torch.gather(cells_label_scores, 1, cells_label[:, None])
        loss = cells_scores[:num_p].sum() - cells_scores[num_p:].sum() + paugment_total

        if self.f_tag is not None:
            return None, (loss, tag_loss)
        else:
            return None, loss

    def label_scores_from_annotations1(self, fencepost_annotations_start, fencepost_annotations_end):
        # Note that the bias added to the final layer norm is useless because
        # this subtraction gets rid of it
        span_features = (torch.unsqueeze(fencepost_annotations_end, 0)
                         - torch.unsqueeze(fencepost_annotations_start, 1))

        label_scores_chart = self.f_label(span_features)
        label_scores_chart = torch.cat([
            label_scores_chart.new_zeros((label_scores_chart.size(0), label_scores_chart.size(1), 1)),
            label_scores_chart
            ], 2)
        return label_scores_chart

    def label_scores_from_annotations_backup(self, fencepost_annotations_start, fencepost_annotations_end):

        span_features = (torch.unsqueeze(fencepost_annotations_end, 0)
                         - torch.unsqueeze(fencepost_annotations_start, 1))

        # if self.contributions and self.use_lal:
        # contributions = np.zeros(
        #     (span_features.shape[0], span_features.shape[1], span_features.shape[2] // self.lal_d_proj))
        contributions = np.zeros(
            (span_features.shape[0], span_features.shape[1], span_features.shape[2] // 128))
        half_vector = span_features.shape[-1] // 2
        # half_dim = self.lal_d_proj // 2
        half_dim = 64
        for i in range(contributions.shape[0]):
            for j in range(contributions.shape[1]):
                for l in range(contributions.shape[-1]):
                    contributions[i, j, l] = span_features[i, j,
                                             l * half_dim:(l + 1) * half_dim].sum() + span_features[i, j,
                                                                                      half_vector + l * half_dim:half_vector + (
                                                                                                  l + 1) * half_dim].sum()
                contributions[i, j, :] = (contributions[i, j, :] - np.min(contributions[i, j, :]))
                contributions[i, j, :] = (contributions[i, j, :]) / (
                            np.max(contributions[i, j, :]) - np.min(contributions[i, j, :]))
                # contributions[i,j,:] = contributions[i,j,:]/np.sum(contributions[i,j,:])
        contributions = torch.softmax(torch.Tensor(contributions), -1)

        label_scores_chart = self.f_label(span_features)
        label_scores_chart = torch.cat([
            label_scores_chart.new_zeros((label_scores_chart.size(0), label_scores_chart.size(1), 1)),
            label_scores_chart
        ], 2)
        # if self.contributions and self.use_lal:
        #     return label_scores_chart, contributions
        return label_scores_chart

    def label_scores_from_annotations(self, fencepost_annotations_start, fencepost_annotations_end):

        span_features = (torch.unsqueeze(fencepost_annotations_end, 0)
                         - torch.unsqueeze(fencepost_annotations_start, 1))

        if self.contributions and self.use_lal:
            contributions = np.zeros(
                (span_features.shape[0], span_features.shape[1], span_features.shape[2] // self.lal_d_proj))
            half_vector = span_features.shape[-1] // 2
            half_dim = self.lal_d_proj // 2
            for i in range(contributions.shape[0]):
                for j in range(contributions.shape[1]):
                    for l in range(contributions.shape[-1]):
                        contributions[i, j, l] = span_features[i, j,
                                                 l * half_dim:(l + 1) * half_dim].sum() + span_features[i, j,
                                                                                          half_vector + l * half_dim:half_vector + (
                                                                                                      l + 1) * half_dim].sum()
                    contributions[i, j, :] = (contributions[i, j, :] - np.min(contributions[i, j, :]))
                    contributions[i, j, :] = (contributions[i, j, :]) / (
                                np.max(contributions[i, j, :]) - np.min(contributions[i, j, :]))
                    # contributions[i,j,:] = contributions[i,j,:]/np.sum(contributions[i,j,:])
            contributions = torch.softmax(torch.Tensor(contributions), -1)

        label_scores_chart = self.f_label(span_features)
        label_scores_chart = torch.cat([
            label_scores_chart.new_zeros((label_scores_chart.size(0), label_scores_chart.size(1), 1)),
            label_scores_chart
        ], 2)
        if self.contributions and self.use_lal:
            return label_scores_chart, contributions
        return label_scores_chart

    def parse_from_annotations(self, fencepost_annotations_start, fencepost_annotations_end, sentence, gold=None):
        is_train = gold is not None
        label_scores_chart = self.label_scores_from_annotations(fencepost_annotations_start, fencepost_annotations_end)
        label_scores_chart_np = label_scores_chart.cpu().data.numpy()

        if is_train:
            decoder_args = dict(
                sentence_len=len(sentence),
                label_scores_chart=label_scores_chart_np,
                gold=gold,
                label_vocab=self.label_vocab,
                is_train=is_train)

            p_score, p_i, p_j, p_label, p_augment = chart_helper.decode(False, **decoder_args)
            g_score, g_i, g_j, g_label, g_augment = chart_helper.decode(True, **decoder_args)
            return p_i, p_j, p_label, p_augment, g_i, g_j, g_label
        else:
            return self.decode_from_chart(sentence, label_scores_chart_np)

    def decode_from_chart_batch(self, sentences, charts_np, golds=None):
        trees = []
        scores = []
        if golds is None:
            golds = [None] * len(sentences)
        for sentence, chart_np, gold in zip(sentences, charts_np, golds):
            tree, score = self.decode_from_chart(sentence, chart_np, gold)
            trees.append(tree)
            scores.append(score)
        return trees, scores

    def decode_from_chart(self, sentence, chart_np, gold=None, contributions=None,  sentence_idx=None):
        decoder_args = dict(
            sentence_len=len(sentence),
            label_scores_chart=chart_np,
            gold=gold,
            label_vocab=self.label_vocab,
            is_train=False)

        force_gold = (gold is not None)

        # The optimized cython decoder implementation doesn't actually
        # generate trees, only scores and span indices. When converting to a
        # tree, we assume that the indices follow a preorder traversal.
        score, p_i, p_j, p_label, _ = chart_helper.decode(force_gold, **decoder_args)
        if contributions is not None:
            d_l = (self.label_vocab.size - 2)
            mb_size = (self.current_attns.shape[0] // d_l)
            print('SENTENCE', sentence)
        idx = -1
        def make_tree():
            nonlocal idx
            idx += 1
            i, j, label_idx = p_i[idx], p_j[idx], p_label[idx]
            label = self.label_vocab.value(label_idx)
            if contributions is not None:
                if label_idx > 0:
                    print(i, sentence[i], j, sentence[j - 1], label, label_idx, contributions[i, j, label_idx - 1])
                    print("CONTRIBUTIONS")
                    print(list(enumerate(contributions[i, j])))
                    print("ATTENTION DIST")
                    print(torch.softmax(self.current_attns[sentence_idx::mb_size, 0, i:j + 1], -1))
            if (i + 1) >= j:
                tag, word = sentence[i]
                tree = trees.LeafParseNode(int(i), tag, word)
                if label:
                    tree = trees.InternalParseNode(label, [tree])
                return [tree]
            else:
                left_trees = make_tree()
                right_trees = make_tree()
                children = left_trees + right_trees
                if label:
                    return [trees.InternalParseNode(label, children)]
                else:
                    return children

        tree = make_tree()[0]
        return tree, score


