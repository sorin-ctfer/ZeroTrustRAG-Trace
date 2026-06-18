import { api, unwrap } from '@/api'

export interface InteractiveChunk {
  chunk_id: string
  content: string
  source: string
  trust_level: string
  risk_score: number
  is_poison_candidate: boolean
  metadata?: Record<string, unknown>
}

export interface ChatResult {
  session_id: string
  question: string
  answer: string
  stage: string
  cited_chunk_ids: string[]
  retrieved_chunks: Array<InteractiveChunk & { rank: number; score: number }>
}

export const addTrustedKnowledge = async (content: string, source = 'manual_trusted') =>
  unwrap<InteractiveChunk[]>(await api.post('/interactive/knowledge/trusted', { content, source }))

export const injectPoisonKnowledge = async (content: string, source = 'manual_poison') =>
  unwrap<InteractiveChunk[]>(await api.post('/interactive/knowledge/poison', { content, source }))

export const listInteractiveChunks = async () =>
  unwrap<InteractiveChunk[]>(await api.get('/interactive/knowledge/chunks'))

export const resetInteractiveLab = async () =>
  unwrap<{ chunks: InteractiveChunk[]; sessions_cleared: boolean }>(
    await api.post('/interactive/knowledge/reset'),
  )

export const interactiveChat = async (
  question: string,
  stage: string,
  sessionId?: string,
) => unwrap<ChatResult>(await api.post('/interactive/rag/chat', {
  question,
  stage,
  session_id: sessionId,
}))

export const detectInteractivePoison = async (payload: {
  session_id: string
  question: string
  before_answer: string
  after_answer: string
}) => unwrap<any>(await api.post('/interactive/rag/chat-detect', payload))

export const quarantineChunks = async (sessionId: string, chunkIds: string[]) =>
  unwrap<InteractiveChunk[]>(await api.post('/interactive/correction/quarantine', {
    session_id: sessionId,
    chunk_ids: chunkIds,
  }))

export const regenerateCorrectedAnswer = async (sessionId: string, question: string) =>
  unwrap<any>(await api.post('/interactive/correction/regenerate', {
    session_id: sessionId,
    question,
  }))

export const getInteractiveReport = async (sessionId: string) =>
  unwrap<any>(await api.get(`/interactive/report/${sessionId}`))
