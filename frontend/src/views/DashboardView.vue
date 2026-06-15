<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api, unwrap } from '@/api'

const stats = ref<Record<string, number>>({})
const cards = [
  ['evidence_count', 'Evidence 数量'], ['chunk_count', 'Chunk 数量'],
  ['agent_count', 'Agent 数量'], ['claim_count', 'Claim 数量'],
  ['high_risk_evidence_count', '高风险证据'], ['high_risk_agent_count', '高风险 Agent'],
  ['average_trust_score', '平均 TrustScore'],
]
const capabilities = [
  ['多 Agent 零信任声明链', '对身份、权限、证据引用、父声明和签名逐项验证。'],
  ['RAG 知识投毒检测', '以 RAS、GIS 和 DualRisk 识别异常吸附与答案诱导。'],
  ['反事实因果验证', '通过原始、删除、仅可疑、可信替代四路结果计算因果贡献。'],
  ['信息污染联合溯源图谱', '贯通 Evidence、Claim、Consensus 和 Action 四层传播链。'],
  ['TrustScore 可信评分', '融合证据覆盖、来源独立性、投毒和因果风险。'],
  ['可信重生成', '隔离污染证据后重检索，并输出带 Evidence 引用的保守答案。'],
]
onMounted(async () => { stats.value = unwrap(await api.get('/dashboard/stats')) })
</script>

<template>
  <div class="page-head"><h1>系统仪表盘</h1><p>多 Agent 零信任协同与 RAG 知识投毒因果验证的完整演示入口。</p></div>
  <div class="stat-grid">
    <div v-for="[key, label] in cards" :key="key" class="stat-card">
      <div class="label">{{ label }}</div><div class="value">{{ stats[key] ?? 0 }}</div>
    </div>
  </div>
  <section class="panel">
    <h2 class="panel-title">核心能力</h2>
    <div class="cap-grid"><div v-for="[title, text] in capabilities" :key="title" class="cap-card"><strong>{{ title }}</strong><span>{{ text }}</span></div></div>
  </section>
</template>
