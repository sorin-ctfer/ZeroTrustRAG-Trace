<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { api, unwrap } from '@/api'
import { useAsyncTask } from '@/composables/useAsyncTask'
const cases = ref<any[]>([])
const caseId = ref('case_enterprise_policy_approval'), reportData = ref<any>()
const { loading, error, execute } = useAsyncTask()
const load = async () => {
  const data = await execute(async () => unwrap(await api.get(`/report/${caseId.value}`)))
  if (data) reportData.value = data
}
const copy = async () => {
  await navigator.clipboard.writeText(JSON.stringify(reportData.value, null, 2))
  ElMessage.success('已复制 JSON')
}
const download = () => {
  const blob = new Blob([JSON.stringify(reportData.value, null, 2)], { type: 'application/json' })
  const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = `${caseId.value}.json`; a.click(); URL.revokeObjectURL(a.href)
}
onMounted(async () => {
  const data = await execute(async () => unwrap<any[]>(await api.get('/rag/cases')))
  if (data) cases.value = data
})
</script>
<template>
  <div class="page-head"><h1>结构化风险报告</h1><p>生成、复制和下载包含检测、溯源、纠偏与前后对比的 JSON 报告。</p></div>
  <el-alert v-if="error" class="error-alert" type="error" :title="error" show-icon :closable="false" />
  <section class="panel"><div class="toolbar"><el-select v-model="caseId" style="width: 420px"><el-option v-for="item in cases" :key="item.case_id" :label="item.title" :value="item.case_id" /></el-select><el-button type="primary" :loading="loading" @click="load">生成报告</el-button><el-button :disabled="!reportData" @click="copy">复制 JSON</el-button><el-button :disabled="!reportData" @click="download">下载 .json</el-button></div></section>
  <section v-if="reportData" v-loading="loading" class="panel"><div class="json-box">{{ JSON.stringify(reportData, null, 2) }}</div></section>
</template>
