<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { interactiveCorrectionApi } from '@/api/lab'

const route = useRoute()
const router = useRouter()
const sessionId = String(route.params.session_id)
const detail = ref<any>()
const counterfactual = ref<any>()
const correction = ref<any>()
const report = ref<any>()
const loading = ref(false)
const tagType = (label: string) => label === 'trusted' ? 'success' : label === 'poison' ? 'danger' : label === 'benign_error' ? 'warning' : 'info'
const refresh = async () => { detail.value = await interactiveCorrectionApi.detail(sessionId) }
const run = async (task: () => Promise<any>, message: string, assign?: (data: any) => void) => {
  loading.value = true
  try {
    const data = await task()
    if (assign) assign(data)
    await refresh()
    ElMessage.success(message)
  } catch (error: any) {
    ElMessage.error(error.message || '操作失败')
  } finally {
    loading.value = false
  }
}
const runCounterfactual = () => run(
  () => interactiveCorrectionApi.counterfactual(sessionId),
  '反事实验证完成',
  data => { counterfactual.value = data },
)
const runRegenerate = () => run(
  () => interactiveCorrectionApi.regenerate(sessionId),
  '可信重生成完成',
  data => { correction.value = data },
)
const runReport = () => run(
  () => interactiveCorrectionApi.report(sessionId),
  '纠偏报告已生成',
  data => { report.value = data },
)
onMounted(refresh)
</script>

<template>
  <div class="page-head">
    <h1>交互式可信纠偏</h1>
    <p>检测到投毒后，在独立页面执行隔离、四路反事实、重检索和可信重生成。</p>
  </div>

  <el-empty v-if="detail && !detail.ready" :description="detail.message">
    <el-button type="primary" @click="router.push('/interactive-rag-lab')">返回 AI 交互实验室</el-button>
  </el-empty>

  <template v-if="detail?.ready">
    <div class="stat-grid">
      <div class="stat-card"><div class="label">Session</div><div class="value small-value">{{ sessionId }}</div></div>
      <div class="stat-card"><div class="label">风险等级</div><div class="value small-value">{{ detail.risk_level }}</div></div>
      <div class="stat-card"><div class="label">Risk Chunks</div><div class="value">{{ detail.risk_chunks.length }}</div></div>
      <div class="stat-card"><div class="label">TrustScore Before</div><div class="value">{{ detail.metrics.TrustScore_after_poison || detail.metrics.TrustScore_before }}</div></div>
    </div>

    <div class="correction-layout">
      <section class="panel">
        <h2 class="panel-title">高风险 Chunk</h2>
        <div class="chunk-list">
          <div v-for="chunk in detail.risk_chunks" :key="chunk.chunk_id" class="chunk-card">
            <div class="chunk-title"><code>{{ chunk.chunk_id }}</code><el-tag :type="tagType(chunk.trust_label)">{{ chunk.trust_label }}</el-tag></div>
            <p>{{ chunk.content }}</p>
            <small>{{ chunk.source }} · RAS {{ chunk.RAS }} · GIS {{ chunk.GIS }} · DualRisk {{ chunk.DualRisk }} · CausalScore {{ chunk.CausalScore }}</small>
            <div class="evidence-strip evidence-risk">{{ chunk.reason }} · target_wrong_answer: {{ chunk.target_wrong_answer_hit ? '命中' : '未命中' }}</div>
          </div>
        </div>
      </section>

      <section class="panel">
        <h2 class="panel-title">四路反事实验证</h2>
        <el-button :loading="loading" @click="runCounterfactual">运行反事实验证</el-button>
        <div v-if="counterfactual" class="counterfactual-grid">
          <div v-for="key in ['original', 'remove', 'solo', 'replace']" :key="key" class="answer-box">
            <strong>{{ key }}</strong>
            <p>{{ counterfactual[key]?.answer }}</p>
          </div>
        </div>
        <div v-if="counterfactual" class="metric-grid">
          <div v-for="key in ['E_remove', 'E_solo', 'E_replace', 'CausalScore']" :key="key"><span>{{ key }}</span><strong>{{ counterfactual[key] }}</strong></div>
        </div>
      </section>

      <section class="panel">
        <h2 class="panel-title">纠偏操作</h2>
        <div class="flow-actions">
          <el-button type="warning" :loading="loading" @click="run(() => interactiveCorrectionApi.quarantine(sessionId), '高风险 Chunk 已在当前 session 隔离')">隔离高风险 Chunk</el-button>
          <el-button :loading="loading" @click="ElMessage.success('重检索将在可信重生成时执行')">重新检索</el-button>
          <el-button type="success" :loading="loading" @click="runRegenerate">可信重生成</el-button>
          <el-button :loading="loading" @click="runReport">生成纠偏报告</el-button>
        </div>
        <div v-if="correction" class="answer-box answer-trusted">{{ correction.corrected_answer }}</div>
      </section>
    </div>

    <section class="panel" v-if="correction">
      <h2 class="panel-title">纠偏前后对比</h2>
      <div class="metric-grid">
        <div><span>TrustScore_before</span><strong>{{ correction.TrustScore_before }}</strong></div>
        <div><span>TrustScore_after</span><strong>{{ correction.TrustScore_after }}</strong></div>
        <div><span>ASR_before</span><strong>{{ correction.ASR_before }}</strong></div>
        <div><span>ASR_after</span><strong>{{ correction.ASR_after }}</strong></div>
        <div><span>RecoveryRate</span><strong>{{ correction.RecoveryRate }}</strong></div>
        <div><span>EvidenceSupportRate</span><strong>{{ correction.EvidenceSupportRate }}</strong></div>
      </div>
      <h3>纠偏后引用证据</h3>
      <el-table :data="correction.trusted_retrieved_chunks">
        <el-table-column prop="chunk_id" label="Chunk" width="190" />
        <el-table-column prop="source" label="来源" width="180" />
        <el-table-column prop="content" label="内容" show-overflow-tooltip />
      </el-table>
    </section>

    <section v-if="report" class="panel">
      <h2 class="panel-title">JSON 风险报告</h2>
      <pre class="json-box">{{ JSON.stringify(report, null, 2) }}</pre>
    </section>
  </template>
</template>
