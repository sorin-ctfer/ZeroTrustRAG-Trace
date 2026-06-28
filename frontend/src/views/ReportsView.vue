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
const detection = computed(() => reportData.value?.detection_result || reportData.value?.detection_report || {})
const correction = computed(() => reportData.value?.correction_result || reportData.value?.correction || {})
const riskChunks = computed(() => detection.value?.risk_chunks || detection.value?.detected_poison_chunks || [])
const retrievedChunks = computed(() => detection.value?.retrieved_chunks || reportData.value?.topk_after || [])

const loadSessions = async () => {
  const data = await execute(() => interactiveSessionApi.sessions())
  if (!data) return
  sessions.value = data
  if (!sessionId.value && sessions.value.length) sessionId.value = sessions.value[0].session_id
}

const load = async () => {
  if (!sessionId.value) {
    ElMessage.warning('请先在交互实验室完成一次投毒检测')
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

const printReport = () => window.print()

onMounted(loadSessions)
</script>

<template>
  <div class="page-head">
    <h1>结构化风险报告</h1>
    <p>报告围绕实验 session 生成，包含投毒前后回答、Top-K 证据、检测结果、纠偏动作和最终风险状态。</p>
  </div>
  <el-alert v-if="error" class="error-alert" type="error" :title="error" show-icon :closable="false" />
  <section class="panel">
    <div class="toolbar">
      <el-select v-model="sessionId" style="width: 520px" placeholder="选择实验 Session" filterable>
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
      <el-button :disabled="!reportData" @click="printReport">打印报告</el-button>
      <el-button @click="router.push('/interactive-rag-lab')">进入交互实验室</el-button>
    </div>
    <el-empty v-if="!sessions.length" description="暂无实验 session，请先完成一次实验" />
    <div v-if="selectedSession" class="metric-grid mt-12">
      <div><span>风险等级</span><strong>{{ selectedSession.risk_level }}</strong></div>
      <div><span>注入投毒</span><strong>{{ selectedSession.injected_poison_count }}</strong></div>
      <div><span>检测状态</span><strong>{{ selectedSession.has_detection ? '已检测' : '未检测' }}</strong></div>
      <div><span>纠偏状态</span><strong>{{ selectedSession.has_correction ? '已纠偏' : '未纠偏' }}</strong></div>
    </div>
  </section>
  <section v-if="reportData" v-loading="loading" class="panel report-body">
    <div class="report-header">
      <div>
        <h2>检测审计报告</h2>
        <p>Session：{{ sessionId }}</p>
      </div>
      <el-tag :type="detection.risk_level === 'high' ? 'danger' : detection.risk_level === 'medium' ? 'warning' : 'success'">
        {{ detection.risk_level || selectedSession?.risk_level || '未检测' }}
      </el-tag>
    </div>

    <div class="metric-grid">
      <div><span>RiskScore</span><strong>{{ detection.risk_score ?? '-' }}</strong></div>
      <div><span>TrustScore</span><strong>{{ detection.metrics?.TrustScore_after_poison ?? '-' }}</strong></div>
      <div><span>异常知识块</span><strong>{{ riskChunks.length }}</strong></div>
      <div><span>纠偏状态</span><strong>{{ correction.corrected_answer ? '已生成' : '未生成' }}</strong></div>
    </div>

    <div class="report-section">
      <h3>执行摘要</h3>
      <p>本报告基于实验 session 的投毒前后回答、Top-K 检索证据和检测指标生成。风险结论以前端当前选择的 session 报告数据为准。</p>
    </div>

    <div class="report-section">
      <h3>异常知识块</h3>
      <el-table :data="riskChunks" border>
        <el-table-column prop="chunk_id" label="Chunk" width="190" show-overflow-tooltip />
        <el-table-column prop="trust_label" label="风险标签" width="110" />
        <el-table-column prop="risk_score" label="风险分" width="90" />
        <el-table-column prop="reason" label="原因" width="220" show-overflow-tooltip />
        <el-table-column prop="content" label="内容" show-overflow-tooltip />
      </el-table>
      <el-empty v-if="!riskChunks.length" description="暂无异常知识块" />
    </div>

    <div class="report-section">
      <h3>证据与检索结果</h3>
      <el-table :data="retrievedChunks.slice(0, 8)" border>
        <el-table-column prop="rank" label="Rank" width="80" />
        <el-table-column prop="chunk_id" label="Chunk" width="190" show-overflow-tooltip />
        <el-table-column prop="trust_label" label="可信状态" width="110" />
        <el-table-column prop="source" label="来源" width="180" show-overflow-tooltip />
        <el-table-column prop="content" label="内容" show-overflow-tooltip />
      </el-table>
    </div>

    <div v-if="correction.corrected_answer" class="report-section">
      <h3>纠偏前后对比</h3>
      <div class="two-col">
        <div class="answer-box answer-risk">{{ detection.after_answer || '暂无纠偏前回答' }}</div>
        <div class="answer-box answer-trusted">{{ correction.corrected_answer }}</div>
      </div>
    </div>

    <div class="report-section">
      <h3>结构化 JSON</h3>
      <div class="json-box report-json">{{ JSON.stringify(reportData, null, 2) }}</div>
    </div>
  </section>
</template>
