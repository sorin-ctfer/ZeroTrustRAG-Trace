<script setup lang="ts">
import { useRoute } from 'vue-router'
import {
  DataAnalysis, Document, Files, Finished, Grid, RefreshRight, Share, Warning,
} from '@element-plus/icons-vue'

const route = useRoute()
const menus = [
  ['/dashboard', '系统仪表盘', Grid],
  ['/knowledge', '知识库管理', Files],
  ['/rag-detection', 'RAG 投毒检测', Warning],
  ['/agent-trust', 'Agent 零信任', Finished],
  ['/cascade-detection', '级联错误检测', DataAnalysis],
  ['/trace-graph', '联合溯源图谱', Share],
  ['/correction', '可信纠偏', RefreshRight],
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
      <div class="sidebar-footer">本地规则引擎 · 无需 LLM API</div>
    </el-aside>
    <el-container>
      <el-header class="topbar">
        <div>
          <strong>多 Agent 零信任协同与 RAG 知识投毒因果验证</strong>
          <span>信息污染溯源纠偏系统</span>
        </div>
        <el-tag type="success" effect="dark">MVP 在线</el-tag>
      </el-header>
      <el-main class="main-content"><router-view /></el-main>
    </el-container>
  </el-container>
</template>
