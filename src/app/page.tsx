'use client'

import { useEffect, useState, type CSSProperties } from 'react'
import { Check, Download, LoaderCircle } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Separator } from '@/components/ui/separator'
import { Switch } from '@/components/ui/switch'
import { cn } from '@/lib/utils'

type FontStatus = 'loading' | 'loaded' | 'error'

type MonoFontClass = 'font-jethan' | 'font-sysmono'

interface CjkSample {
  readonly text: string
  readonly size: number
}

interface WeightDef {
  readonly name: string
  readonly css: number
  /** CJK 侧字形来源（等宽版仅 Regular/Bold，其余来自 Noto Sans CJK SC 同源设计） */
  readonly cjk: string
  /** 文件大小（构建完成后回填） */
  readonly ttfSize: string
  readonly woff2Size: string
}

interface BuildInfoItem {
  readonly label: string
  readonly detail: string
}

/** 卡片 1 代码块：必须逐字符精确渲染（含中文注释与连字演示） */
const LIGATURE_CODE = [
  'const 波动率 = (prices: number[]): number => {',
  '  // 计算对数收益率 -> 标准差 * sqrt(252)',
  '  const returns = prices',
  '    .slice(1)',
  '    .map((p, i) => Math.log(p / prices[i]));',
  '  const mean = returns.reduce((a, b) => a + b, 0) / returns.length;',
  '  const variance =',
  '    returns.reduce((a, r) => a + (r - mean) ** 2, 0) / (returns.length - 1);',
  '  return Math.sqrt(variance) * Math.sqrt(252) ?? 0;',
  '};',
  '',
  '// 连字演示: -> => <- ->> >= <= === !== :: /* */',
  'if (波动率(prices) >= 0.05 && repo !== null) {',
  '  console.log(`风险 -> 高，建议 => 减仓`);',
  '}',
].join('\n')

/** 卡片 2 中文样例：18px / 16px / 14px 各一行 */
const CJK_SAMPLES: readonly CjkSample[] = [
  { text: '春眠不觉晓，处处闻啼鸟。——孟浩然', size: 18 },
  { text: '全角标点：，。：；？！「」『』（）《》、——……', size: 16 },
  { text: '混排：当 price >= 100 且 qty != 0 时，输出『买入信号』。', size: 14 },
]

/**
 * 卡片 3/4 八档字重定义（JetBrains Mono 全系罗马字重；无 Heavy——上游最重
 * ExtraBold 800）。CJK 侧：思源等宽只有 Regular/Bold，其余字重借 Noto Sans
 * CJK SC（同源设计）按 usWeightClass 就近映射，平手取更重档。
 */
const WEIGHT_LIST: readonly WeightDef[] = [
  { name: 'Thin', css: 100, cjk: 'CJK ← Sans Thin', ttfSize: '12.6MB', woff2Size: '4.2MB' },
  { name: 'ExtraLight', css: 200, cjk: 'CJK ← Sans Light', ttfSize: '12.6MB', woff2Size: '4.7MB' },
  { name: 'Light', css: 300, cjk: 'CJK ← Sans Light', ttfSize: '12.6MB', woff2Size: '4.7MB' },
  { name: 'Regular', css: 400, cjk: 'CJK ← 等宽 Regular', ttfSize: '12.5MB', woff2Size: '4.9MB' },
  { name: 'Medium', css: 500, cjk: 'CJK ← Sans Medium', ttfSize: '12.4MB', woff2Size: '5.0MB' },
  { name: 'SemiBold', css: 600, cjk: 'CJK ← 等宽 Bold', ttfSize: '12.3MB', woff2Size: '5.0MB' },
  { name: 'Bold', css: 700, cjk: 'CJK ← 等宽 Bold', ttfSize: '12.3MB', woff2Size: '5.0MB' },
  { name: 'ExtraBold', css: 800, cjk: 'CJK ← Sans Black', ttfSize: '12.2MB', woff2Size: '4.9MB' },
]

