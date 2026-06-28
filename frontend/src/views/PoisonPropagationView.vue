<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { RefreshRight, Right, Share } from '@element-plus/icons-vue'
import GraphChart from '@/components/GraphChart.vue'
import { interactiveSessionApi, poisonPropagationApi } from '@/api/lab'

const route = useRoute()
const router = useRouter()
const sessionId = ref(String(route.params.session_id || ''))
const sessions = ref<any[]>([])
const result = ref<any>()
const loading = ref(false)
const error = ref('')

const summary = computed(() => result.value?.summary || {})
const similarChunks = computed(() => result.value?.similar_poison_chunks || [])
const paths = computed(() => result.value?.propagation_paths || [])

const loadSessions = async () => {
  sessions.value = await interactiveSessionApi.sessions()
  if (!sessionId.value) {
    const detected = sessions.value.find(item => item.has_detection)
    sessionId.value = detected?.session_id || sessions.value[0]?.session_id || ''
  }
}

const buildGraph = async () => {
  if (!sessionId.value) {
    ElMessage.warning('请选择一个实验 session')
    return
  }
  loading.value = true
  error.value = ''
  try {
    result.value = await poisonPropagationApi.build(sessionId.value)
  } catch (err: any) {
    error.value = err.message || '传播图谱构建失败'
    result.value = undefined
  } finally {
    loading.value = false
  }
}

watch(() => route.params.session_id, value => {
  sessionId.value = String(value || '')
  if (sessionId.value) buildGraph()
})

onMounted(async () => {
  await loadSessions()
  if (sessionId.value) await buildGraph()
})
</script>

<template>
  <div class="page-head">
    <h1>RAG 投毒传播图谱构建</h1>
    <p>基于实验检测结果构建 Query、Answer、Chunk、Document、Claim 异构知识图谱，定位相似投毒片段与传播路径。</p>
  </div>

  <el-alert v-if="error" class="error-alert" type="error" :title="error" show-icon :closable="false" />

  <section class="panel">
    <div class="toolbar">
      <el-select v-model="sessionId" style="width: 520px" placeholder="选择已检测 Session" filterable>
        <el-option
          v-for="item in sessions"
          :key="item.session_id"
          :label="`${item.session_id} · ${item.risk_level} · ${item.question || '未记录问题'}`"
          :value="item.session_id"
        />
      </el-select>
      <el-button type="primary" :icon="Share" :loading="loading" @click="buildGraph">构建传播图谱</el-button>
      <el-button :icon="RefreshRight" @click="loadSessions">刷新 Session</el-button>
      <el-button :icon="Right" @click="router.push('/interactive-rag-lab')">返回交互实验室</el-button>
    </div>
  </section>

  <template v-if="result">
    <div class="stat-grid propagation-stats">
      <div class="stat-card"><div class="label">图谱节点</div><div class="value">{{ summary.node_count }}</div></div>
      <div class="stat-card"><div class="label">关系边</div><div class="value">{{ summary.edge_count }}</div></div>
      <div class="stat-card"><div class="label">高风险 Chunk</div><div class="value">{{ summary.risk_node_count }}</div></div>
      <div class="stat-card"><div class="label">相似投毒片段</div><div class="value">{{ summary.similar_poison_count }}</div></div>
      <div class="stat-card"><div class="label">图谱方法</div><div class="value small-value">{{ summary.graph_method }}</div></div>
    </div>
    <el-alert
      v-if="summary.backend_note"
      class="error-alert"
      type="info"
      show-icon
      :closable="false"
      :title="summary.backend_note"
    />

    <section class="panel propagation-layout">
      <div>
        <h2 class="panel-title">异构投毒传播知识图谱</h2>
        <GraphChart :graph="result.graph" />
      </div>
      <aside>
        <h2 class="panel-title">传播路径</h2>
        <el-timeline>
          <el-timeline-item v-for="item in paths" :key="`${item.anchor_chunk_id}-${item.similar_chunk_id}`" type="danger">
            <strong>{{ item.relation }}</strong>
            <p>{{ item.source }}</p>
            <small>{{ item.anchor_chunk_id }} -> {{ item.similar_chunk_id }} · similarity {{ item.similarity }}</small>
          </el-timeline-item>
        </el-timeline>
        <el-empty v-if="!paths.length" description="暂无传播路径" />
      </aside>
    </section>

    <section class="panel">
      <h2 class="panel-title">相似投毒片段</h2>
      <el-table :data="similarChunks" stripe>
        <el-table-column prop="gat_score" label="GAT 分数" width="110" />
        <el-table-column prop="similarity_to_anchor" label="相似度" width="100" />
        <el-table-column prop="attack_type" label="攻击类型" width="150" />
        <el-table-column prop="source" label="来源" width="180" show-overflow-tooltip />
        <el-table-column prop="anchor_chunk_id" label="锚点 Chunk" width="190" show-overflow-tooltip />
        <el-table-column label="同错误声明" width="110">
          <template #default="{ row }">
            <el-tag :type="row.same_claim ? 'danger' : 'info'">{{ row.same_claim ? '是' : '否' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="content" label="片段内容" min-width="420" show-overflow-tooltip />
      </el-table>
    </section>
  </template>

  <el-empty v-else-if="!loading" description="请选择已完成投毒检测的 session 后构建传播图谱" />
</template>
