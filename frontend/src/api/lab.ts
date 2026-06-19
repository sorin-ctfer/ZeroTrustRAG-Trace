import { api, unwrap } from '@/api'

export const externalKnowledgeApi = {
  upload: async (file: File) => {
    const form = new FormData()
    form.append('file', file)
    return unwrap<any[]>(await api.post('/external-knowledge/upload', form))
  },
  importDatasetClean: async (jsonl: string, dataset_name = 'JSONL 数据集') =>
    unwrap<any[]>(await api.post('/external-knowledge/import-dataset-clean', { jsonl, dataset_name })),
  loadDemo: async () => unwrap<any[]>(await api.post('/external-knowledge/load-demo')),
  chunks: async () => unwrap<any[]>(await api.get('/external-knowledge/chunks')),
  stats: async () => unwrap<any>(await api.get('/external-knowledge/stats')),
  rebuildIndex: async () => unwrap<any>(await api.post('/external-knowledge/rebuild-index')),
  clear: async () => unwrap<any[]>(await api.post('/external-knowledge/clear')),
}

export const poisonSamplesApi = {
  create: async (payload: any) => unwrap<any>(await api.post('/poison-samples/create', payload)),
  loadDemo: async () => unwrap<any[]>(await api.post('/poison-samples/load-demo')),
  loadFromTraining: async (limit = 80) => unwrap<any[]>(await api.post('/poison-samples/load-from-training', { limit })),
  list: async () => unwrap<any[]>(await api.get('/poison-samples/list')),
  enable: async (sampleId: string) => unwrap<any>(await api.post(`/poison-samples/${sampleId}/enable`)),
  disable: async (sampleId: string) => unwrap<any>(await api.post(`/poison-samples/${sampleId}/disable`)),
  remove: async (sampleId: string) => unwrap<any>(await api.delete(`/poison-samples/${sampleId}`)),
  injectToSession: async (session_id: string, sample_id: string) =>
    unwrap<any>(await api.post('/poison-samples/inject-to-session', { session_id, sample_id })),
}

export const interactiveSessionApi = {
  create: async () => unwrap<any>(await api.post('/interactive/session/create')),
  sessions: async () => unwrap<any[]>(await api.get('/interactive/sessions')),
  get: async (sessionId: string) => unwrap<any>(await api.get(`/interactive/session/${sessionId}`)),
  injectPoison: async (sessionId: string, sample_id: string) =>
    unwrap<any>(await api.post(`/interactive/session/${sessionId}/inject-poison`, { sample_id })),
  riskSummary: async (sessionId: string) => unwrap<any>(await api.get(`/interactive/session/${sessionId}/risk-summary`)),
  chat: async (question: string, stage: string, session_id?: string) =>
    unwrap<any>(await api.post('/interactive/rag/chat', { question, stage, session_id })),
  detect: async (payload: any) => unwrap<any>(await api.post('/interactive/rag/chat-detect', payload)),
  report: async (sessionId: string) => unwrap<any>(await api.get(`/interactive/report/${sessionId}`)),
}

export const interactiveCorrectionApi = {
  detail: async (sessionId: string) => unwrap<any>(await api.get(`/interactive/correction/${sessionId}/detail`)),
  counterfactual: async (sessionId: string) => unwrap<any>(await api.post(`/interactive/correction/${sessionId}/counterfactual`)),
  quarantine: async (sessionId: string) => unwrap<any>(await api.post(`/interactive/correction/${sessionId}/quarantine`)),
  regenerate: async (sessionId: string) => unwrap<any>(await api.post(`/interactive/correction/${sessionId}/regenerate`)),
  report: async (sessionId: string) => unwrap<any>(await api.get(`/interactive/correction/${sessionId}/report`)),
}

export const poisonPropagationApi = {
  build: async (sessionId: string) => unwrap<any>(await api.get(`/interactive/propagation/${sessionId}`)),
}

export const trainingApi = {
  importDataset: async (jsonl: string, name = 'imported_jsonl') =>
    unwrap<any>(await api.post('/datasets/import', { jsonl, name })),
  loadDemo: async () => unwrap<any>(await api.post('/datasets/load-demo')),
  list: async () => unwrap<any[]>(await api.get('/datasets/list')),
  stats: async () => unwrap<any>(await api.get('/datasets/stats')),
  samples: async () => unwrap<any[]>(await api.get('/datasets/samples')),
  reset: async () => unwrap<any[]>(await api.post('/datasets/reset')),
  train: async (model_type = 'logistic_regression') =>
    unwrap<any>(await api.post('/training/rag-detector/train', { model_type })),
  status: async () => unwrap<any>(await api.get('/training/rag-detector/status')),
  metrics: async () => unwrap<any>(await api.get('/training/rag-detector/metrics')),
  predict: async (texts: string[], query = '', correct_answer = '', target_wrong_answer = '') =>
    unwrap<any>(await api.post('/training/rag-detector/predict', { texts, query, correct_answer, target_wrong_answer })),
  publicSources: async () => unwrap<any[]>(await api.get('/datasets/public/sources')),
  publicDownload: async (source_keys?: string[], force = false) =>
    unwrap<any[]>(await api.post('/datasets/public/download', { source_keys, force })),
  publicConvert: async (source_key?: string, limit = 120) =>
    unwrap<any>(await api.post('/datasets/public/convert', { source_key, limit })),
  publicImportTraining: async (source_key?: string, limit = 120) =>
    unwrap<any>(await api.post('/datasets/public/import-training', { source_key, limit })),
  publicImportCleanKnowledge: async (source_key: string, limit = 120) =>
    unwrap<any>(await api.post('/datasets/public/import-clean-knowledge', { source_key, limit })),
}
