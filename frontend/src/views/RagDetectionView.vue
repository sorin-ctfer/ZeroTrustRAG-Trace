<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api, unwrap } from '@/api'

const cases = ref<any[]>([]), caseId = ref('case_enterprise_policy_approval')
const query = ref(''), answer = ref(''), result = ref<any>(), loading = ref(false)
const selectCase = async () => {
  const data: any = unwrap(await api.get(`/rag/cases/${caseId.value}`))
  query.value = data.question; answer.value = data.original_answer || data.target_wrong_answer
}
const analyze = async () => {
  loading.value = true
  try { result.value = unwrap(await api.post('/rag/analyze', { case_id: caseId.value, query: query.value, original_answer: answer.value, top_k: 8 })) }
  finally { loading.value = false }
}
onMounted(async () => { cases.value = unwrap(await api.get('/rag/cases')); await selectCase() })
</script>

<template>
  <div class="page-head"><h1>RAG 知识投毒检测</h1><p>TF-IDF 检索结合 RAS、GIS、DualRisk、四路反事实和 TrustScore。</p></div>
  <section class="panel">
    <el-form label-width="100px">
      <el-form-item label="演示案例"><el-select v-model="caseId" style="width: 520px" @change="selectCase"><el-option v-for="item in cases" :key="item.case_id" :label="item.title" :value="item.case_id" /></el-select></el-form-item>
      <el-form-item label="Query"><el-input v-model="query" /></el-form-item>
      <el-form-item label="原始 Answer"><el-input v-model="answer" type="textarea" :rows="3" /></el-form-item>
      <el-button type="primary" :loading="loading" @click="analyze">执行投毒分析</el-button>
    </el-form>
  </section>
  <section v-if="result" class="panel">
    <div class="toolbar"><el-tag type="danger">可疑证据 {{ result.suspicious_evidence.length }}</el-tag><el-tag type="warning">TrustScore {{ result.trust_score.trust_score }}</el-tag></div>
    <el-table :data="result.top_k" stripe>
      <el-table-column prop="retrieval_rank" label="排名" width="70" />
      <el-table-column prop="evidence_id" label="Evidence" width="135" />
      <el-table-column prop="content" label="内容" min-width="310" show-overflow-tooltip />
      <el-table-column prop="ras" label="RAS" width="85" /><el-table-column prop="gis" label="GIS" width="85" />
      <el-table-column prop="dual_risk" label="DualRisk" width="100" /><el-table-column prop="causal_score" label="Causal" width="90" />
      <el-table-column label="风险" width="90"><template #default="{ row }"><el-tag :type="row.dual_risk >= .6 ? 'danger' : row.dual_risk >= .5 ? 'warning' : 'success'">{{ row.risk_level }}</el-tag></template></el-table-column>
    </el-table>
  </section>
  <section v-if="result?.counterfactual_results?.length" class="panel">
    <h2 class="panel-title">四路反事实验证</h2>
    <el-collapse><el-collapse-item v-for="item in result.counterfactual_results" :key="item.suspicious_evidence_id" :title="`${item.suspicious_evidence_id} · CausalScore ${item.causal_score}`"><p><b>原始：</b>{{ item.original_answer }}</p><p><b>删除：</b>{{ item.remove_answer }}</p><p><b>仅可疑：</b>{{ item.solo_answer }}</p><p><b>可信替代：</b>{{ item.replace_answer }}</p></el-collapse-item></el-collapse>
  </section>
</template>
