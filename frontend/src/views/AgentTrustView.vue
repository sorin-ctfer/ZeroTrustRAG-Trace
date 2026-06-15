<script setup lang="ts">
import { ref } from 'vue'
import { api, unwrap } from '@/api'
import GraphChart from '@/components/GraphChart.vue'
import { useAsyncTask } from '@/composables/useAsyncTask'

const caseId = ref('case_threat_intel_false_consensus'), result = ref<any>()
const { loading, error, execute } = useAsyncTask()
const run = async () => {
  const data = await execute(async () => unwrap(await api.post('/agents/run-demo', { case_id: caseId.value })))
  if (data) result.value = data
}
</script>
<template>
  <div class="page-head"><h1>多 Agent 零信任协同</h1><p>每条 Claim 均封装身份、权限、Evidence、父声明、签名和风险状态。</p></div>
  <el-alert v-if="error" class="error-alert" type="error" :title="error" show-icon :closable="false" />
  <section class="panel"><el-button type="primary" :loading="loading" @click="run">运行六 Agent 演示</el-button></section>
  <section v-if="result" v-loading="loading" class="panel"><GraphChart :graph="result.graph" /></section>
  <section v-if="result" class="panel">
    <el-table :data="result.claims" stripe>
      <el-table-column prop="claim_id" label="Claim" width="100" /><el-table-column prop="agent_name" label="Agent" width="170" />
      <el-table-column prop="role" label="角色" width="110" /><el-table-column prop="content" label="声明" min-width="300" show-overflow-tooltip />
      <el-table-column label="Evidence" width="150"><template #default="{ row }">{{ row.evidence_ids?.join(', ') || '无' }}</template></el-table-column>
      <el-table-column prop="risk_score" label="风险" width="80" />
      <el-table-column label="风险等级" width="100"><template #default="{ row }"><el-tag :type="row.risk_score >= .6 ? 'danger' : row.risk_score >= .3 ? 'warning' : 'success'">{{ row.risk_score >= .6 ? '高' : row.risk_score >= .3 ? '中' : '低' }}</el-tag></template></el-table-column>
      <el-table-column label="零信任状态" width="120"><template #default="{ row }"><el-tag :type="row.trust_status === 'trusted' ? 'success' : 'danger'">{{ row.trust_status }}</el-tag></template></el-table-column>
    </el-table>
  </section>
</template>
