<script setup lang="ts">
import * as echarts from 'echarts'
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'

const props = defineProps<{ graph: { nodes?: any[]; links?: any[]; categories?: any[] } }>()
const root = ref<HTMLElement>()
let chart: echarts.ECharts | undefined

const render = async () => {
  await nextTick()
  if (!root.value) return
  chart ||= echarts.init(root.value)
  const categoryNames = (props.graph.categories || ['Agent', 'Claim', 'Evidence', 'Action']).map((item: any) =>
    typeof item === 'string' ? { name: item } : item,
  )
  chart.setOption({
    tooltip: { formatter: (p: any) => p.data?.name || p.data?.type || '' },
    legend: [{ data: categoryNames.map((item: any) => item.name), bottom: 0 }],
    series: [{
      type: 'graph', layout: 'force', roam: true, draggable: true,
      data: (props.graph.nodes || []).map((n: any) => ({
        ...n, symbolSize: 28 + (n.risk || 0) * 26,
        itemStyle: { color: (n.risk || 0) >= .6 ? '#e25555' : n.category === 0 ? '#3b82f6' : '#25a18e' },
      })),
      links: props.graph.links || [], categories: categoryNames,
      label: { show: true, fontSize: 10 },
      edgeLabel: { show: true, formatter: (p: any) => p.data.type || '' },
      force: { repulsion: 320, edgeLength: [80, 160] },
      lineStyle: { color: 'source', curveness: .08, opacity: .65 },
    }],
  }, true)
}
watch(() => props.graph, render, { deep: true })
onMounted(() => { render(); window.addEventListener('resize', render) })
onBeforeUnmount(() => { window.removeEventListener('resize', render); chart?.dispose() })
</script>

<template><div ref="root" class="chart" /></template>
