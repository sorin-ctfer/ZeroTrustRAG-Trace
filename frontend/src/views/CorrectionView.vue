<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api, unwrap } from '@/api'
import ScoreComparisonChart from '@/components/ScoreComparisonChart.vue'
import { useAsyncTask } from '@/composables/useAsyncTask'
const cases = ref<any[]>([])
const caseId = ref('case_enterprise_policy_approval'), result = ref<any>()
const { loading, error, execute } = useAsyncTask()
const run = async () => {
  const data = await execute(async () => unwrap(await api.post('/correction/run', { case_id: caseId.value })))
  if (data) result.value = data
}
onMounted(async () => {
  const data = await execute(async () => unwrap<any[]>(await api.get('/rag/cases')))
  if (data) cases.value = data.filter(item => item.poisoned_count > 0)
})
</script>
<template>
  <div class="page-head"><h1>可信纠偏</h1><p>隔离 Chunk、降权 Agent、回滚 Claim、重检索并形成 Evidence-backed BFT Consensus。</p></div>
  <el-alert v-if="error" class="error-alert" type="error" :title="error" show-icon :closable="false" />
  <section class="panel"><div class="toolbar"><el-select v-model="caseId" style="width: 420px"><el-option v-for="item in cases" :key="item.case_id" :label="item.title" :value="item.case_id" /></el-select><el-button type="primary" :loading="loading" @click="run">一键执行纠偏</el-button></div></section>
  <template v-if="result">
    <div class="stat-grid"><div class="stat-card"><div class="label">纠偏前 TrustScore</div><div class="value">{{ result.trust_score.before }}</div></div><div class="stat-card"><div class="label">纠偏后 TrustScore</div><div class="value">{{ result.trust_score.after }}</div></div><div class="stat-card"><div class="label">提升</div><div class="value">+{{ result.before_after_comparison.improvement }}</div></div><div class="stat-card"><div class="label">隔离证据</div><div class="value">{{ result.suspicious_evidence.length }}</div></div></div>
    <section class="panel two-col"><div><h2 class="panel-title">TrustScore 对比</h2><ScoreComparisonChart :before="result.trust_score.before" :after="result.trust_score.after" /></div><div><h2 class="panel-title">纠偏动作</h2><el-timeline><el-timeline-item v-for="item in result.correction_actions" :key="item">{{ item }}</el-timeline-item></el-timeline></div></section>
    <section class="panel"><h2 class="panel-title">Evidence-backed BFT 加权声明</h2><el-table :data="result.bft_consensus" empty-text="无可参与共识的低风险声明"><el-table-column prop="claim_id" label="Claim" width="120" /><el-table-column prop="weight" label="Weight" width="110" /><el-table-column prop="content" label="内容" show-overflow-tooltip /></el-table></section>
    <section class="panel"><h2 class="panel-title">可信重生成结果</h2><div class="answer-box">{{ result.trusted_answer }}</div></section>
  </template>
</template>
