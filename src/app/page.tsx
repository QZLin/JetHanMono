'use client'

import { useCallback, useEffect, useRef, useState, type CSSProperties } from 'react'
import { Check, Download, ExternalLink, LoaderCircle, RefreshCw } from 'lucide-react'

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
type ReleaseStatus = 'loading' | 'ready' | 'error'
type Variant = 'centered' | 'scaled'

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
}

interface AssetInfo {
  readonly name: string
  readonly url: string
  readonly size: number
}

type FontEntry = Partial<Record<'ttf' | 'woff2', AssetInfo>>

interface ReleasePayload {
  readonly ready: boolean
  readonly nWoff2: number
  readonly tag: string
  readonly version: string
  readonly htmlUrl: string
  readonly publishedAt: string | null
  readonly zipCount: number
  readonly looseCount: number
  readonly fonts: Record<Variant, Partial<Record<string, FontEntry>>>
  readonly zips: Record<'centered' | 'scaled' | 'centeredWoff' | 'scaledWoff', AssetInfo | null>
  readonly ofl: AssetInfo | null
  readonly error: string | null
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
  { name: 'Thin', css: 100, cjk: 'CJK ← Sans Thin' },
  { name: 'ExtraLight', css: 200, cjk: 'CJK ← Sans Light' },
  { name: 'Light', css: 300, cjk: 'CJK ← Sans Light' },
  { name: 'Regular', css: 400, cjk: 'CJK ← 等宽 Regular' },
  { name: 'Medium', css: 500, cjk: 'CJK ← Sans Medium' },
  { name: 'SemiBold', css: 600, cjk: 'CJK ← 等宽 Bold' },
  { name: 'Bold', css: 700, cjk: 'CJK ← 等宽 Bold' },
  { name: 'ExtraBold', css: 800, cjk: 'CJK ← Sans Black' },
]

const CSS_OF_WEIGHT: Readonly<Record<string, number>> = Object.fromEntries(
  WEIGHT_LIST.map((w) => [w.name, w.css]),
)

/** 急加载字重（页面主文案），其余字重后台按需加载 */
const EAGER_WEIGHTS: readonly string[] = ['Regular', 'Bold']

const VARIANT_INFO: Record<
  Variant,
  { cap: string; label: string; tagline: string; desc: string }
> = {
  centered: {
    cap: 'Centered',
    label: '居中版',
    tagline: '默认 / 推荐',
    desc: 'CJK 轮廓不缩放，保持思源等宽原始 1000u 设计与字面观感（"中"墨高 ~919u），设计盒水平居中于 1200u 全角格；全部墨迹在 JBM 纵向度量（1020/-300）之内。',
  },
  scaled: {
    cap: 'Scaled',
    label: '缩放版',
    tagline: '满格派',
    desc: 'CJK 轮廓双轴 ×1.2 放大填满 1200u 全角格（"中"墨高 ~1103u，比上游高 20%），更接近传统中文字体的字面率；汉字顶部会略超出拉丁上伸部，属该方案已知取舍。',
  },
}

const RELEASE_REPO_URL = 'https://github.com/QZLin/JetHanMono'

/** 卡片 4 构建配方信息 */
const BUILD_INFO: readonly BuildInfoItem[] = [
  {
    label: '发行结构：4 压缩包 + 32 散装字体',
    detail:
      'Centered / Scaled 各出 TTF 与 WOFF2 压缩包，包内字体文件不带变体后缀；散装字体文件名带 -Centered/-Scaled 后缀，内容与包内一致',
  },
  {
    label: '预览字体来自 GitHub Latest Release',
    detail:
      '页面启动时经 /api/release 读取最新发布的散装 woff2 资产（经同源代理注入 FontFace，规避 GitHub 资产下载无 CORS 头的限制），切换方案即时换源',
  },
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
    detail: '拉丁 600u，中文/全角/谚文拉宽至 1200u = 2×600；字形不缩放居中（Centered）或 ×1.2 填满（Scaled），终端 1 汉字恰占 2 英文格',
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
    label: 'CI: GitHub Actions build-font',
    detail: 'font-build 变更自动构建 8 档字重双方案并上传产物，手动 dispatch 可发 Release（测试为发布质量门槛，默认勾选）',
  },
]

