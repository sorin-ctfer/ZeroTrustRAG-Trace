import { ref } from 'vue'
import { ElMessage } from 'element-plus'

export const useAsyncTask = () => {
  const loading = ref(false)
  const error = ref('')

  const execute = async <T>(task: () => Promise<T>, successMessage = ''): Promise<T | undefined> => {
    loading.value = true
    error.value = ''
    try {
      const result = await task()
      if (successMessage) ElMessage.success(successMessage)
      return result
    } catch (reason: any) {
      error.value = reason?.response?.data?.error || reason?.message || '接口请求失败'
      ElMessage.error(error.value)
      return undefined
    } finally {
      loading.value = false
    }
  }

  return { loading, error, execute }
}
