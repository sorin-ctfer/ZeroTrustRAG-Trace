<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { externalKnowledgeApi, interactiveSessionApi, poisonSamplesApi, trainingApi } from '@/api/lab'
import { useAsyncTask } from '@/composables/useAsyncTask'

const router = useRouter()
const externalStats = ref<any>({})
const trainingStats = ref<any>({})
const trainingStatus = ref<any>({})
const samples = ref<any[]>([])
const sessions = ref<any[]>([])
const publicSources = ref<any[]>([])
const { loading, error, execute } = useAsyncTask()

const latestSession = computed(() => sessions.value[0] || {})
const highRiskSessions = computed(() => sessions.value.filter(item => item.risk_level === 'high').length)
const cards = computed(() => [
  ['可信知识 Chunk', externalStats.value.chunk_count || 0],
  ['训练样本', trainingStats.value.sample_count || 0],
  ['投毒知识样本', samples.value.length],
  ['实验室 Session', sessions.value.length],
  ['高风险 Session', highRiskSessions.value],
  ['公开数据源', publicSources.value.length],
])
const capabilities = computed(() => [
  ['交互实验室', `当前检测模式：${trainingStatus.value.mode || '规则模式'}，回答生成过程在实验 session 中按证据范围记录。`],
  ['数据集驱动投毒知识', `投毒知识来自训练数据集 poison/benign_error 样本，当前可选 ${samples.value.length} 条。`],
  ['Session 风险闭环', `最近 session 风险：${latestSession.value.risk_level || '暂无'}；报告和纠偏均绑定 session。`],
])

const load = async () => {
  const data = await execute(async () => {
    const [external, trainStats, trainStatus, poisonSamples, labSessions, sources] = await Promise.all([
      externalKnowledgeApi.stats(),
      trainingApi.stats(),
      trainingApi.status(),
      poisonSamplesApi.list(),
      interactiveSessionApi.sessions(),
      trainingApi.publicSources(),
    ])
    return { external, trainStats, trainStatus, poisonSamples, labSessions, sources }
  })
  if (!data) return
  externalStats.value = data.external
  trainingStats.value = data.trainStats
  trainingStatus.value = data.trainStatus
  samples.value = data.poisonSamples
  sessions.value = data.labSessions
  publicSources.value = data.sources
}

onMounted(load)
</script>

<template>
  <div class="page-head">
    <h1>系统仪表盘</h1>
    <p>汇总数据集、可信知识、投毒样本、训练检测模式和 session 风险状态。</p>
  </div>
  <el-alert v-if="error" class="error-alert" type="error" :title="error" show-icon :closable="false" />
  <div v-loading="loading" class="stat-grid">
    <div v-for="[label, value] in cards" :key="label" class="stat-card">
      <div class="label">{{ label }}</div>
      <div class="value">{{ value }}</div>
    </div>
  </div>
  <section class="panel">
    <div class="toolbar">
      <el-button type="primary" @click="router.push('/interactive-rag-lab')">进入交互实验室</el-button>
      <el-button @click="router.push('/rag-training')">管理训练数据集</el-button>
      <el-button @click="router.push('/reports')">查看 Session 报告</el-button>
    </div>
    <h2 class="panel-title mt-12">当前闭环</h2>
    <div class="cap-grid">
      <div v-for="[title, text] in capabilities" :key="title" class="cap-card">
        <strong>{{ title }}</strong>
        <span>{{ text }}</span>
      </div>
    </div>
  </section>
  <section class="panel">
    <h2 class="panel-title">最近实验 Session</h2>
    <el-table :data="sessions.slice(0, 6)" v-loading="loading" size="small">
      <el-table-column prop="session_id" label="Session" min-width="180" />
      <el-table-column prop="question" label="问题" min-width="260" show-overflow-tooltip />
      <el-table-column prop="risk_level" label="风险" width="110" />
      <el-table-column prop="injected_poison_count" label="注入" width="90" />
      <el-table-column prop="updated_at" label="更新时间" min-width="180" />
    </el-table>
  </section>
</template>
