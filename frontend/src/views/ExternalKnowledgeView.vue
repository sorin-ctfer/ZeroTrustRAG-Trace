<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { externalKnowledgeApi } from '@/api/lab'

const chunks = ref<any[]>([])
const stats = ref<any>({})
const datasetJsonl = ref('')
const loading = ref(false)

const refresh = async () => {
  chunks.value = await externalKnowledgeApi.chunks()
  stats.value = await externalKnowledgeApi.stats()
}
const run = async (task: () => Promise<any>, message: string) => {
  loading.value = true
  try {
    await task()
    await refresh()
    ElMessage.success(message)
  } catch (error: any) {
    ElMessage.error(error.message || '操作失败')
  } finally {
    loading.value = false
  }
}
const upload = async (option: any) => {
  await run(() => externalKnowledgeApi.upload(option.file), '可信文档已导入')
}
onMounted(refresh)
</script>

<template>
  <div class="page-head">
    <h1>外部可信知识库</h1>
    <p>统一导入可信文档、内置数据集和 clean_chunks，AI 交互实验室只读取这里的可信 Chunk。</p>
  </div>

  <div class="stat-grid">
    <div class="stat-card"><div class="label">Trusted Chunks</div><div class="value">{{ stats.chunk_count || 0 }}</div></div>
    <div class="stat-card"><div class="label">Documents</div><div class="value">{{ stats.document_count || 0 }}</div></div>
    <div class="stat-card"><div class="label">Embedding Ready</div><div class="value">{{ stats.embedding_ready || 0 }}</div></div>
    <div class="stat-card"><div class="label">Index</div><div class="value small-value">{{ stats.index_status || 'unknown' }}</div></div>
  </div>

  <section class="panel">
    <h2 class="panel-title">导入可信来源</h2>
    <div class="knowledge-actions">
      <el-upload :show-file-list="false" :http-request="upload" accept=".txt,.md,.pdf,.docx,.jsonl">
        <el-button type="primary" :loading="loading">上传 txt / md / pdf / docx / jsonl</el-button>
      </el-upload>
      <el-button :loading="loading" @click="run(() => externalKnowledgeApi.loadDemo(), '内置可信知识已加载')">加载内置可信知识样例</el-button>
      <el-button :loading="loading" @click="run(() => externalKnowledgeApi.rebuildIndex(), 'FAISS/检索索引已重建')">重建 FAISS 索引</el-button>
      <el-button type="danger" plain :loading="loading" @click="run(() => externalKnowledgeApi.clear(), '外部知识库已清空')">清空外部知识库</el-button>
    </div>
    <el-input v-model="datasetJsonl" type="textarea" :rows="5" placeholder='粘贴 JSONL，每行包含 {"clean_chunks": ["..."]}' />
    <el-button class="mt-12" :loading="loading" @click="run(() => externalKnowledgeApi.importDatasetClean(datasetJsonl), 'JSONL clean_chunks 已导入')">导入 JSONL clean_chunks</el-button>
  </section>

  <section class="panel">
    <h2 class="panel-title">可信 Chunk 列表</h2>
    <el-table :data="chunks" height="520">
      <el-table-column prop="source" label="来源" width="190" show-overflow-tooltip />
      <el-table-column prop="document_id" label="文档 ID" width="150" />
      <el-table-column prop="chunk_id" label="Chunk ID" width="190" />
      <el-table-column prop="content" label="内容摘要" show-overflow-tooltip />
      <el-table-column prop="updated_at" label="更新时间" width="190" />
      <el-table-column prop="content_hash" label="Hash" width="130" />
      <el-table-column prop="embedding_status" label="向量状态" width="100" />
    </el-table>
  </section>
</template>
