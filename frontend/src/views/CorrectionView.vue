<script setup lang="ts">
import { ref } from 'vue'
import { api, unwrap } from '@/api'
const cases = [
  ['case_enterprise_policy_approval', '企业制度知识投毒'],
  ['case_threat_intel_false_consensus', '安全情报错误共识'],
  ['case_prompt_infection', 'Prompt Infection'],
]
const caseId = ref(cases[0][0]), result = ref<any>(), loading = ref(false)
const run = async () => { loading.value = true; try { result.value = unwrap(await api.post('/correction/run', { case_id: caseId.value })) } finally { loading.value = false } }
</script>
<template>
  <div class="page-head"><h1>可信纠偏</h1><p>隔离 Chunk、降权 Agent、回滚 Claim、重检索并形成 Evidence-backed BFT Consensus。</p></div>
  <section class="panel"><div class="toolbar"><el-select v-model="caseId" style="width: 360px"><el-option v-for="[id,name] in cases" :key="id" :label="name" :value="id" /></el-select><el-button type="primary" :loading="loading" @click="run">一键执行纠偏</el-button></div></section>
  <template v-if="result">
    <div class="stat-grid"><div class="stat-card"><div class="label">纠偏前 TrustScore</div><div class="value">{{ result.trust_score.before }}</div></div><div class="stat-card"><div class="label">纠偏后 TrustScore</div><div class="value">{{ result.trust_score.after }}</div></div><div class="stat-card"><div class="label">提升</div><div class="value">+{{ result.before_after_comparison.improvement }}</div></div><div class="stat-card"><div class="label">隔离证据</div><div class="value">{{ result.suspicious_evidence.length }}</div></div></div>
    <section class="panel two-col"><div><h2 class="panel-title">纠偏动作</h2><el-timeline><el-timeline-item v-for="item in result.correction_actions" :key="item">{{ item }}</el-timeline-item></el-timeline></div><div><h2 class="panel-title">BFT 加权声明</h2><el-table :data="result.bft_consensus"><el-table-column prop="claim_id" label="Claim" /><el-table-column prop="weight" label="Weight" /><el-table-column prop="content" label="内容" show-overflow-tooltip /></el-table></div></section>
    <section class="panel"><h2 class="panel-title">可信重生成结果</h2><div class="answer-box">{{ result.trusted_answer }}</div></section>
  </template>
</template>
