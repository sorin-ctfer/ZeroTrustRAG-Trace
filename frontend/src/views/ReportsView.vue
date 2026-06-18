<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { interactiveCorrectionApi, interactiveSessionApi } from '@/api/lab'
import { useAsyncTask } from '@/composables/useAsyncTask'

const router = useRouter()
const sessions = ref<any[]>([])
const sessionId = ref('')
const reportData = ref<any>()
const { loading, error, execute } = useAsyncTask()
const selectedSession = computed(() => sessions.value.find(item => item.session_id === sessionId.value))

const loadSessions = async () => {
  const data = await execute(() => interactiveSessionApi.sessions())
  if (!data) return
  sessions.value = data
  if (!sessionId.value && sessions.value.length) sessionId.value = sessions.value[0].session_id
}

const load = async () => {
  if (!sessionId.value) {
    ElMessage.warning('请先在 AI 交互实验室完成一次投毒检测')
    return
  }
  const data = await execute(async () => {
    try {
      return await interactiveCorrectionApi.report(sessionId.value)
    } catch {
      return await interactiveSessionApi.report(sessionId.value)
    }
  })
  if (data) reportData.value = data
}

const copy = async () => {
  await navigator.clipboard.writeText(JSON.stringify(reportData.value, null, 2))
  ElMessage.success('已复制 JSON')
}

const download = () => {
  const blob = new Blob([JSON.stringify(reportData.value, null, 2)], { type: 'application/json' })
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = `${sessionId.value || 'interactive-rag-report'}.json`
  a.click()
  URL.revokeObjectURL(a.href)
}

onMounted(loadSessions)
</script>

<template>
  <div class="page-head">
    <h1>结构化风险报告</h1>
    <p>报告只围绕 AI 交互实验室 session 生成，包含投毒前后回答、Top-K 证据、检测结果、纠偏动作和最终风险状态。</p>
  </div>
  <el-alert v-if="error" class="error-alert" type="error" :title="error" show-icon :closable="false" />
  <section class="panel">
    <div class="toolbar">
      <el-select v-model="sessionId" style="width: 520px" placeholder="选择 AI 交互实验室 Session" filterable>
        <el-option
          v-for="item in sessions"
          :key="item.session_id"
          :label="`${item.session_id} · ${item.risk_level} · ${item.question || '未提问'}`"
          :value="item.session_id"
        />
      </el-select>
      <el-button type="primary" :loading="loading" @click="load">生成 Session 报告</el-button>
      <el-button :disabled="!reportData" @click="copy">复制 JSON</el-button>
      <el-button :disabled="!reportData" @click="download">下载 .json</el-button>
      <el-button @click="router.push('/interactive-rag-lab')">进入 AI 交互实验室</el-button>
    </div>
    <el-empty v-if="!sessions.length" description="暂无 AI 交互实验室 session，请先完成一次实验" />
    <div v-if="selectedSession" class="metric-grid mt-12">
      <div><span>风险等级</span><strong>{{ selectedSession.risk_level }}</strong></div>
      <div><span>注入投毒</span><strong>{{ selectedSession.injected_poison_count }}</strong></div>
      <div><span>检测状态</span><strong>{{ selectedSession.has_detection ? '已检测' : '未检测' }}</strong></div>
      <div><span>纠偏状态</span><strong>{{ selectedSession.has_correction ? '已纠偏' : '未纠偏' }}</strong></div>
    </div>
  </section>
  <section v-if="reportData" v-loading="loading" class="panel">
    <div class="json-box">{{ JSON.stringify(reportData, null, 2) }}</div>
  </section>
</template>
