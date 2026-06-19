<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ChatDotRound, InfoFilled, Right, Search, Share, Warning } from '@element-plus/icons-vue'
import { externalKnowledgeApi, interactiveSessionApi, poisonSamplesApi, trainingApi } from '@/api/lab'

const router = useRouter()
const question = ref('')
const session = ref<any>()
const summary = ref<any>({})
const samples = ref<any[]>([])
const selectedSample = ref('')
const publicSources = ref<any[]>([])
const selectedSource = ref('')
const beforeChat = ref<any>()
const afterChat = ref<any>()
const detection = ref<any>()
const externalStats = ref<any>({})
const trainingStats = ref<any>({})
const trainingStatus = ref<any>({})
const loadingStep = ref('')
const injectedSampleId = ref('')
const initError = ref('')
const tourOpen = ref(false)
const LAB_STATE_KEY = 'interactive-rag-lab-state'

const selectedPoison = computed(() => samples.value.find(item => item.sample_id === selectedSample.value))
const sessionId = computed(() => session.value?.session_id || '')
const riskPercent = computed(() => Math.round((detection.value?.risk_score || 0) * 100))
const currentTrustScore = computed(() => summary.value.current_trust_score || detection.value?.metrics?.TrustScore_after_poison || 100)
const injectedCount = computed(() => summary.value.injected_poison_count ?? session.value?.injected_poison_chunk_ids?.length ?? 0)
const topkBefore = computed(() => beforeChat.value?.retrieved_chunks || [])
const topkAfter = computed(() => afterChat.value?.retrieved_chunks || [])
const llmStatus = computed(() => summary.value.llm_status || beforeChat.value?.llm_status || afterChat.value?.llm_status || {})
const llmMode = computed(() => llmStatus.value.mode || '模型状态检查中')
const llmProvider = computed(() => afterChat.value?.llm_provider || beforeChat.value?.llm_provider || 'bailian')
const llmProviderLabel = computed(() => {
  if (llmProvider.value === 'ollama') return '本地 Ollama'
  if (llmProvider.value === 'bailian') return '百炼大模型'
  if (llmProvider.value === 'extractive') return '证据抽取兜底'
  return llmStatus.value.mode || '模型待调用'
})
const canEnterCorrection = computed(() => detection.value?.risk_level === 'high' || detection.value?.detected_poison_chunks?.length)
const tagType = (label: string) => label === 'trusted' ? 'success' : label === 'poison' ? 'danger' : label === 'benign_error' ? 'warning' : label === 'quarantined' ? 'info' : 'primary'
const displayQuestion = computed(() => question.value.trim() || (selectedPoison.value ? '使用所选样本内置问题（已隐藏）' : ''))
const experimentQuestion = () => question.value.trim() || selectedPoison.value?.target_query || ''
const sampleLabel = (item: any, index: number) => {
  const source = item.source || '训练数据集投毒知识'
  return `样本 ${String(index + 1).padStart(3, '0')} · ${item.attack_type} · ${source}`
}

const persistLabState = () => {
  window.localStorage.setItem(LAB_STATE_KEY, JSON.stringify({
    session_id: sessionId.value,
    question: question.value,
    selected_sample: selectedSample.value,
    injected_sample: injectedSampleId.value,
    selected_source: selectedSource.value,
  }))
}

const hydrateFromSession = (savedSession: any) => {
  session.value = savedSession
  const chats = savedSession?.chats || {}
  beforeChat.value = chats.before_poison || chats.normal_chat
  afterChat.value = chats.after_poison
  detection.value = savedSession?.detection_result || savedSession?.detection_report
  injectedSampleId.value = savedSession?.injected_poison_chunks?.[0]?.sample_id || ''
}

const restoreLabState = async () => {
  const raw = window.localStorage.getItem(LAB_STATE_KEY)
  if (!raw) return false
  try {
    const saved = JSON.parse(raw)
    if (saved.selected_source) selectedSource.value = saved.selected_source
    if (saved.selected_sample) selectedSample.value = saved.selected_sample
    if (saved.question) question.value = saved.question
    if (saved.injected_sample) injectedSampleId.value = saved.injected_sample
    if (!saved.session_id) return false
    const savedSession = await withTimeout(interactiveSessionApi.get(saved.session_id))
    hydrateFromSession(savedSession)
    return true
  } catch {
    window.localStorage.removeItem(LAB_STATE_KEY)
    return false
  }
}

