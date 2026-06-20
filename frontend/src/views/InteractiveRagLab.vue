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
const builtInQuestion = computed(() => String(selectedPoison.value?.target_query || '').trim())
const activeQuestion = computed(() => question.value.trim() || builtInQuestion.value)
const questionSourceLabel = computed(() => question.value.trim() ? '自定义问题' : builtInQuestion.value ? '样本内置问题' : '未设置')
const displayQuestion = computed(() => activeQuestion.value || '请选择数据集投毒样本，或输入一个实验问题')
const experimentQuestion = () => activeQuestion.value
const flowSteps = computed(() => [
  {
    title: '输入问题',
    note: activeQuestion.value ? displayQuestion.value : '等待输入问题或选择含内置问题的样本',
    done: Boolean(activeQuestion.value),
  },
  {
    title: '投毒前可信检索',
    note: beforeChat.value ? '可信基线回答已生成' : '点击“投毒前提问”生成可信基线',
    done: Boolean(beforeChat.value),
  },
  {
    title: '注入样本并对比',
    note: afterChat.value ? '投毒后混合检索回答已生成' : '选择样本后执行投毒后提问',
    done: Boolean(afterChat.value),
  },
  {
    title: '执行投毒检测',
    note: detection.value ? `${detection.value.risk_level} · ${riskPercent.value}%` : '完成前后问答后执行检测',
    done: Boolean(detection.value),
  },
])
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
      description="样本来自已导入训练数据集，只注入当前 session，不写入外部可信知识库；样本内置问题会在页面展示并可直接用于实验。"
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

  <div class="lab-page">
    <div class="stat-grid compact-stats lab-status-grid guide-target-status">
      <div class="stat-card"><div class="label">外部可信 Chunk</div><div class="value">{{ externalStats.chunk_count || 0 }}</div></div>
      <div class="stat-card"><div class="label">当前 session 投毒</div><div class="value">{{ injectedCount }}</div></div>
      <div class="stat-card"><div class="label">训练样本</div><div class="value">{{ trainingStats.sample_count || 0 }}</div></div>
      <div class="stat-card"><div class="label">检测模式</div><div class="value small-value">{{ summary.detection_mode || trainingStatus.mode || '规则模式' }}</div></div>
      <div class="stat-card"><div class="label">AI 模型</div><div class="value small-value">{{ llmMode }}</div></div>
      <div class="stat-card"><div class="label">当前 TrustScore</div><div class="value">{{ currentTrustScore }}</div></div>
    </div>

    <section class="panel lab-prep-panel">
      <div class="lab-panel-heading">
        <div>
          <h2 class="panel-title">数据集实验准备</h2>
          <p>导入训练样本、可信 clean chunks，并生成当前实验可选的投毒知识。</p>
        </div>
        <el-tag type="info">Session {{ sessionId || '初始化中' }}</el-tag>
      </div>
      <div class="prep-toolbar">
        <el-select v-model="selectedSource" placeholder="选择公开数据集">
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
      </div>
    </section>

    <div class="lab-workbench">
      <main class="lab-primary-column">
        <section class="panel lab-input-panel guide-target-question guide-target-samples">
          <div class="lab-panel-heading">
            <div>
              <h2 class="panel-title">输入、注入与检测</h2>
              <p>按顺序完成问题确认、可信基线、投毒后对比和风险检测。</p>
            </div>
            <el-tag :type="llmProvider === 'extractive' ? 'warning' : 'success'">{{ llmProviderLabel }}</el-tag>
          </div>

          <div class="lab-input-grid">
            <div class="lab-question-block">
              <div v-if="selectedPoison || question.trim()" class="active-question-card">
                <div class="active-question-head">
                  <span>当前实验问题</span>
                  <el-tag size="small" :type="question.trim() ? 'primary' : 'success'">{{ questionSourceLabel }}</el-tag>
                </div>
                <p>{{ displayQuestion }}</p>
              </div>
              <el-input v-model="question" type="textarea" :rows="4" placeholder="输入自定义实验问题；留空时使用所选样本内置问题" />
            </div>

            <div class="lab-sample-card">
              <div class="sample-picker-row">
                <div class="sample-scope-note">仅注入当前 session</div>
                <el-select v-model="selectedSample" placeholder="选择投毒样本" filterable>
                  <el-option
                    v-for="(item, index) in samples"
                    :key="item.sample_id"
                    :label="sampleLabel(item, index)"
                    :value="item.sample_id"
                  />
                </el-select>
              </div>
              <div v-if="selectedPoison" class="poison-detail compact-poison-detail">
                <div class="sample-preview-grid">
                  <div class="sample-preview-question">
                    <span>样本内置问题</span>
                    <strong>{{ selectedPoison.target_query }}</strong>
                  </div>
                  <div class="sample-answer-grid">
                    <div>
                      <span>目标错误答案</span>
                      <strong>{{ selectedPoison.target_wrong_answer || '未标注' }}</strong>
                    </div>
                    <div>
                      <span>可信正确答案</span>
                      <strong>{{ selectedPoison.correct_answer || '未标注' }}</strong>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div class="lab-action-bar">
            <el-button :icon="Search" :loading="loadingStep === 'before'" @click="askBefore">投毒前提问</el-button>
            <el-button type="warning" plain :icon="Warning" :loading="loadingStep === 'after'" @click="askAfter">注入样本并投毒后提问</el-button>
            <el-button class="guide-target-detect" type="primary" :loading="loadingStep === 'detect'" @click="detectPoison">执行投毒检测</el-button>
          </div>

          <div class="workflow-card">
            <div v-for="(step, index) in flowSteps" :key="step.title" class="workflow-step" :class="{ done: step.done }">
              <div class="workflow-index">{{ index + 1 }}</div>
              <div class="workflow-copy">
                <strong>{{ step.title }}</strong>
                <span>{{ step.note }}</span>
              </div>
            </div>
          </div>
        </section>

        <section class="panel chat-panel guide-target-chat">
          <div class="lab-panel-heading">
            <div>
              <h2 class="panel-title">回答对比</h2>
              <p>投毒前回答只使用可信知识库；投毒后回答混合当前 session 注入样本。</p>
            </div>
            <el-tag effect="dark">{{ sessionId || 'SESSION 初始化中' }}</el-tag>
          </div>

          <div v-if="!beforeChat && !afterChat" class="chat-empty">
            <el-icon><ChatDotRound /></el-icon>
            <span>请输入问题并执行检测，系统将在此展示检索过程、来源证据和回答分析。</span>
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
                    <div v-for="chunk in topkBefore" :key="`before-chat-${chunk.chunk_id}`" class="citation-card">
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
                    <div v-for="chunk in topkAfter" :key="`after-chat-${chunk.chunk_id}`" class="citation-card">
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
        </section>

        <section class="panel evidence-panel">
          <div class="lab-panel-heading">
            <div>
              <h2 class="panel-title">检索证据</h2>
              <p>对比投毒前后 Top-K，观察 poison 或低可信证据是否靠前。</p>
            </div>
          </div>

          <div v-if="!topkBefore.length && !topkAfter.length" class="empty-workbench-card">
            <strong>暂无检索证据</strong>
            <span>请输入问题并执行投毒前/投毒后提问，系统将在此展示来源证据、相似度和检索排名。</span>
          </div>

          <div v-else class="evidence-grid">
            <div>
              <h3>投毒前 Top-K</h3>
              <div class="topk-list guide-target-topk-before">
                <div v-for="chunk in topkBefore" :key="`before-${chunk.chunk_id}`" class="citation-card">
                  <div><code>#{{ chunk.rank }} {{ chunk.chunk_id }}</code><el-tag size="small" :type="tagType(chunk.trust_label)">{{ chunk.trust_label }}</el-tag></div>
                  <p>{{ chunk.content }}</p>
                  <small>similarity {{ chunk.similarity ?? chunk.score }}</small>
                </div>
                <el-empty v-if="!topkBefore.length" description="暂无投毒前检索结果" />
              </div>
            </div>
            <div>
              <h3>投毒后 Top-K</h3>
              <div class="topk-list guide-target-topk-after">
                <div v-for="chunk in topkAfter" :key="`after-${chunk.chunk_id}`" class="citation-card">
                  <div><code>#{{ chunk.rank }} {{ chunk.chunk_id }}</code><el-tag size="small" :type="tagType(chunk.trust_label)">{{ chunk.trust_label }}</el-tag></div>
                  <p>{{ chunk.content }}</p>
                  <small>similarity {{ chunk.similarity ?? chunk.score }}</small>
                </div>
                <el-empty v-if="!topkAfter.length" description="暂无投毒后检索结果" />
              </div>
            </div>
          </div>
        </section>
      </main>

      <aside class="panel result-panel guide-target-correction">
        <div class="lab-panel-heading">
          <div>
            <h2 class="panel-title">检测结果</h2>
            <p>风险评分、检测指标和后续处置入口集中展示。</p>
          </div>
        </div>

        <template v-if="detection">
          <div class="risk-score-block">
            <div>
              <span>总体风险</span>
              <strong>{{ riskPercent }}%</strong>
            </div>
            <el-tag :type="detection.risk_level === 'high' ? 'danger' : detection.risk_level === 'medium' ? 'warning' : 'success'">
              {{ detection.risk_level }}
            </el-tag>
          </div>
          <el-progress :percentage="riskPercent" :status="riskPercent >= 70 ? 'exception' : riskPercent >= 35 ? 'warning' : 'success'" />

          <div class="result-metric-grid">
            <div v-for="key in ['RAS', 'GIS', 'DualRisk']" :key="key">
              <span>{{ key }}</span>
              <strong>{{ Number(detection.metrics?.[key] || 0).toFixed(3) }}</strong>
            </div>
          </div>

          <div class="risk-reason-section">
            <h3>风险原因</h3>
            <div class="risk-reason-list">
              <el-tag
                v-for="item in detection.risk_types || ['低风险观察项']"
                :key="item"
                :type="detection.risk_level === 'high' ? 'danger' : 'info'"
                effect="plain"
              >
                {{ item }}
              </el-tag>
            </div>
          </div>

          <div class="result-actions">
            <el-button type="primary" :icon="Share" @click="enterPropagation">
              构建投毒传播图谱
            </el-button>
            <el-button v-if="canEnterCorrection" type="danger" :icon="Right" @click="enterCorrection">
              进入可信纠偏
            </el-button>
          </div>
        </template>

        <div v-else class="result-empty">
          <el-icon><ChatDotRound /></el-icon>
          <strong>等待检测结果</strong>
          <span>完成投毒前提问、注入样本并投毒后提问后，点击“执行投毒检测”。风险百分比、RAS/GIS/DualRisk 和后续操作会在这里集中展示。</span>
        </div>
      </aside>
    </div>
  </div>
</template>
