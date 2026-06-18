<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { trainingApi } from '@/api/lab'

const jsonl = ref('')
const stats = ref<any>({})
const status = ref<any>({})
const metrics = ref<any>({})
const samples = ref<any[]>([])
const publicSources = ref<any[]>([])
const loading = ref(false)
const modelType = ref('logistic_regression')
const publicLimit = ref(120)
const selectedPublicSource = ref('safe_rag_nctd')
const matrix = computed(() => metrics.value.confusion_matrix || [[0, 0], [0, 0]])

const refresh = async () => {
  stats.value = await trainingApi.stats()
  status.value = await trainingApi.status()
  metrics.value = await trainingApi.metrics()
  samples.value = await trainingApi.samples()
  publicSources.value = await trainingApi.publicSources()
  if (!publicSources.value.some(item => item.key === selectedPublicSource.value) && publicSources.value[0]) {
    selectedPublicSource.value = publicSources.value[0].key
  }
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
onMounted(refresh)
</script>

<template>
  <div class="page-head">
    <h1>RAG 训练评测</h1>
    <p>导入 PoisonBench JSONL，使用 scikit-learn 训练 RAS/GIS 检测模型；没有模型时自动 fallback 到规则模式。</p>
  </div>

  <div class="stat-grid">
    <div class="stat-card"><div class="label">样本数</div><div class="value">{{ stats.sample_count || 0 }}</div></div>
    <div class="stat-card"><div class="label">Clean</div><div class="value">{{ stats.clean_chunks || 0 }}</div></div>
    <div class="stat-card"><div class="label">Poison</div><div class="value">{{ stats.poison_chunks || 0 }}</div></div>
    <div class="stat-card"><div class="label">检测模式</div><div class="value small-value">{{ status.mode || '规则模式' }}</div></div>
  </div>

  <section class="panel two-col">
    <div>
      <h2 class="panel-title">数据集导入</h2>
      <el-input v-model="jsonl" type="textarea" :rows="9" placeholder='每行 JSON：{"clean_chunks":["..."],"poison_chunks":[{"content":"...","attack_type":"policy_bypass"}]}' />
      <div class="toolbar mt-12">
        <el-button type="primary" :loading="loading" @click="run(() => trainingApi.importDataset(jsonl), '数据集已导入')">导入 JSONL</el-button>
        <el-button :loading="loading" @click="run(() => trainingApi.loadDemo(), '内置 poisonbench_seed 已加载')">加载内置 PoisonBench</el-button>
        <el-button type="danger" plain :loading="loading" @click="run(() => trainingApi.reset(), '训练数据已清空')">重置数据集</el-button>
      </div>
    </div>
    <div>
      <h2 class="panel-title">训练检测模型</h2>
      <el-radio-group v-model="modelType">
        <el-radio-button label="logistic_regression">LogisticRegression</el-radio-button>
        <el-radio-button label="random_forest">RandomForest</el-radio-button>
      </el-radio-group>
      <div class="train-status">
        <el-tag :type="status.model_exists ? 'success' : 'info'" effect="dark">{{ status.training_status || '未训练' }}</el-tag>
        <span>{{ status.trained_at || '尚未训练' }}</span>
      </div>
      <el-button type="primary" size="large" :loading="loading" @click="run(() => trainingApi.train(modelType), '训练完成，指标已由验证集计算')">训练 RAS/GIS 检测模型</el-button>
      <pre class="json-box mini-json">{{ JSON.stringify(stats.attack_type_distribution || {}, null, 2) }}</pre>
    </div>
  </section>

  <section class="panel">
    <h2 class="panel-title">公开数据集接入</h2>
    <div class="toolbar">
      <el-select v-model="selectedPublicSource" style="width: 220px">
        <el-option v-for="item in publicSources" :key="item.key" :label="item.name" :value="item.key" />
      </el-select>
      <el-input-number v-model="publicLimit" :min="10" :max="1000" :step="10" />
      <el-button :loading="loading" @click="run(() => trainingApi.publicDownload([selectedPublicSource]), '公开数据集已下载')">下载</el-button>
      <el-button type="primary" :loading="loading" @click="run(() => trainingApi.publicImportTraining(selectedPublicSource, publicLimit), '公开数据集已转换并导入训练集')">导入训练集</el-button>
      <el-button :loading="loading" @click="run(() => trainingApi.publicImportCleanKnowledge(selectedPublicSource, publicLimit), '可信 clean_chunks 已导入外部知识库')">导入可信知识库</el-button>
      <el-button type="success" :loading="loading" @click="run(() => trainingApi.publicImportTraining(undefined, publicLimit), '全部公开数据集已导入训练集')">导入全部</el-button>
    </div>
    <el-table :data="publicSources" class="mt-12">
      <el-table-column prop="name" label="Dataset" width="180" />
      <el-table-column label="状态" width="140">
        <template #default="{ row }">
          <el-tag :type="row.downloaded ? 'success' : 'info'">{{ row.downloaded ? '已下载' : '未下载' }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="description" label="说明" show-overflow-tooltip />
      <el-table-column prop="converted_path" label="转换输出" width="280" show-overflow-tooltip />
    </el-table>
  </section>

  <section class="panel">
    <h2 class="panel-title">真实评测指标</h2>
    <div class="metric-grid">
      <div v-for="key in ['Precision', 'Recall', 'F1', 'AUC', 'PR_AUC']" :key="key"><span>{{ key }}</span><strong>{{ metrics[key] ?? '-' }}</strong></div>
    </div>
    <div class="confusion">
      <div>TN {{ matrix[0]?.[0] || 0 }}</div><div>FP {{ matrix[0]?.[1] || 0 }}</div>
      <div>FN {{ matrix[1]?.[0] || 0 }}</div><div>TP {{ matrix[1]?.[1] || 0 }}</div>
    </div>
  </section>

  <section class="panel">
    <h2 class="panel-title">样本预览</h2>
    <el-table :data="samples" height="360">
      <el-table-column prop="label" label="Label" width="120" />
      <el-table-column prop="attack_type" label="Attack Type" width="180" />
      <el-table-column prop="query" label="Query" width="240" show-overflow-tooltip />
      <el-table-column prop="text" label="Text" show-overflow-tooltip />
    </el-table>
  </section>
</template>
