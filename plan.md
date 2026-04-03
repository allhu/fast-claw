# FastClaw: Shopify 商家网址与联系方式抓取系统

## 1. 产品概述
FastClaw 是一个多渠道的 Shopify 商家线索采集系统。旨在通过自动化脚本和半自动化工具，从不同来源发现 Shopify 独立站网址，并进一步抓取和结构化这些商家的联系方式（邮箱、电话、社交媒体等），最终汇聚到统一的数据库中供业务使用。

## 2. 核心功能模块

### 2.1 数据源与链接获取模块
系统支持三种主要的 Shopify 商家发现方式：
1. **Google 搜索自动化**: 通过特定的 Google Dorks (如 `site:myshopify.com "contact us"`) 批量获取 Shopify 商家链接。
2. **Chrome 浏览器插件 (半自动化)**: 辅助业务人员在浏览网页（如行业论坛、展会名录等）时，一键提取页面上的 Shopify 链接并保存到云端数据库。
3. **广告数据源抓取**: 监控和抓取 Facebook Ads Library 或 Google Shopping 的广告数据，解析广告落地页，识别并提取 Shopify 商家网址。

### 2.2 联系方式深度抓取模块
- **网页爬虫**: 访问已获取的 Shopify 商家网址，自动寻找 "Contact Us", "About Us", 页面底部 (Footer) 等关键位置。
- **信息提取**: 使用正则表达式或大语言模型 (LLM) 提取邮箱 (Email)、电话号码 (Phone)、WhatsApp、以及社交媒体主页链接 (Facebook, Instagram, Twitter 等)。

### 2.3 数据存储与管理模块
- 统一的数据库存储商家 URL、联系方式、发现来源、抓取状态等信息。
- 提供基础的 API 供插件和爬虫写入数据，以及供前端或外部系统读取/导出数据 (CSV/Excel)。

---

## 3. 技术栈建议
- **后端 API 与核心逻辑**: Python (FastAPI) - 适合快速开发 API 和编写爬虫脚本。
- **爬虫技术**: Playwright (应对动态渲染的广告页面和反爬) + BeautifulSoup/Scrapy (常规页面解析)。或者直接使用 SERP API 替代 Google 搜索爬虫以降低反爬风险。
- **数据库**: PostgreSQL 或 SQLite (初期可使用 SQLite 快速起步)。
- **Chrome 插件**: HTML/CSS + JavaScript (Manifest V3)。

---

## 4. 研发计划 (分阶段实施)

### 阶段一：基础设施与数据库搭建 (MVP 基础)
- 设计数据库表结构（Store, Contact, Source_Log）。
- 搭建 FastAPI 后端服务。
- 实现基础的 CRUD API，允许存入 URL 和查询数据。

### 阶段二：Chrome 插件开发 (快速收集)
- 开发 Manifest V3 插件。
- 实现提取当前网页所有外链，并初步过滤出可能的 Shopify 链接。
- 实现一键将选中的链接发送到后端 API 保存。

### 阶段三：联系方式抓取引擎 (核心业务)
- 开发基于 Playwright/HTTPX 的异步爬虫。
- 实现调度器，定期从数据库拉取未处理的 URL。
- 实现信息提取逻辑（识别 Shopify 特征、提取邮箱、电话等）。
- 将提取结果更新回数据库。

### 阶段四：Google 搜索与广告数据源抓取 (自动化拓客)
- **Google 搜索**: 集成 SerpApi 或编写 Playwright 脚本执行 `site:myshopify.com` 等高级搜索。
- **FB Ads / Google Shopping**: 编写针对广告库的自动化浏览器脚本，提取落地页链接并判断是否为 Shopify 站点 (通过检测网页源码中的 `Shopify.theme` 等特征)。

### 阶段五：数据导出与后台面板 (完善期)
- 提供简单的 Web 页面或高级 API 用于筛选和导出数据 (CSV 格式)。

---

## 5. 待确认事项
- 后端语言和数据库是否同意使用 Python (FastAPI) + SQLite/PostgreSQL？
- 是否优先从**阶段一（基础设施）**和**阶段二（Chrome 插件）**开始？