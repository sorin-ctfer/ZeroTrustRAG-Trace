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
    return unwrap(await api.post('/trace/ipjg', { case_id: 'case_threat_intel_false_consensus' }))
  })
  if (data) result.value = data
}
</script>
<template>
  <div class="page-head"><h1>信息污染联合溯源</h1><p>IPJG 四层图谱从错误 Action 反向追踪 Consensus、Claim、Evidence 与 Chunk。</p></div>
  <el-alert v-if="error" class="error-alert" type="error" :title="error" show-icon :closable="false" />
  <section class="panel"><el-button type="primary" :loading="loading" @click="run">构建 IPJG 图谱</el-button></section>
  <section v-if="result" v-loading="loading" class="panel"><GraphChart :graph="result" /></section>
  <section v-if="result" class="panel two-col">
    <div><h2 class="panel-title">溯源结论</h2><p><b>污染源：</b>{{ result.pollution_sources.join(', ') }}</p><p><b>受影响 Claim：</b>{{ result.affected_claims.join(', ') }}</p><p><b>可疑 Agent：</b>{{ result.suspicious_agents.join(', ') }}</p><p>{{ result.risk_explanation }}</p></div>
    <div><h2 class="panel-title">建议动作</h2><el-timeline><el-timeline-item v-for="item in result.recommended_actions" :key="item">{{ item }}</el-timeline-item></el-timeline></div>
  </section>
</template>
