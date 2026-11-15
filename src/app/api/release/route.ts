import { NextResponse } from 'next/server'

/**
 * GitHub Latest Release 元数据 -> 预览站友好的结构化载荷。
 *
 * 预览站的所有字体（woff2）与下载链接都来自 GitHub Latest Release 的
 * 散装资产（1.004 起：JetHanMono-<字重>-<Centered|Scaled>.ttf/.woff2）。
 * 服务端代取可以：
 *   1. 复用 GitHub API 的服务端缓存（revalidate 300s），避免客户端
 *      各自打 API 触发 60 次/小时 的未认证限流；
 *   2. 把资产名解析成 方案 x 字重 x 格式 的矩阵，客户端零解析。
 */

export const runtime = 'nodejs'
export const revalidate = 300

const REPO = 'QZLin/JetHanMono'

const WEIGHTS = [
  'Thin',
  'ExtraLight',
  'Light',
  'Regular',
  'Medium',
  'SemiBold',
  'Bold',
  'ExtraBold',
] as const

type Weight = (typeof WEIGHTS)[number]
type Variant = 'centered' | 'scaled'
type Format = 'ttf' | 'woff2'

interface AssetInfo {
  name: string
  url: string
  size: number
}

type FontMatrix = Record<Variant, Partial<Record<Weight, Partial<Record<Format, AssetInfo>>>>>

interface GhAsset {
  name: string
  browser_download_url: string
  size: number
}

interface GhRelease {
  tag_name?: string
  html_url?: string
  published_at?: string
  assets?: GhAsset[]
  message?: string
}

const FONT_RE =
  /^JetHanMono-(Thin|ExtraLight|Light|Regular|Medium|SemiBold|Bold|ExtraBold)-(Centered|Scaled)\.(ttf|woff2)$/
const ZIP_RE = /^JetHanMono-[\d.]+-(Centered|Scaled)(_woff)?\.zip$/

function countWoff2(fonts: FontMatrix): number {
  let n = 0
  for (const v of ['centered', 'scaled'] as const) {
    for (const w of WEIGHTS) {
      if (fonts[v][w]?.woff2) n += 1
    }
  }
  return n
}

export async function GET() {
  let rel: GhRelease
  try {
    const res = await fetch(`https://api.github.com/repos/${REPO}/releases/latest`, {
      headers: {
        Accept: 'application/vnd.github+json',
        'User-Agent': 'JetHanMono-preview-site',
      },
      next: { revalidate: 300 },
    })
    if (!res.ok) {
      return NextResponse.json(
        { ready: false, error: `GitHub API ${res.status}${res.status === 403 ? ' (rate limit, 请稍后重试)' : ''}` },
        { status: 502 },
      )
    }
    rel = (await res.json()) as GhRelease
  } catch {
    return NextResponse.json({ ready: false, error: '无法连接 GitHub API' }, { status: 502 })
  }

  const tag = rel.tag_name ?? ''
  const assets = rel.assets ?? []
  const fonts: FontMatrix = { centered: {}, scaled: {} }
  const zips: Record<'centered' | 'scaled' | 'centeredWoff' | 'scaledWoff', AssetInfo | null> = {
    centered: null,
    scaled: null,
    centeredWoff: null,
    scaledWoff: null,
  }
  let ofl: AssetInfo | null = null

  for (const a of assets) {
    const m = FONT_RE.exec(a.name)
    if (m) {
      const variant = m[2].toLowerCase() as Variant
      const weight = m[1] as Weight
      const format = m[3] as Format
      const bucket = fonts[variant][weight] ?? {}
      bucket[format] = { name: a.name, url: a.browser_download_url, size: a.size }
      fonts[variant][weight] = bucket
      continue
    }
    const z = ZIP_RE.exec(a.name)
    if (z) {
      const key = (z[2] ? `${z[1].toLowerCase()}Woff` : z[1].toLowerCase()) as
        | 'centered'
        | 'scaled'
        | 'centeredWoff'
        | 'scaledWoff'
      zips[key] = { name: a.name, url: a.browser_download_url, size: a.size }
      continue
    }
    if (a.name === 'JetHanMono-OFL.txt') {
      ofl = { name: a.name, url: a.browser_download_url, size: a.size }
    }
  }

  // 就绪判定：散装 woff2 覆盖 2 方案 x 8 字重（预览渲染的必要条件）。
  // 旧格式 Release（1.003 及更早：woff2 只在压缩包内）会被判为未就绪。
  const nWoff2 = countWoff2(fonts)
  const ready = nWoff2 === 16

  return NextResponse.json({
    ready,
    nWoff2,
    tag,
    version: tag.startsWith('jethan-v') ? tag.slice('jethan-v'.length) : tag,
    htmlUrl: rel.html_url ?? `https://github.com/${REPO}/releases/latest`,
    publishedAt: rel.published_at ?? null,
    zipCount: assets.filter((a) => ZIP_RE.test(a.name)).length,
    looseCount: assets.filter((a) => FONT_RE.test(a.name)).length,
    fonts,
    zips,
    ofl,
    error: ready ? null : `最新 Release (${tag || '未知'}) 缺少散装 woff2 资产（${nWoff2}/16），需要 1.004+ 格式的发布`,
  })
}
