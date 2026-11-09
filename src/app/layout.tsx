import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { Toaster } from "@/components/ui/toaster";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "JetHan Mono — JetBrains Mono × 思源等宽拼合字体",
  description:
    "JetBrains Mono（拉丁/代码/编程连字优先）与思源等宽（中文）拼合的等宽字体：拉丁 600u、中文 1200u，终端 1 汉字恰占 2 英文格。提供 Thin → ExtraBold 共 8 档字重。",
  keywords: ["JetHan Mono", "JetBrains Mono", "思源等宽", "Source Han Mono", "Noto Sans Mono CJK SC", "等宽字体", "编程字体", "中英混排"],
  authors: [{ name: "QZLin" }],
  icons: {
    icon: "/logo.svg",
  },
  openGraph: {
    title: "JetHan Mono — JetBrains Mono × 思源等宽拼合字体",
    description:
      "拉丁 600u、中文 1200u，终端 1 汉字恰占 2 英文格；8 档字重，SIL OFL 1.1 许可。",
    type: "website",
  },
  twitter: {
    card: "summary",
    title: "JetHan Mono — JetBrains Mono × 思源等宽拼合字体",
    description: "终端严格 2:1 中英等宽的拼合字体，8 档字重。",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN" suppressHydrationWarning>
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased bg-background text-foreground`}
      >
        {children}
        <Toaster />
      </body>
    </html>
  );
}
