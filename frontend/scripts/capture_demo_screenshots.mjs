import { chromium } from 'playwright'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const repoRoot = path.resolve(__dirname, '../..')
const screenshotDir = path.join(repoRoot, 'docs', 'screenshots')
const baseUrl = process.env.DEMO_BASE_URL || 'http://127.0.0.1:5173'

async function waitForApp(page) {
  await page.waitForLoadState('networkidle', { timeout: 45000 }).catch(() => {})
  await page.waitForTimeout(800)
}

async function clickIfVisible(page, text, timeout = 45000) {
  const locator = page.getByText(text, { exact: false }).first()
  await locator.waitFor({ state: 'visible', timeout })
  await locator.click()
}

async function main() {
  const browser = await chromium.launch({ headless: true })
  const page = await browser.newPage({ viewport: { width: 1440, height: 960 }, deviceScaleFactor: 1 })

  await page.goto(`${baseUrl}/external-knowledge`, { waitUntil: 'domcontentloaded' })
  await waitForApp(page)
  await page.screenshot({ path: path.join(screenshotDir, 'external_knowledge.png'), fullPage: true })

  await page.goto(`${baseUrl}/interactive-rag-lab`, { waitUntil: 'domcontentloaded' })
  await waitForApp(page)
  await clickIfVisible(page, '投毒前提问')
  await waitForApp(page)
  await clickIfVisible(page, '注入样本并投毒后提问')
  await waitForApp(page)
  await clickIfVisible(page, '执行投毒检测')
  await waitForApp(page)
  await page.screenshot({ path: path.join(screenshotDir, 'interactive_rag_lab.png'), fullPage: true })

  const correctionButton = page.getByText('进入可信纠偏', { exact: false }).first()
  if (await correctionButton.isVisible().catch(() => false)) {
    await correctionButton.click()
    await waitForApp(page)
  } else {
    const tag = await page.locator('.el-tag').filter({ hasText: 'SESSION-' }).first().textContent()
    const sessionId = (tag || '').trim()
    if (sessionId) {
      await page.goto(`${baseUrl}/interactive-correction/${sessionId}`, { waitUntil: 'domcontentloaded' })
      await waitForApp(page)
    }
  }

  for (const label of ['运行反事实验证', '隔离高风险 Chunk', '可信重生成', '生成纠偏报告']) {
    const button = page.getByText(label, { exact: false }).first()
    if (await button.isVisible().catch(() => false)) {
      await button.click()
      await waitForApp(page)
    }
  }
  await page.screenshot({ path: path.join(screenshotDir, 'interactive_correction.png'), fullPage: true })

  await browser.close()
  console.log(`Screenshots saved to ${screenshotDir}`)
}

main().catch(error => {
  console.error(error)
  process.exit(1)
})
