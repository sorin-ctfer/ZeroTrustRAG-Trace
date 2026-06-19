"""Train and run a small GAT model for poisoning propagation graphs.

This script is executed by the Windows Conda PyTorch environment. It is kept
Python 3.6 compatible because the local pytorch env uses Python 3.6.
"""

import json
import sys

import torch
import torch.nn as nn
import torch.nn.functional as F


class GraphAttentionLayer(nn.Module):
    def __init__(self, in_features, out_features, dropout=0.15, alpha=0.2):
        super(GraphAttentionLayer, self).__init__()
        self.dropout = dropout
        self.weight = nn.Parameter(torch.empty(size=(in_features, out_features)))
        self.attn_src = nn.Parameter(torch.empty(size=(out_features, 1)))
        self.attn_dst = nn.Parameter(torch.empty(size=(out_features, 1)))
        self.leakyrelu = nn.LeakyReLU(alpha)
        nn.init.xavier_uniform_(self.weight.data, gain=1.414)
        nn.init.xavier_uniform_(self.attn_src.data, gain=1.414)
        nn.init.xavier_uniform_(self.attn_dst.data, gain=1.414)

    def forward(self, features, adjacency):
        h = torch.mm(features, self.weight)
        src_score = torch.mm(h, self.attn_src)
        dst_score = torch.mm(h, self.attn_dst)
        e = self.leakyrelu(src_score + dst_score.t())
        zero_vec = -9e15 * torch.ones_like(e)
        attention = torch.where(adjacency > 0, e, zero_vec)
        attention = F.softmax(attention, dim=1)
        attention = F.dropout(attention, self.dropout, training=self.training)
        return torch.mm(attention, h), attention


class PoisonGAT(nn.Module):
    def __init__(self, in_features, hidden=16, classes=2):
        super(PoisonGAT, self).__init__()
        self.gat1 = GraphAttentionLayer(in_features, hidden)
        self.out = GraphAttentionLayer(hidden, classes)

    def forward(self, features, adjacency):
        h, attn1 = self.gat1(features, adjacency)
        h = F.elu(h)
        logits, attn2 = self.out(h, adjacency)
        return logits, attn1, attn2


def normalize_features(rows):
    features = torch.tensor(rows, dtype=torch.float32)
    if features.numel() == 0:
        return features
    mean = features.mean(dim=0, keepdim=True)
    std = features.std(dim=0, keepdim=True)
    std = torch.where(std < 1e-6, torch.ones_like(std), std)
    return (features - mean) / std


def main(input_path, output_path):
    with open(input_path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    nodes = payload["nodes"]
    edges = payload["edges"]
    n = len(nodes)
    if n == 0:
        raise ValueError("empty graph")

    id_to_idx = dict((node["id"], idx) for idx, node in enumerate(nodes))
    adjacency = torch.eye(n, dtype=torch.float32)
    for edge in edges:
        source = id_to_idx.get(edge.get("source"))
        target = id_to_idx.get(edge.get("target"))
        if source is None or target is None:
            continue
        weight = float(edge.get("weight", 1.0))
        adjacency[source, target] = max(float(adjacency[source, target]), weight)
        adjacency[target, source] = max(float(adjacency[target, source]), weight)

    features = normalize_features([node["features"] for node in nodes])
    labels = torch.tensor([int(node.get("label", -1)) for node in nodes], dtype=torch.long)
    train_mask = labels >= 0
    if int(train_mask.sum()) < 2 or len(set(labels[train_mask].tolist())) < 2:
        raise ValueError("GAT requires at least one positive and one negative labelled node")

    torch.manual_seed(7)
    model = PoisonGAT(features.shape[1])
    optimizer = torch.optim.Adam(model.parameters(), lr=0.012, weight_decay=5e-4)
    model.train()
    for _ in range(int(payload.get("epochs", 90))):
        optimizer.zero_grad()
        logits, _, _ = model(features, adjacency)
        loss = F.cross_entropy(logits[train_mask], labels[train_mask])
        loss.backward()
        optimizer.step()

    model.eval()
    with torch.no_grad():
        logits, attn1, attn2 = model(features, adjacency)
        probs = F.softmax(logits, dim=1)[:, 1].cpu().tolist()
        attention = ((attn1 + attn2) / 2.0).cpu()

    attention_edges = []
    for edge in edges:
        source = id_to_idx.get(edge.get("source"))
        target = id_to_idx.get(edge.get("target"))
        if source is None or target is None:
            continue
        attention_edges.append({
            "source": edge.get("source"),
            "target": edge.get("target"),
            "attention": round(float(attention[source, target]), 6),
        })

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({
            "method": "dynamic_pytorch_gat",
            "node_scores": dict((nodes[idx]["id"], round(float(score), 6)) for idx, score in enumerate(probs)),
            "attention_edges": attention_edges,
        }, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
