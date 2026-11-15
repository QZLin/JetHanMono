import { NextResponse } from 'next/server'

/**
 * GitHub Latest Release 资产字节代理（同源流式转发）。
 *
 * 为什么需要代理：GitHub 的 Release 资产下载
 * （github.com/.../releases/download/... -> release-assets.githubusercontent.com）
 * 响应不带 Access-Control-Allow-Origin，浏览器 FontFace 无法跨源加载；
 * 由本路由在服务端转发，前端用同源 URL 注入字体。
 *
 * 安全：只转发"名字能匹配散装字体资产白名单且确实存在于 Latest Release
 * 资产列表"的文件，不做任意 URL 转发。
 */

export const runtime = 'nodejs'

const REPO = 'QZLin/JetHanMono'

// 与 /api/release 的 FONT_RE 一致 + OFL（供下载按钮走同一代理入口的兜底）
const ASSET_RE =
  /^(JetHanMono-(Thin|ExtraLight|Light|Regular|Medium|SemiBold|Bold|ExtraBold)-(Centered|Scaled)\.(ttf|woff2)|JetHanMono-OFL\.txt)$/

interface GhAsset {
  name: string
  browser_download_url: string
  size: number
}

const CONTENT_TYPES: Record<string, string> = {
  '.woff2': 'font/woff2',
  '.ttf': 'font/ttf',
  '.txt': 'text/plain; charset=utf-8',
}

export async function GET(req: Request) {
  const name = new URL(req.url).searchParams.get('name') ?? ''
  if (!ASSET_RE.test(name)) {
    return NextResponse.json({ error: '非法资产名' }, { status: 400 })
  }

  // 解析 Latest Release（与 /api/release 相同的 revalidate 策略，共享缓存）
  let assets: GhAsset[]
  try {
    const res = await fetch(`https://api.github.com/repos/${REPO}/releases/latest`, {
      headers: {
        Accept: 'application/vnd.github+json',
        'User-Agent': 'JetHanMono-preview-site',
      },
      next: { revalidate: 300 },
    })
    if (!res.ok) {
      return NextResponse.json({ error: `GitHub API ${res.status}` }, { status: 502 })
    }
    assets = ((await res.json()) as { assets?: GhAsset[] }).assets ?? []
  } catch {
    return NextResponse.json({ error: '无法连接 GitHub API' }, { status: 502 })
  }

  const asset = assets.find((a) => a.name === name)
  if (!asset) {
    return NextResponse.json(
      { error: `Latest Release 中没有资产 ${name}（需要 1.004+ 格式发布）` },
      { status: 404 },
    )
  }

  // 拉取资产字节（带重试：GitHub 资产 CDN 偶发连接失败/限流，
  // 连接失败与 5xx/429 重试，其余 4xx 不重试）
  let upstream: Response | null = null
  let lastDetail = ''
  for (let attempt = 1; attempt <= 3 && !upstream; attempt++) {
    try {
      const r = await fetch(asset.browser_download_url, {
        headers: { 'User-Agent': 'JetHanMono-preview-site' },
        cache: 'no-store',
      })
      if (r.ok && r.body) {
        upstream = r
        break
      }
      lastDetail = `HTTP ${r.status}`
      try {
        await r.body?.cancel()
      } catch {
        /* ignore */
      }
      if (r.status === 429 || r.status >= 500) {
        await new Promise((res) => setTimeout(res, 1200 * attempt))
        continue
      }
      break // 4xx: 重试无意义
    } catch (e) {
      // 连接失败：退避后重试
      lastDetail = e instanceof Error ? e.message : String(e)
      await new Promise((res) => setTimeout(res, 1200 * attempt))
    }
  }
  if (!upstream || !upstream.ok || !upstream.body) {
    return NextResponse.json(
      { error: `上游资产下载失败 (${lastDetail || '未知错误'})` },
      { status: 502 },
    )
  }

  const ext = name.slice(name.lastIndexOf('.'))
  return new NextResponse(upstream.body, {
    status: 200,
    headers: {
      'Content-Type': CONTENT_TYPES[ext] ?? 'application/octet-stream',
      'Cache-Control': 'public, max-age=3600, stale-while-revalidate=86400',
      'Content-Disposition': `inline; filename="${name}"`,
    },
  })
}
