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
  const categoryNames = (props.graph.categories || ['Claim', 'Evidence', 'Action']).map((item: any) =>
    typeof item === 'string' ? { name: item } : item,
  )
  const palette = ['#3b82f6', '#25a18e', '#8b5cf6', '#f59e0b', '#64748b']
  chart.setOption({
    tooltip: {
      formatter: (p: any) => {
        if (p.dataType === 'edge') return `${p.data.source} → ${p.data.target}<br/>${p.data.type || ''}`
        return `${p.data?.name || p.data?.id}<br/>风险：${Number(p.data?.risk || 0).toFixed(2)}`
      },
    },
    legend: [{ data: categoryNames.map((item: any) => item.name), bottom: 0 }],
    series: [{
      type: 'graph', layout: 'force', roam: true, draggable: true,
      data: (props.graph.nodes || []).map((n: any) => ({
        ...n, symbolSize: 32 + (n.risk || 0) * 24,
        itemStyle: {
          color: (n.risk || 0) >= .6 ? '#e25555' : palette[n.category || 0],
          borderColor: '#fff', borderWidth: 2, shadowBlur: 8, shadowColor: '#0002',
        },
      })),
      links: props.graph.links || [], categories: categoryNames,
      label: { show: true, fontSize: 11, color: '#24324a' },
      edgeSymbol: ['none', 'arrow'], edgeSymbolSize: 8,
      edgeLabel: {
        show: true, formatter: (p: any) => p.data.type || '', fontSize: 9,
        color: '#52627a', backgroundColor: '#ffffffdd', padding: [2, 3],
      },
      force: { repulsion: 420, edgeLength: [105, 190], gravity: .08 },
      lineStyle: { color: 'source', curveness: .08, opacity: .72, width: 1.5 },
      emphasis: { focus: 'adjacency', lineStyle: { width: 4, opacity: 1 } },
    }],
  }, true)
}
watch(() => props.graph, render, { deep: true })
onMounted(() => { render(); window.addEventListener('resize', render) })
onBeforeUnmount(() => { window.removeEventListener('resize', render); chart?.dispose() })
</script>

<template><div ref="root" class="chart" /></template>