const startTour = () => {
  tourOpen.value = true
}

const closeTour = () => {
  tourOpen.value = false
  window.localStorage.setItem('interactive-rag-lab-tour-dismissed', '1')
}

const withTimeout = async <T,>(task: Promise<T>, ms = 180000): Promise<T> => {
  let timer: ReturnType<typeof setTimeout> | undefined
  try {
    return await Promise.race([
      task,
      new Promise<T>((_, reject) => {
        timer = setTimeout(() => reject(new Error('接口响应超时，请确认本地 Ollama 已启动；如需百炼兜底，请检查后端 .env 配置')), ms)
      }),
    ])
  } finally {
    if (timer) clearTimeout(timer)
  }
}

const refresh = async () => {
  externalStats.value = await withTimeout(externalKnowledgeApi.stats())
  trainingStats.value = await withTimeout(trainingApi.stats())
  trainingStatus.value = await withTimeout(trainingApi.status())
  samples.value = (await withTimeout(poisonSamplesApi.list())).filter(item => item.enabled)
  if (!selectedSample.value && samples.value.length) selectedSample.value = samples.value[0].sample_id
  if (sessionId.value) summary.value = await withTimeout(interactiveSessionApi.riskSummary(sessionId.value))
}

const prepareDatasetLab = async () => run('prepare', async () => {
  if (!selectedSource.value) {
    ElMessage.warning('请选择一个公开数据集来源')
    return
  }
  await withTimeout(trainingApi.publicDownload([selectedSource.value]))
  await withTimeout(trainingApi.publicImportTraining(selectedSource.value, 120))
  await withTimeout(trainingApi.publicImportCleanKnowledge(selectedSource.value, 120))
  await withTimeout(poisonSamplesApi.loadFromTraining(120))
  ElMessage.success('已基于所选数据集准备可信知识和投毒知识')
})

const createCleanSession = async () => {
  session.value = await withTimeout(interactiveSessionApi.create())
  beforeChat.value = undefined
  afterChat.value = undefined
  detection.value = undefined
  injectedSampleId.value = ''
  summary.value = {}
  persistLabState()
}

const run = async (step: string, task: () => Promise<void>) => {
  loadingStep.value = step
  try {
    await task()
    await refresh()
  } catch (error: any) {
    ElMessage.error(error.message || '操作失败')
  } finally {
    loadingStep.value = ''
  }
}

const askBefore = async () => run('before', async () => {
  const currentQuestion = experimentQuestion()
  if (!currentQuestion) {
    ElMessage.warning('请选择数据集投毒样本，或输入一个实验问题')
    return
  }
  await createCleanSession()
  beforeChat.value = await withTimeout(interactiveSessionApi.chat(currentQuestion, 'before_poison', sessionId.value))
  session.value = await withTimeout(interactiveSessionApi.get(sessionId.value))
  persistLabState()
})

const askAfter = async () => run('after', async () => {
  if (!sessionId.value || !beforeChat.value) await askBefore()
  if (!beforeChat.value) return
  if (!selectedSample.value) {
    ElMessage.warning('请选择数据集投毒样本')
    return
  }
  if (injectedSampleId.value !== selectedSample.value) {
    await withTimeout(interactiveSessionApi.injectPoison(sessionId.value, selectedSample.value))
    injectedSampleId.value = selectedSample.value
  }
  afterChat.value = await withTimeout(interactiveSessionApi.chat(experimentQuestion(), 'after_poison', sessionId.value))
  session.value = await withTimeout(interactiveSessionApi.get(sessionId.value))
  persistLabState()
})

const detectPoison = async () => run('detect', async () => {
  if (!sessionId.value || !beforeChat.value || !afterChat.value) {
    ElMessage.warning('请先完成投毒前和投毒后问答')
    return
  }
  detection.value = await withTimeout(interactiveSessionApi.detect({
    session_id: sessionId.value,
    question: experimentQuestion(),
    before_answer: beforeChat.value.answer,
    after_answer: afterChat.value.answer,
  }))
  session.value = await withTimeout(interactiveSessionApi.get(sessionId.value))
  persistLabState()
  if (canEnterCorrection.value) ElMessage.warning('检测到高风险投毒，请进入可信纠偏页面处理')
  else ElMessage.success('已完成检测，未发现明确高风险投毒')
})

