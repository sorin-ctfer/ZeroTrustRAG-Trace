<script setup lang="ts">
import * as echarts from 'echarts'
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'

const props = defineProps<{ before: number; after: number }>()
const root = ref<HTMLElement>()
let chart: echarts.ECharts | undefined

const render = async () => {
  await nextTick()
  if (!root.value) return
  chart ||= echarts.init(root.value)
  chart.setOption({
    tooltip: { trigger: 'axis' },
    grid: { left: 45, right: 20, top: 25, bottom: 35 },
    xAxis: { type: 'category', data: ['纠偏前', '纠偏后'] },
    yAxis: { type: 'value', min: 0, max: 100, name: 'TrustScore' },
    series: [{
      type: 'bar',
      barWidth: 64,
      data: [
        { value: props.before, itemStyle: { color: '#e25555' } },
        { value: props.after, itemStyle: { color: '#25a18e' } },
      ],
      label: { show: true, position: 'top', fontSize: 16, fontWeight: 'bold' },
    }],
  })
}
watch(() => [props.before, props.after], render)
onMounted(() => { render(); window.addEventListener('resize', render) })
onBeforeUnmount(() => { window.removeEventListener('resize', render); chart?.dispose() })
</script>

<template><div ref="root" class="score-chart" /></template>
