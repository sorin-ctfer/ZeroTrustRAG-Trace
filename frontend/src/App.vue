<script setup lang="ts">
import { useRoute } from 'vue-router'
import {
  ChatDotRound, Coin, DataAnalysis, Document, Files, Grid,
} from '@element-plus/icons-vue'

const route = useRoute()
const menus = [
  ['/dashboard', '系统仪表盘', Grid],
  ['/rag-training', 'RAG 训练评测', DataAnalysis],
  ['/poison-samples', '演示投毒知识', Coin],
  ['/knowledge', '知识库管理', Files],
  ['/interactive-rag-lab', 'AI 交互实验室', ChatDotRound],
  ['/reports', '风险报告', Document],
]
</script>

<template>
  <el-container class="app-shell">
    <el-aside width="244px" class="sidebar">
      <div class="brand">
        <div class="brand-mark">智</div>
        <div><strong>智源净域</strong><span>RAGweblab</span></div>
      </div>
      <el-menu :default-active="route.path" router class="nav-menu">
        <el-menu-item v-for="[path, label, icon] in menus" :key="String(path)" :index="String(path)">
          <el-icon><component :is="icon" /></el-icon><span>{{ label }}</span>
        </el-menu-item>
      </el-menu>
      <div class="sidebar-footer">本地规则 + 百炼增强模式</div>
    </el-aside>
    <el-container>
      <el-header class="topbar">
        <div>
          <strong>RAG 知识投毒检测、因果验证与可信纠偏</strong>
          <span>信息污染溯源纠偏系统</span>
        </div>
        <el-tag type="success" effect="dark">MVP 在线</el-tag>
      </el-header>
      <el-main class="main-content"><router-view /></el-main>
    </el-container>
  </el-container>
</template>