/** 卡片 4 构建配方信息 */
const BUILD_INFO: readonly BuildInfoItem[] = [
  {
    label: 'JetBrains Mono v2.304',
    detail: '英文 / 代码字形来源，8 档罗马字重（Thin 100 → ExtraBold 800）全部优先',
  },
  {
    label: '思源等宽（Noto Sans Mono CJK SC）Regular + Bold',
    detail: '等宽中文：Regular/Bold 两个最常用字重直接用等宽版，补充约 44,000 码位（1200u 宽格）',
  },
  {
    label: 'Noto Sans CJK SC（其余 6 档字重的 CJK 侧）',
    detail: '思源等宽本身只有 R/B 两档，其余字重的中文借 Source Han Sans 同源设计（CJK 字形一致、步进同为 1000u）',
  },
  {
    label: '字重映射：就近映射 + 平手取重',
    detail: 'Thin→Thin、ExtraLight→Light、Light→Light、Medium→Medium、SemiBold→Bold、ExtraBold→Black；中文无 Heavy，最重到 Black',
  },
  {
    label: '等宽网格 2:1（中文 1200u）',
    detail: '拉丁 600u，中文/全角/谚文拉宽至 1200u = 2×600；字形不缩放、居中留白，终端 1 汉字恰占 2 英文格',
  },
  {
    label: '命名 JetHan Mono（不可叫 JetBrains-Source-Han-Mono）',
    detail: '思源 OFL 保留字体名 "Source"，衍生名禁用；JetBrains Mono 无 RFN 但属注册商标，故取中性新名；非 RIBBI 字重走 family+16/17 排版族名规范',
  },
  {
    label: '工具链 fontTools subset + cu2qu + Merger API',
    detail: '子集化、曲线转换与字体拼合；拼合走 Merger API，避开 pyftmerge CLI 只认 --opt=value 的解析坑',
  },
  {
    label: '校验 fontTools 静态检查 + HarfBuzz shaping 对比',
    detail: '每档字重独立校验：拼合前后 shaping 一致性 + 区块级宽度不变量（宽格 1200 / 半角 600）',
  },
  {
    label: 'Windows (Git Bash / MSYS2) 可直接构建',
    detail: '脚本自带 CRLF 自愈守卫、自动定位 python、无 unzip 时 zipfile 兜底',
  },
  {
    label: 'CI: GitHub Actions build-font',
    detail: 'font-build 变更自动构建 8 档字重并上传产物，手动 dispatch 可发 Release',
  },
]

const HEADER_BADGES: readonly { readonly text: string; readonly className: string }[] = [
  { text: 'calt 连字 ✓', className: 'border-emerald-200 bg-emerald-50 text-emerald-700' },
  { text: '8 档字重', className: 'border-amber-200 bg-amber-50 text-amber-700' },
  { text: 'CJK ~44,000 码位', className: 'border-amber-200 bg-amber-50 text-amber-700' },
  { text: '中英混排 ✓', className: 'border-emerald-200 bg-emerald-50 text-emerald-700' },
  { text: '终端 2:1 等宽 ✓', className: 'border-emerald-200 bg-emerald-50 text-emerald-700' },
  { text: 'OFL-1.1', className: 'border-zinc-200 bg-zinc-50 text-zinc-600' },
]