const enterCorrection = () => {
  if (!sessionId.value || !detection.value) {
    ElMessage.warning('请先在 AI 交互实验室执行投毒检测')
    return
  }
  router.push(`/interactive-correction/${sessionId.value}`)
}

const enterPropagation = () => {
  if (!sessionId.value || !detection.value) {
    ElMessage.warning('请先在 AI 交互实验室执行投毒检测')
    return
  }
  router.push(`/poison-propagation/${sessionId.value}`)
}

watch(selectedPoison, persistLabState)

watch([question, selectedSource], persistLabState)

onMounted(async () => {
  tourOpen.value = window.localStorage.getItem('interactive-rag-lab-tour-dismissed') !== '1'
  try {
    publicSources.value = await withTimeout(trainingApi.publicSources())
    if (!selectedSource.value && publicSources.value.length) selectedSource.value = publicSources.value[0].key
    const restored = await restoreLabState()
    if (!restored) await createCleanSession()
    await refresh()
  } catch (error: any) {
    initError.value = error.message || '初始化失败，请确认后端 API 已启动'
  }
})
</script>

<template>
  <div class="page-head lab-hero">
    <div class="lab-title-row">
      <div>
        <h1>AI 交互实验室</h1>
        <p>围绕公开数据集完成可信知识导入、投毒知识选择、百炼大模型问答、Top-K 对比、投毒检测、可信纠偏和 session 风险报告。</p>
      </div>
      <el-button :icon="InfoFilled" @click="startTour">打开指引</el-button>
    </div>
  </div>
  <el-alert v-if="initError" class="error-alert" type="warning" show-icon :closable="false" :title="initError" />

  <el-tour v-model="tourOpen" @close="closeTour" @finish="closeTour">
    <el-tour-step
      target=".guide-target-status"
      title="确认模型调用状态"
      description="这里显示当前 AI 模型链路。当前默认直接调用百炼大模型；切换到 Ollama 时才使用本地模型快速模式。"
      placement="bottom"
    />
    <el-tour-step
      target=".guide-target-chat"
      title="投毒前后问答区"
      description="实验回答会在这里展示。投毒前回答只使用可信知识库，投毒后回答会混合当前 session 注入样本。"
      placement="right"
    />
    <el-tour-step
      target=".guide-target-question"
      title="按顺序执行实验"
      description="先编辑问题并点击投毒前提问，再注入样本并投毒后提问，最后执行投毒检测。"
      placement="top"
    />
    <el-tour-step
      target=".guide-target-samples"
      title="选择数据集投毒样本"
      description="样本来自已导入训练数据集，只注入当前 session，不写入外部可信知识库；目标问题在页面隐藏。"
      placement="left"
    />
    <el-tour-step
      target=".guide-target-topk-before"
      title="查看投毒前 Top-K"
      description="这里是可信基线检索结果，用来确认正常证据、引用 chunk 和相似度。"
      placement="left"
    />
    <el-tour-step
      target=".guide-target-topk-after"
      title="对比投毒后 Top-K"
      description="如果 poison 或低可信证据排名靠前，并影响回答结论，就继续执行检测。"
      placement="left"
    />
    <el-tour-step
      target=".guide-target-detect"
      title="执行投毒检测"
      description="检测会综合 RAS、GIS、DualRisk 和 TrustScore 判断投毒风险。"
      placement="top"
    />
    <el-tour-step
      target=".guide-target-correction"
      title="构建传播图谱与可信纠偏"
      description="检测后先构建投毒传播图谱，查看相似投毒片段和传播路径；高风险时继续进入可信纠偏。"
      placement="left"
    />
  </el-tour>

  <div class="stat-grid compact-stats guide-target-status">
    <div class="stat-card"><div class="label">外部可信 Chunk</div><div class="value">{{ externalStats.chunk_count || 0 }}</div></div>
    <div class="stat-card"><div class="label">当前 session 投毒</div><div class="value">{{ injectedCount }}</div></div>
    <div class="stat-card"><div class="label">训练样本</div><div class="value">{{ trainingStats.sample_count || 0 }}</div></div>
    <div class="stat-card"><div class="label">检测模式</div><div class="value small-value">{{ summary.detection_mode || trainingStatus.mode || '规则模式' }}</div></div>
    <div class="stat-card"><div class="label">AI 模型</div><div class="value small-value">{{ llmMode }}</div></div>
    <div class="stat-card"><div class="label">当前 TrustScore</div><div class="value">{{ currentTrustScore }}</div></div>
  </div>

  <section class="panel">
    <h2 class="panel-title">数据集实验准备</h2>
    <div class="toolbar">
      <el-select v-model="selectedSource" style="width: 320px" placeholder="选择公开数据集">
        <el-option
          v-for="item in publicSources"
          :key="item.key"
          :label="`${item.name} · ${item.downloaded ? '已下载' : '未下载'}`"
          :value="item.key"
        />
      </el-select>
      <el-button type="primary" :loading="loadingStep === 'prepare'" @click="prepareDatasetLab">
        准备当前实验数据
      </el-button>
      <el-tag type="info">Session {{ sessionId || '初始化中' }}</el-tag>
    </div>
    <p class="muted">
      该步骤从所选公开数据集导入训练样本和可信 clean chunks，并从 poison/benign_error 样本生成实验室可选投毒知识。
    </p>
  </section>

  <div class="rag-lab-layout">
    <section class="panel chat-panel guide-target-chat">
      <div class="session-strip">
        <el-tag effect="dark">{{ sessionId || 'SESSION 初始化中' }}</el-tag>
        <el-tag :type="llmProvider === 'extractive' ? 'warning' : 'success'">{{ llmProviderLabel }}</el-tag>
        <el-button :loading="loadingStep === 'before'" @click="askBefore">新建可信基线</el-button>
      </div>

      <div v-if="!beforeChat && !afterChat" class="chat-empty">
        <el-icon><ChatDotRound /></el-icon>
        <span>输入问题后先生成投毒前可信回答</span>
      </div>

      <div v-else class="chat-scroll">
        <div class="chat-row user">
          <div class="chat-bubble">
            <div class="chat-stage">用户问题</div>
            <div class="chat-text">{{ displayQuestion }}</div>
          </div>
        </div>
        <div v-if="beforeChat" class="chat-row assistant">
          <div class="chat-bubble">
            <div class="chat-stage">AI 回答 · 投毒前可信检索 · {{ beforeChat.llm_provider }}</div>
            <div class="chat-text">{{ beforeChat.answer }}</div>
            <el-collapse class="citation-collapse">
              <el-collapse-item title="引用证据">
                <div v-for="chunk in topkBefore" :key="chunk.chunk_id" class="citation-card">
                  <div>
                    <code>#{{ chunk.rank }} {{ chunk.chunk_id }}</code>
                    <el-tag size="small" :type="tagType(chunk.trust_label || chunk.trust_level)">{{ chunk.trust_label || chunk.trust_level }}</el-tag>
                  </div>
                  <p>{{ chunk.content }}</p>
                  <small>similarity {{ chunk.similarity ?? chunk.score }} · {{ chunk.retrieval_mode || 'tfidf_fallback' }}</small>
                </div>
              </el-collapse-item>
            </el-collapse>
          </div>
        </div>
        <div v-if="afterChat" class="chat-row assistant">
          <div class="chat-bubble risk-bubble">
            <div class="chat-stage">AI 回答 · 投毒后混合检索 · {{ afterChat.llm_provider }}</div>
            <div class="chat-text">{{ afterChat.answer }}</div>
            <el-collapse class="citation-collapse">
              <el-collapse-item title="引用证据">
                <div v-for="chunk in topkAfter" :key="chunk.chunk_id" class="citation-card">
                  <div>
                    <code>#{{ chunk.rank }} {{ chunk.chunk_id }}</code>
                    <el-tag size="small" :type="tagType(chunk.trust_label || chunk.trust_level)">{{ chunk.trust_label || chunk.trust_level }}</el-tag>
                  </div>
                  <p>{{ chunk.content }}</p>
                  <small>similarity {{ chunk.similarity ?? chunk.score }} · {{ chunk.retrieval_mode || 'tfidf_fallback' }}</small>
                </div>
              </el-collapse-item>
            </el-collapse>
          </div>
        </div>
      </div>

      <div class="chat-input guide-target-question">
        <el-input v-model="question" type="textarea" :rows="3" placeholder="输入自定义实验问题；留空时使用所选样本内置问题（页面隐藏）" />
        <div class="toolbar mt-12">
          <el-button type="primary" :icon="Search" :loading="loadingStep === 'before'" @click="askBefore">投毒前提问</el-button>
          <el-button type="warning" :icon="Warning" :loading="loadingStep === 'after'" @click="askAfter">注入样本并投毒后提问</el-button>
          <el-button class="guide-target-detect" :loading="loadingStep === 'detect'" @click="detectPoison">执行投毒检测</el-button>
        </div>
      </div>
    </section>

    <aside class="panel risk-panel guide-target-correction">
      <h2 class="panel-title">数据集投毒知识</h2>
      <div class="guide-target-samples">
        <el-alert type="warning" :closable="false" show-icon title="只注入当前 session，不写入外部可信知识库。" />
        <el-select v-model="selectedSample" class="mt-12" placeholder="选择投毒样本" filterable>
          <el-option
            v-for="(item, index) in samples"
            :key="item.sample_id"
            :label="sampleLabel(item, index)"
            :value="item.sample_id"
          />
        </el-select>
        <div v-if="selectedPoison" class="poison-detail">
          <h3>数据来源</h3>
          <p>{{ selectedPoison.source }}</p>
          <h3>样本问题</h3>
          <p class="muted">已隐藏，执行实验时在后台使用。</p>
          <h3>投毒内容</h3>
          <div class="answer-box answer-risk">{{ selectedPoison.content }}</div>
        </div>
      </div>

      <h3>投毒前 Top-K</h3>
      <div class="topk-list guide-target-topk-before">
        <div v-for="chunk in topkBefore" :key="chunk.chunk_id" class="citation-card">
          <div><code>#{{ chunk.rank }} {{ chunk.chunk_id }}</code><el-tag size="small" :type="tagType(chunk.trust_label)">{{ chunk.trust_label }}</el-tag></div>
          <p>{{ chunk.content }}</p>
          <small>similarity {{ chunk.similarity ?? chunk.score }}</small>
        </div>
        <el-empty v-if="!topkBefore.length" description="暂无投毒前检索结果" />
      </div>

      <h3>投毒后 Top-K</h3>
      <div class="topk-list guide-target-topk-after">
        <div v-for="chunk in topkAfter" :key="chunk.chunk_id" class="citation-card">
          <div><code>#{{ chunk.rank }} {{ chunk.chunk_id }}</code><el-tag size="small" :type="tagType(chunk.trust_label)">{{ chunk.trust_label }}</el-tag></div>
          <p>{{ chunk.content }}</p>
          <small>similarity {{ chunk.similarity ?? chunk.score }}</small>
        </div>
        <el-empty v-if="!topkAfter.length" description="暂无投毒后检索结果" />
      </div>

      <template v-if="detection">
        <h3>检测结果</h3>
        <el-progress :percentage="riskPercent" :status="riskPercent >= 70 ? 'exception' : undefined" />
        <div class="metric-grid">
          <div v-for="key in ['RAS', 'GIS', 'DualRisk']" :key="key">
            <span>{{ key }}</span>
            <strong>{{ Number(detection.metrics?.[key] || 0).toFixed(3) }}</strong>
          </div>
        </div>
        <el-timeline class="mt-12">
          <el-timeline-item v-for="item in detection.risk_types || ['低风险观察项']" :key="item" :type="detection.risk_level === 'high' ? 'danger' : 'primary'">
            {{ item }}
          </el-timeline-item>
        </el-timeline>
        <el-button class="correct-entry" type="primary" :icon="Share" @click="enterPropagation">
          构建投毒传播图谱
        </el-button>
        <el-button v-if="canEnterCorrection" class="correct-entry" type="danger" :icon="Right" @click="enterCorrection">
          进入可信纠偏
        </el-button>
      </template>
    </aside>
  </div>
</template>
