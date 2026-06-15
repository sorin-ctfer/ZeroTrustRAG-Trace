<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { api, unwrap } from '@/api'
const cases = [
  ['case_enterprise_policy_approval', '企业制度知识投毒'],
  ['case_threat_intel_false_consensus', '安全情报错误共识'],
  ['case_prompt_infection', 'Prompt Infection'],
]
const caseId = ref(cases[0][0]), report = ref<any>()
const load = async () => { report.value = unwrap(await api.get(`/report/${caseId.value}`)) }
const copy = async () => { await navigator.clipboard.writeText(JSON.stringify(report.value, null, 2)); ElMessage.success('已复制 JSON') }
const download = () => {
  const blob = new Blob([JSON.stringify(report.value, null, 2)], { type: 'application/json' })
  const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = `${caseId.value}.json`; a.click(); URL.revokeObjectURL(a.href)
}
</script>
<template>
  <div class="page-head"><h1>结构化风险报告</h1><p>生成、复制和下载包含检测、溯源、纠偏与前后对比的 JSON 报告。</p></div>
  <section class="panel"><div class="toolbar"><el-select v-model="caseId" style="width: 360px"><el-option v-for="[id,name] in cases" :key="id" :label="name" :value="id" /></el-select><el-button type="primary" @click="load">生成报告</el-button><el-button :disabled="!report" @click="copy">复制 JSON</el-button><el-button :disabled="!report" @click="download">下载 .json</el-button></div></section>
  <section v-if="report" class="panel"><div class="json-box">{{ JSON.stringify(report, null, 2) }}</div></section>
</template>
