<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'
import {
  Coin,
  DataAnalysis,
  Document,
  Files,
  Fold,
  Grid,
  Menu as MenuIcon,
  Search,
  Share,
} from '@element-plus/icons-vue'

const route = useRoute()
const collapsed = ref(false)

const menuGroups = [
  {
    title: '运行概览',
    items: [
      ['/dashboard', '系统仪表盘', Grid],
      ['/reports', '风险报告', Document],
    ],
  },
  {
    title: '知识与数据',
    items: [
      ['/external-knowledge', '外部可信知识库', Files],
      ['/knowledge', '知识库管理', Files],
      ['/rag-training', 'RAG 训练评测', DataAnalysis],
      ['/poison-samples', '演示投毒样本', Coin],
    ],
  },
  {
    title: '检测处置',
    items: [
      ['/interactive-rag-lab', '交互实验室', Search],
      ['/poison-propagation', '投毒传播图谱', Share],
    ],
  },
]

const titleMap = new Map(
  menuGroups.flatMap(group => group.items.map(([path, label]) => [path, label])),
)
titleMap.set('/interactive-correction', '可信纠偏')

const currentTitle = computed(() => {
  const direct = titleMap.get(route.path)
  if (direct) return direct
  if (route.path.startsWith('/interactive-correction')) return '可信纠偏'
  if (route.path.startsWith('/poison-propagation')) return '投毒传播图谱'
  return '工作台'
})
</script>

<template>
  <el-container class="app-shell" :class="{ 'is-collapsed': collapsed }">
    <el-aside :width="collapsed ? '72px' : '252px'" class="sidebar">
      <div class="sidebar-head">
        <el-button text :icon="collapsed ? MenuIcon : Fold" @click="collapsed = !collapsed" />
        <span v-if="!collapsed">系统菜单</span>
      </div>

      <el-menu :default-active="route.path" router class="nav-menu" :collapse="collapsed">
        <template v-for="group in menuGroups" :key="group.title">
          <div v-if="!collapsed" class="nav-group-title">{{ group.title }}</div>
          <el-menu-item
            v-for="[path, label, icon] in group.items"
            :key="String(path)"
            :index="String(path)"
          >
            <el-icon><component :is="icon" /></el-icon>
            <template #title>{{ label }}</template>
          </el-menu-item>
        </template>
      </el-menu>
    </el-aside>

    <el-container class="workspace">
      <el-header class="topbar">
        <div class="topbar-left">
          <el-button text class="mobile-menu" :icon="collapsed ? MenuIcon : Fold" @click="collapsed = !collapsed" />
          <el-breadcrumb separator="/">
            <el-breadcrumb-item>工作台</el-breadcrumb-item>
            <el-breadcrumb-item>{{ currentTitle }}</el-breadcrumb-item>
          </el-breadcrumb>
          <strong>{{ currentTitle }}</strong>
        </div>
        <div class="topbar-actions">
          <el-tag type="success" effect="plain">服务正常</el-tag>
        </div>
      </el-header>
      <el-main class="main-content"><router-view /></el-main>
    </el-container>
  </el-container>
</template>