export default function Home() {
  const [compareMode, setCompareMode] = useState<boolean>(false)
  const [caltOn, setCaltOn] = useState<boolean>(true)
  const [ligaOn, setLigaOn] = useState<boolean>(true)
  const [fontStatus, setFontStatus] = useState<FontStatus>('loading')

  // 字体预加载：仅在客户端 useEffect 中执行，避免 hydration mismatch。
  // 只急加载 Regular/Bold 两档（页面主文案），其余字重由浏览器按需加载
  useEffect(() => {
    let cancelled = false

    async function loadFonts(): Promise<void> {
      try {
        if (typeof document === 'undefined' || !('fonts' in document)) {
          throw new Error('FontFaceSet API not supported')
        }
        await Promise.all([
          document.fonts.load('16px "JetHan Mono"'),
          document.fonts.load('700 16px "JetHan Mono"'),
        ])
        await document.fonts.ready
        if (!cancelled) {
          setFontStatus('loaded')
        }
      } catch {
        if (!cancelled) {
          setFontStatus('error')
        }
      }
    }

    void loadFonts()

    return () => {
      cancelled = true
    }
  }, [])

  // 对比模式：所有演示文本在 JetHan Mono 与系统等宽之间切换
  const monoFontClass: MonoFontClass = compareMode ? 'font-sysmono' : 'font-jethan'

  // 连字开关：calt 走 fontFeatureSettings，liga 走 fontVariantLigatures
  const ligatureStyle: CSSProperties = {
    fontFeatureSettings: caltOn ? '"calt" 1' : '"calt" 0',
    fontVariantLigatures: ligaOn ? 'normal' : 'none',
  }

  return (
    <div className="flex min-h-screen flex-col bg-background text-foreground">
      <main className="mx-auto w-full max-w-4xl flex-1 space-y-6 px-4 py-8">
        {/* ===================== Header ===================== */}
        <header className="flex flex-col gap-6 sm:flex-row sm:items-start sm:justify-between">
          <div className="space-y-3">
            <h1 className={cn('text-3xl font-bold tracking-tight sm:text-4xl', 'font-jethan')}>
              JetHan Mono
            </h1>
            <p className="text-sm text-muted-foreground sm:text-base">
              JetBrains Mono × 思源等宽 · 拼合字体预览
            </p>
            <ul className="flex flex-wrap gap-2" aria-label="字体特性">
              {HEADER_BADGES.map((badge) => (
                <li key={badge.text}>
                  <Badge variant="outline" className={badge.className}>
                    {badge.text}
                  </Badge>
                </li>
              ))}
            </ul>
          </div>

          <div className="flex items-center gap-4 rounded-xl border bg-card p-4 sm:shrink-0">
            <div className="space-y-1">
              <label htmlFor="compare-mode" className="block cursor-pointer text-sm font-medium">
                对比模式
              </label>
              <p className="text-xs text-muted-foreground">切换为系统等宽字体对照</p>
            </div>
            <Switch
              id="compare-mode"
              checked={compareMode}
              onCheckedChange={setCompareMode}
              aria-label="切换对比模式"
            />
          </div>
        </header>

        {/* ===================== 字体加载状态 ===================== */}
        <section aria-label="字体加载状态" aria-live="polite">
          {fontStatus === 'loading' ? (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <LoaderCircle className="size-4 animate-spin" aria-hidden="true" />
              <span>正在加载字体（Regular / Bold woff2），首次加载需要一些时间，其余字重按需加载…</span>
            </div>
          ) : fontStatus === 'loaded' ? (
            <div className="flex flex-wrap items-center gap-2">
              <Badge className="border-emerald-200 bg-emerald-100 text-emerald-800">
                字体加载完成
              </Badge>
              <Badge variant="outline" className="border-zinc-200 bg-zinc-50 text-zinc-600">
                Regular / Bold 已就绪 · 其余 6 档字重按需加载 · woff2
              </Badge>
            </div>
          ) : (
            <div className="flex flex-wrap items-center gap-2">
              <Badge className="border-amber-200 bg-amber-100 text-amber-800">
                字体加载失败
              </Badge>
              <span className="text-sm text-muted-foreground">
                页面已回退到系统等宽字体，请检查网络后刷新重试。
              </span>
            </div>
          )}
        </section>

        {/* ===================== 卡片 1 · 连字演示 ===================== */}
        <section aria-label="连字演示">
          <Card>
            <CardHeader>
              <CardTitle>连字演示</CardTitle>
              <CardDescription>
                编程连字（calt）与全部连字（liga）可分别开关，实时观察代码中的字形合并效果。
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex flex-wrap items-center gap-x-6 gap-y-3">
                <div className="flex items-center gap-2">
                  <Switch
                    id="calt-switch"
                    checked={caltOn}
                    onCheckedChange={setCaltOn}
                    aria-label="切换编程连字 (calt)"
                  />
                  <label htmlFor="calt-switch" className="cursor-pointer select-none text-sm">
                    编程连字 (calt)
                  </label>
                </div>
                <div className="flex items-center gap-2">
                  <Switch
                    id="liga-switch"
                    checked={ligaOn}
                    onCheckedChange={setLigaOn}
                    aria-label="切换全部连字 (liga)"
                  />
                  <label htmlFor="liga-switch" className="cursor-pointer select-none text-sm">
                    全部连字 (liga)
                  </label>
                </div>
              </div>

              <div className="code-scroll max-h-96 overflow-x-auto overflow-y-auto rounded-xl bg-zinc-900 p-4 text-zinc-100">
                <pre
                  className={cn('whitespace-pre text-xs leading-relaxed sm:text-sm', monoFontClass)}
                  style={ligatureStyle}
                >
                  <code>{LIGATURE_CODE}</code>
                </pre>
              </div>

              <p className="text-xs text-muted-foreground">
                JetBrains Mono 的连字字形 .liga 通过 calt 上下文特性触发；SPC
                占位字形保证连字仍占整数格宽。
              </p>
            </CardContent>
          </Card>
        </section>

        {/* ===================== 卡片 2 · 中文渲染 ===================== */}
        <section aria-label="中文渲染">
          <Card>
            <CardHeader>
              <CardTitle>中文渲染</CardTitle>
              <CardDescription>
                思源等宽提供的中文字形在不同字号下的渲染效果，覆盖全角标点与中英混排。
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {CJK_SAMPLES.map((sample, index) => (
                <div key={sample.size}>
                  {index > 0 && <Separator className="mb-4" />}
                  <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between sm:gap-4">
                    <p
                      className={cn('min-w-0 break-words', monoFontClass)}
                      style={{ fontSize: sample.size }}
                    >
                      {sample.text}
                    </p>
                    <Badge
                      variant="outline"
                      className="shrink-0 border-amber-200 bg-amber-50 text-amber-700"
                    >
                      {sample.size}px
                    </Badge>
                  </div>
                </div>
              ))}
            </CardContent>

            {/* 宽度网格: 2 英文 = 1 中文 (0.6em : 1.2em), 两行横条严格等长 */}
            <CardContent className="space-y-3 border-t bg-muted/30">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="text-sm font-medium">宽度网格 · 中英对应关系</p>
                <Badge variant="outline" className="border-zinc-200 bg-zinc-50 text-zinc-600">
                  英文 0.60em · 中文 1.20em → 精确 2 : 1
                </Badge>
              </div>
              <div className="overflow-x-auto pb-1">
                <div className="inline-flex flex-col gap-1 font-jethan" style={{ fontSize: 20, lineHeight: 1.5 }}>
                  <div className="flex border-r-2 border-primary pr-px">
                    {'abcdefghij0123456789'.split('').map((ch, i) => (
                      <span
                        key={`lat-${i}`}
                        className={cn(
                          'flex justify-center',
                          i % 2 ? 'bg-emerald-100 text-emerald-900' : 'bg-emerald-50 text-emerald-800',
                        )}
                        style={{ width: '0.6em' }}
                      >
                        {ch}
                      </span>
                    ))}
                  </div>
                  <div className="flex border-r-2 border-primary pr-px">
                    {'壹贰叁肆伍陆柒捌玖拾'.split('').map((ch, i) => (
                      <span
                        key={`cjk-${i}`}
                        className={cn(
                          'flex justify-center',
                          i % 2 ? 'bg-amber-100 text-amber-900' : 'bg-amber-50 text-amber-800',
                        )}
                        style={{ width: '1.2em' }}
                      >
                        {ch}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
              <p className="text-xs leading-relaxed text-muted-foreground">
                两行横条严格等长（20 英文格 = 10 中文格 = 12em）：中文步进由上游的 1.0em 拉宽到
                1.2em（= 2 × 0.6em），恰好 1 汉字占 2 英文格，终端与编辑器中英混排严格对齐同一网格。
                字形本身不缩放，居中留白（汉字两侧各 ~100u），中文观感略松；半角片假名等窄字符吸附到
                0.6em，与英文同宽。
              </p>
            </CardContent>
          </Card>
        </section>

        {/* ===================== 卡片 3 · 八档字重 ===================== */}
        <section aria-label="八档字重">
          <Card>
            <CardHeader>
              <CardTitle>八档字重</CardTitle>
              <CardDescription>
                Thin 100 → ExtraBold 800 全系罗马字重（上游无 Heavy）；CJK
                侧无对应字重时按 usWeightClass 就近映射，同源设计保证灰度衔接。
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {WEIGHT_LIST.map((sample, index) => (
                <div key={sample.name}>
                  {index > 0 && <Separator className="mb-4" />}
                  <div className="flex flex-col gap-2 sm:flex-row sm:items-baseline sm:justify-between sm:gap-4">
                    <p
                      className={cn('text-xl sm:text-2xl', monoFontClass)}
                      style={{ fontWeight: sample.css }}
                    >
                      快速棕狐跳过懒狗 0123456789 {(sample.css / 100).toFixed(1)}
                    </p>
                    <div className="flex shrink-0 flex-wrap items-center gap-1.5">
                      <Badge variant="secondary">
                        {sample.name} {sample.css}
                      </Badge>
                      <Badge
                        variant="outline"
                        className="border-zinc-200 bg-zinc-50 text-xs text-zinc-600"
                      >
                        {sample.cjk}
                      </Badge>
                    </div>
                  </div>
                </div>
              ))}

              <Separator />

              <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between sm:gap-4">
                <p className={cn('text-lg sm:text-xl', monoFontClass)}>
                  0O 1lI 5S 2Z 8B cn 排版鉴别
                </p>
                <Badge
                  variant="outline"
                  className="shrink-0 border-zinc-200 bg-zinc-50 text-zinc-600"
                >
                  易混字符
                </Badge>
              </div>
            </CardContent>
          </Card>
        </section>

        {/* ===================== 卡片 4 · 下载与构建信息 ===================== */}
        <section aria-label="下载与构建信息">
          <Card>
            <CardHeader>
              <CardTitle>下载与构建信息</CardTitle>
              <CardDescription>每档字重提供 ttf（桌面安装）与 woff2（Web）两种格式。</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              {/* 按字重分行：ttf / woff2 双格式下载 */}
              <div className="space-y-2" aria-label="字体文件下载">
                {WEIGHT_LIST.map((w) => (
                  <div
                    key={w.name}
                    className="flex flex-wrap items-center gap-x-3 gap-y-2 rounded-lg border p-3"
                  >
                    <span className="font-jethan text-sm font-semibold">
                      JetHanMono-{w.name}
                    </span>
                    <Badge variant="outline" className="border-zinc-200 bg-zinc-50 text-zinc-600">
                      {w.css}
                    </Badge>
                    <span className="hidden text-xs text-muted-foreground lg:inline">{w.cjk}</span>
                    <div className="ml-auto flex flex-wrap gap-2">
                      <Button asChild variant="outline" size="sm">
                        <a
                          href={`/fonts/JetHanMono-${w.name}.ttf`}
                          download={`JetHanMono-${w.name}.ttf`}
                          aria-label={`下载 JetHanMono-${w.name}.ttf（${w.ttfSize}）`}
                        >
                          <Download className="size-3.5" aria-hidden="true" />
                          <span className="font-jethan">ttf</span>
                          <span className="text-xs text-muted-foreground">{w.ttfSize}</span>
                        </a>
                      </Button>
                      <Button asChild variant="outline" size="sm">
                        <a
                          href={`/fonts/JetHanMono-${w.name}.woff2`}
                          download={`JetHanMono-${w.name}.woff2`}
                          aria-label={`下载 JetHanMono-${w.name}.woff2（${w.woff2Size}）`}
                        >
                          <Download className="size-3.5" aria-hidden="true" />
                          <span className="font-jethan">woff2</span>
                          <span className="text-xs text-muted-foreground">{w.woff2Size}</span>
                        </a>
                      </Button>
                    </div>
                  </div>
                ))}

                {/* 源码包（构建管线 + 工具 + CI，不含字体二进制） */}
                <div className="flex flex-wrap items-center gap-3 rounded-lg border border-dashed p-3">
                  <span className="font-jethan text-sm font-semibold">JetHanMono-src.zip</span>
                  <span className="hidden text-xs text-muted-foreground lg:inline">
                    源码包 — 构建管线 + 工具脚本 + CI（不含字体）
                  </span>
                  <Button asChild variant="outline" size="sm" className="ml-auto">
                    <a
                      href="/JetHanMono-src.zip"
                      download="JetHanMono-src.zip"
                      aria-label="下载 JetHanMono-src.zip 源码包"
                    >
                      <Download className="size-3.5" aria-hidden="true" />
                      <span className="font-jethan">zip</span>
                    </a>
                  </Button>
                </div>

                {/* 许可证 */}
                <div className="flex flex-wrap items-center gap-3 rounded-lg border border-dashed p-3">
                  <span className="font-jethan text-sm font-semibold">JetHanMono-OFL.txt</span>
                  <span className="hidden text-xs text-muted-foreground lg:inline">
                    双上游版权声明 + OFL 1.1 全文
                  </span>
                  <Button asChild variant="outline" size="sm" className="ml-auto">
                    <a
                      href="/fonts/JetHanMono-OFL.txt"
                      download="JetHanMono-OFL.txt"
                      aria-label="下载 JetHanMono-OFL.txt"
                    >
                      <Download className="size-3.5" aria-hidden="true" />
                      <span className="font-jethan">txt</span>
                    </a>
                  </Button>
                </div>
              </div>

              <Separator />

              <ul className="space-y-3" aria-label="构建配方">
                {BUILD_INFO.map((item) => (
                  <li key={item.label} className="flex items-start gap-3 text-sm">
                    <Check className="mt-0.5 size-4 shrink-0 text-emerald-600" aria-hidden="true" />
                    <span>
                      <span className={cn('font-medium', 'font-jethan')}>{item.label}</span>
                      <span className="text-muted-foreground"> — {item.detail}</span>
                    </span>
                  </li>
                ))}
              </ul>
            </CardContent>
          </Card>
        </section>
      </main>

      {/* ===================== Footer（sticky footer） ===================== */}
      <footer className="mt-auto border-t">
        <div className="mx-auto w-full max-w-4xl px-4 py-6 text-center text-sm text-muted-foreground">
          JetHan Mono · 基于 JetBrains Mono 与思源等宽拼合 · 8 档字重 · SIL OFL 1.1 许可
        </div>
      </footer>
    </div>
  )
}