const HEADER_BADGES: readonly { readonly text: string; readonly className: string }[] = [
  { text: 'calt 连字 ✓', className: 'border-emerald-200 bg-emerald-50 text-emerald-700' },
  { text: '双方案 Centered / Scaled', className: 'border-amber-200 bg-amber-50 text-amber-700' },
  { text: '8 档字重', className: 'border-amber-200 bg-amber-50 text-amber-700' },
  { text: 'CJK ~44,000 码位', className: 'border-amber-200 bg-amber-50 text-amber-700' },
  { text: '终端 2:1 等宽 ✓', className: 'border-emerald-200 bg-emerald-50 text-emerald-700' },
  { text: 'OFL-1.1', className: 'border-zinc-200 bg-zinc-50 text-zinc-600' },
]

function fmtMB(bytes: number): string {
  return `${(bytes / 1048576).toFixed(1)}MB`
}

export default function Home() {
  const [compareMode, setCompareMode] = useState<boolean>(false)
  const [caltOn, setCaltOn] = useState<boolean>(true)
  const [ligaOn, setLigaOn] = useState<boolean>(true)
  const [variant, setVariant] = useState<Variant>('centered')
  const [fontStatus, setFontStatus] = useState<FontStatus>('loading')

  const [release, setRelease] = useState<ReleasePayload | null>(null)
  const [releaseStatus, setReleaseStatus] = useState<ReleaseStatus>('loading')
  const [releaseError, setReleaseError] = useState<string | null>(null)
  const [weightReady, setWeightReady] = useState<Record<string, boolean>>({})

  // 已注入 document.fonts 的 FontFace 句柄（切方案时整体卸载）
  const loadedFacesRef = useRef<FontFace[]>([])
  const loadEpochRef = useRef(0)

  // ---- 拉取 Latest Release 元数据 ----
  // 注意：所有 setState 都在 await 之后（异步路径），不落在 effect 同步执行路径
  const fetchRelease = useCallback(async () => {
    try {
      const res = await fetch('/api/release', { cache: 'no-store' })
      const data = (await res.json()) as ReleasePayload
      if (!res.ok || !data.ready) {
        // 完整载荷（旧格式 Release）保留给下载卡片用；纯错误响应置空
        setRelease(data.tag !== undefined ? data : null)
        setReleaseStatus('error')
        setReleaseError(data.error ?? `获取 Release 失败 (HTTP ${res.status})`)
        return
      }
      setRelease(data)
      setReleaseStatus('ready')
    } catch {
      setRelease(null)
      setReleaseStatus('error')
      setReleaseError('网络错误，无法获取 Release 信息')
    }
  }, [])

  // 重试按钮（事件处理器内同步 setState 无碍）
  const retryAll = useCallback(() => {
    setReleaseStatus('loading')
    setReleaseError(null)
    setFontStatus('loading')
    void fetchRelease()
  }, [fetchRelease])

  useEffect(() => {
    let cancelled = false
    void (async () => {
      // 异步边界后再取数，避免 effect 同步路径触发 setState
      await Promise.resolve()
      if (cancelled) return
      await fetchRelease()
    })()
    return () => {
      cancelled = true
    }
  }, [fetchRelease])

  // ---- 按方案加载 woff2（Regular/Bold 急加载 -> 其余字重后台队列） ----
  useEffect(() => {
    if (!release || !release.ready || typeof window === 'undefined') return
    const epoch = ++loadEpochRef.current

    // 同步部分只触碰外部系统（document.fonts：卸载上一方案注入的 FontFace）
    for (const face of loadedFacesRef.current) {
      try {
        document.fonts.delete(face)
      } catch {
        /* ignore */
      }
    }
    loadedFacesRef.current = []

    let cancelled = false
    void (async () => {
      // 异步边界之后才 setState：避免 effect 同步路径引发级联渲染
      await Promise.resolve()
      if (cancelled || loadEpochRef.current !== epoch) return
      setWeightReady({})
      setFontStatus('loading')

      const loadOne = async (name: string): Promise<boolean> => {
        const asset = release?.fonts[variant][name]?.woff2
        if (!asset) return false
        try {
          const face = new FontFace(
            'JetHan Mono',
            `url("/api/font-asset?name=${encodeURIComponent(asset.name)}")`,
            { weight: String(CSS_OF_WEIGHT[name] ?? 400), display: 'swap' },
          )
          document.fonts.add(face)
          await face.load()
          if (loadEpochRef.current !== epoch) {
            // 加载期间方案已被再次切换：丢弃本次结果
            try {
              document.fonts.delete(face)
            } catch {
              /* ignore */
            }
            return false
          }
          loadedFacesRef.current.push(face)
          setWeightReady((prev) => ({ ...prev, [name]: true }))
          return true
        } catch {
          return false
        }
      }

      // 第一阶段：急加载字重决定整体状态
      let eagerFailed = false
      for (const name of EAGER_WEIGHTS) {
        if (cancelled || loadEpochRef.current !== epoch) return
        const ok = await loadOne(name)
        if (!ok) eagerFailed = true
      }
      if (cancelled || loadEpochRef.current !== epoch) return
      setFontStatus(eagerFailed ? 'error' : 'loaded')

      // 第二阶段：其余字重顺序后台加载（浏览器并行缓存，页面按需渲染）
      for (const w of WEIGHT_LIST) {
        if (EAGER_WEIGHTS.includes(w.name)) continue
        if (cancelled || loadEpochRef.current !== epoch) return
        await loadOne(w.name)
      }
    })()

    return () => {
      cancelled = true
    }
  }, [release, variant])

  const monoFontClass: MonoFontClass = compareMode ? 'font-sysmono' : 'font-jethan'

  const ligatureStyle: CSSProperties = {
    fontFeatureSettings: caltOn ? '"calt" 1' : '"calt" 0',
    fontVariantLigatures: ligaOn ? 'normal' : 'none',
  }

  const eagerNames = EAGER_WEIGHTS.map((n) => `JetHanMono-${n}-${VARIANT_INFO[variant].cap}.woff2`).join(' / ')
  const info = VARIANT_INFO[variant]

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

        {/* ===================== CJK 方案切换 ===================== */}
        <section aria-label="CJK 几何方案切换">
          <Card>
            <CardContent className="space-y-4">
              <div
                className="grid gap-3 sm:grid-cols-2"
                role="radiogroup"
                aria-label="选择 CJK 几何方案"
              >
                {(Object.keys(VARIANT_INFO) as Variant[]).map((v) => {
                  const vi = VARIANT_INFO[v]
                  const selected = variant === v
                  return (
                    <button
                      key={v}
                      type="button"
                      role="radio"
                      aria-checked={selected}
                      onClick={() => setVariant(v)}
                      className={cn(
                        'flex flex-col gap-1 rounded-xl border p-4 text-left transition-colors',
                        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
                        selected
                          ? 'border-primary bg-primary/5 shadow-sm'
                          : 'bg-card hover:bg-muted/50',
                      )}
                    >
                      <span className="flex items-center gap-2">
                        <span className={cn('font-jethan text-base font-semibold')}>
                          {vi.label} {vi.cap}
                        </span>
                        <Badge
                          variant="outline"
                          className={
                            v === 'centered'
                              ? 'border-emerald-200 bg-emerald-50 text-emerald-700'
                              : 'border-amber-200 bg-amber-50 text-amber-700'
                          }
                        >
                          {vi.tagline}
                        </Badge>
                        {selected && (
                          <Check className="ml-auto size-4 text-primary" aria-hidden="true" />
                        )}
                      </span>
                      <span className="text-xs leading-relaxed text-muted-foreground">
                        {vi.desc}
                      </span>
                    </button>
                  )
                })}
              </div>
              <p className="text-xs text-muted-foreground">
                两方案字体内名完全相同（JetHan Mono），仅 CJK 几何不同；预览渲染与下载链接跟随所选方案，
                woff2 实时取自 GitHub Latest Release 散装资产。
              </p>
            </CardContent>
          </Card>
        </section>

        {/* ===================== 字体加载状态 ===================== */}
        <section aria-label="字体加载状态" aria-live="polite">
          {releaseStatus === 'loading' ? (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <LoaderCircle className="size-4 animate-spin" aria-hidden="true" />
              <span>正在获取 GitHub Latest Release 信息…</span>
            </div>
          ) : releaseStatus === 'error' ? (
            <div className="flex flex-wrap items-center gap-2">
              <Badge className="border-amber-200 bg-amber-100 text-amber-800">
                Release 加载失败
              </Badge>
              <span className="text-sm text-muted-foreground">{releaseError}</span>
              <Button variant="outline" size="sm" onClick={retryAll}>
                <RefreshCw className="size-3.5" aria-hidden="true" />
                重试
              </Button>
            </div>
          ) : fontStatus === 'loading' ? (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <LoaderCircle className="size-4 animate-spin" aria-hidden="true" />
              <span>
                正在从 Release {release?.tag} 加载字体（{info.label} {info.cap} · Regular / Bold
                优先，其余字重后台按需加载）…
              </span>
            </div>
          ) : fontStatus === 'loaded' ? (
            <div className="flex flex-wrap items-center gap-2">
              <Badge className="border-emerald-200 bg-emerald-100 text-emerald-800">
                字体加载完成
              </Badge>
              <Badge variant="outline" className="border-zinc-200 bg-zinc-50 text-zinc-600">
                Release {release?.tag} · {info.label} {info.cap} · Regular / Bold 已就绪 · 其余 6
                档字重后台加载 · woff2
              </Badge>
            </div>
          ) : (
            <div className="flex flex-wrap items-center gap-2">
              <Badge className="border-amber-200 bg-amber-100 text-amber-800">字体加载失败</Badge>
              <span className="text-sm text-muted-foreground">
                页面已回退到系统等宽字体（{eagerNames}），请检查网络后重试。
              </span>
              <Button variant="outline" size="sm" onClick={retryAll}>
                <RefreshCw className="size-3.5" aria-hidden="true" />
                重试
              </Button>
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
                {variant === 'centered'
                  ? '当前方案（居中版）字形本身不缩放，居中留白（汉字两侧各 ~100u），中文观感略松。'
                  : '当前方案（缩放版）字形双轴 ×1.2 放大填满 1.2em 格，字面更满，步进与居中版完全一致。'}
                半角片假名等窄字符吸附到 0.6em，与英文同宽。
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
                      {!weightReady[sample.name] && release?.ready && (
                        <LoaderCircle
                          className="size-3.5 animate-spin text-muted-foreground"
                          aria-label={`${sample.name} 字重加载中`}
                        />
                      )}
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
              <CardDescription>
                资产实时来自 GitHub Latest Release{release ? `（${release.tag}）` : ''}：
                4 个压缩包 + 全部散装字体；压缩包内文件不带变体后缀，散装文件带 -Centered/-Scaled 后缀。
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              {/* 压缩包：4 个 */}
              <div className="space-y-2" aria-label="压缩包下载">
                <p className="text-sm font-medium text-muted-foreground">压缩包（包内无变体后缀）</p>
                {(
                  [
                    { key: 'centered', name: `JetHanMono-${release?.version ?? '<版本>'}-Centered.zip`, desc: '居中版 TTF · 桌面安装（8 字重）' },
                    { key: 'scaled', name: `JetHanMono-${release?.version ?? '<版本>'}-Scaled.zip`, desc: '缩放版 TTF · 桌面安装（8 字重）' },
                    { key: 'centeredWoff', name: `JetHanMono-${release?.version ?? '<版本>'}-Centered_woff.zip`, desc: '居中版 WOFF2 · Web（8 字重）' },
                    { key: 'scaledWoff', name: `JetHanMono-${release?.version ?? '<版本>'}-Scaled_woff.zip`, desc: '缩放版 WOFF2 · Web（8 字重）' },
                  ] as const
                ).map(({ key, name, desc }) => {
                  const asset = release?.zips[key] ?? null
                  return (
                    <div
                      key={key}
                      className="flex flex-wrap items-center gap-x-3 gap-y-2 rounded-lg border p-3"
                    >
                      <span className="font-jethan text-sm font-semibold">{asset?.name ?? name}</span>
                      <span className="hidden text-xs text-muted-foreground lg:inline">{desc}</span>
                      <div className="ml-auto flex gap-2">
                        {asset ? (
                          <Button asChild variant="outline" size="sm">
                            <a
                              href={asset.url}
                              download={asset.name}
                              aria-label={`下载 ${asset.name}（${fmtMB(asset.size)}）`}
                            >
                              <Download className="size-3.5" aria-hidden="true" />
                              <span className="font-jethan">zip</span>
                              <span className="text-xs text-muted-foreground">{fmtMB(asset.size)}</span>
                            </a>
                          </Button>
                        ) : (
                          <Button variant="outline" size="sm" disabled>
                            <LoaderCircle className="size-3.5 animate-spin" aria-hidden="true" />
                            <span className="font-jethan">zip</span>
                          </Button>
                        )}
                      </div>
                    </div>
                  )
                })}
              </div>

              {/* 散装字体：按当前方案分行，文件名带变体后缀 */}
              <div className="space-y-2" aria-label="散装字体下载">
                <div className="flex flex-wrap items-center gap-2">
                  <p className="text-sm font-medium text-muted-foreground">
                    散装字体（文件名带 -{info.cap} 后缀 · 内容与压缩包内一致）
                  </p>
                  {!release?.ready && (
                    <Badge variant="outline" className="border-zinc-200 bg-zinc-50 text-zinc-600">
                      {releaseStatus === 'loading' ? '加载中…' : '需要 1.004+ Release'}
                    </Badge>
                  )}
                </div>
                {WEIGHT_LIST.map((w) => {
                  const entry = release?.fonts[variant][w.name]
                  const cap = info.cap
                  return (
                    <div
                      key={w.name}
                      className="flex flex-wrap items-center gap-x-3 gap-y-2 rounded-lg border p-3"
                    >
                      <span className="font-jethan text-sm font-semibold">
                        JetHanMono-{w.name}-{cap}
                      </span>
                      <Badge variant="outline" className="border-zinc-200 bg-zinc-50 text-zinc-600">
                        {w.css}
                      </Badge>
                      <span className="hidden text-xs text-muted-foreground lg:inline">{w.cjk}</span>
                      <div className="ml-auto flex flex-wrap gap-2">
                        {(['ttf', 'woff2'] as const).map((fmt) => {
                          const asset = entry?.[fmt]
                          return asset ? (
                            <Button asChild key={fmt} variant="outline" size="sm">
                              <a
                                href={asset.url}
                                download={asset.name}
                                aria-label={`下载 ${asset.name}（${fmtMB(asset.size)}）`}
                              >
                                <Download className="size-3.5" aria-hidden="true" />
                                <span className="font-jethan">{fmt}</span>
                                <span className="text-xs text-muted-foreground">
                                  {fmtMB(asset.size)}
                                </span>
                              </a>
                            </Button>
                          ) : (
                            <Button variant="outline" size="sm" disabled key={fmt}>
                              <LoaderCircle className="size-3.5 animate-spin" aria-hidden="true" />
                              <span className="font-jethan">{fmt}</span>
                            </Button>
                          )
                        })}
                      </div>
                    </div>
                  )
                })}

                {/* 源代码 */}
                <div className="flex flex-wrap items-center gap-3 rounded-lg border border-dashed p-3">
                  <span className="font-jethan text-sm font-semibold">源代码 · QZLin/JetHanMono</span>
                  <span className="hidden text-xs text-muted-foreground lg:inline">
                    构建管线 + 工具脚本 + CI（不含字体二进制）
                  </span>
                  <Button asChild variant="outline" size="sm" className="ml-auto">
                    <a
                      href={RELEASE_REPO_URL}
                      target="_blank"
                      rel="noreferrer"
                      aria-label="打开 GitHub 仓库"
                    >
                      <ExternalLink className="size-3.5" aria-hidden="true" />
                      <span className="font-jethan">GitHub</span>
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
                      href={release?.ofl?.url ?? `${RELEASE_REPO_URL}/releases/latest`}
                      download={release?.ofl?.name ?? 'JetHanMono-OFL.txt'}
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
          JetHan Mono · 基于 JetBrains Mono 与思源等宽拼合 · 8 档字重 · 双方案 · SIL OFL 1.1 许可
        </div>
      </footer>
    </div>
  )
}
