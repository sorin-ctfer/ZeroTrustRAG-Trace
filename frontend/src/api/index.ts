import axios from 'axios'

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE || '/api',
  timeout: 30000,
})

export const unwrap = <T>(response: { data: { success?: boolean; data: T; error?: string } }): T => {
  if (response.data.success === false) throw new Error(response.data.error || '请求失败')
  return response.data.data
}
