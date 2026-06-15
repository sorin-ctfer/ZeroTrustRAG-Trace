<script setup lang="ts">
import { ref } from 'vue'
import { api, unwrap } from '@/api'
import GraphChart from '@/components/GraphChart.vue'
import { useAsyncTask } from '@/composables/useAsyncTask'
const result = ref<any>()
const { loading, error, execute } = useAsyncTask()
const run = async () => {
  const data = await execute(async () => {
    await api.post('/agents/run-demo', { case_id: 'case_threat_intel_false_consensus' })
    return unwrap(await api.post('/detect/cascade', { case_id: 'case_threat_intel_false_consensus' }))
  })
  if (data) result.value = data
}
</script>
<template>
  <div class="page-head"><h1>级联错误检测</h1><p>检测错误 Claim 的传播、伪多数共识、语义漂移、影响力与 Byzantine 可疑度。</p></div>
  <el-alert v-if="error" class="error-alert" type="error" :title="error" show-icon :closable="false" />
  <section class="panel"><el-button type="primary" :loading="loading" @click="run">运行级联检测</el-button></section>
  <template v-if="result">
    <div class="stat-grid">
      <div class="stat-card"><div class="label">False Consensus Rate</div><div class="value">{{ result.false_consensus_rate }}</div></div>
      <div class="stat-card"><div class="label">Drift Velocity</div><div class="value">{{ result.drift_velocity }}</div></div>
      <div class="stat-card"><div class="label">高风险 Claim</div><div class="value">{{ result.high_risk_claims.length }}</div></div>
      <div class="stat-card"><div class="label">可疑 Agent</div><div class="value">{{ result.suspicious_agents.length }}</div></div>
    </div>
    <section v-loading="loading" class="panel"><GraphChart :graph="result.graph" /></section>
    <section class="panel two-col"><div><h2 class="panel-title">Propagation Factor</h2><el-descriptions border :column="1"><el-descriptions-item v-for="(v,k) in result.propagation_factor" :key="k" :label="String(k)">{{ v }}</el-descriptions-item></el-descriptions></div><div><h2 class="panel-title">Byzantine Suspicion Score</h2><el-descriptions border :column="1"><el-descriptions-item v-for="(v,k) in result.byzantine_suspicion_score" :key="k" :label="String(k)">{{ v }}</el-descriptions-item></el-descriptions></div></section>
  </template>
</template>
