# NFC 碰一碰播歌 (NFC Touch Player)

> 一张 NFC 标签贴在墙上 / 挂在包上，**安卓手机碰一下就播你指定的歌**。
> 零服务器、零域名、零 App、零读卡器硬件。

[![deploy](https://img.shields.io/badge/deploy-EdgeOne%20Pages-blue)](https://edgeone.ai/pages)

---

## 线上地址

| 用途 | 地址 |
|---|---|
| GitHub 仓库 | https://github.com/burningleaves/nfc-player |
| GitHub Pages（备用托管，已跑通） | https://burningleaves.github.io/nfc-player/ |
| 音频直链 | https://raw.githubusercontent.com/burningleaves/nfc-player/main/audio/<文件> |

落地页在 `site/` 目录，通过 GitHub Actions 自动发布到 Pages。
主托管推荐 EdgeOne Pages（国内实测 285ms），见 [docs/08_NFC碰一碰播歌.md](docs/08_NFC碰一碰播歌.md) 的 4.4。

---

## 它是怎么工作的

```
NFC 标签 (NTAG213, 144 字节)
   │  NDEF URI: https://<你的域名>/?id=mysong
   ▼
安卓手机碰一下 -> 浏览器打开落地页
   │
   ▼
落地页读 config.json -> 找到这一首歌的直链
   │
   ▼
<audio> 播放 (支持拖进度)
```

**关键点：NFC 标签只存一个几十字节的短 URL。** 一首歌有几个 MB，
标签装不下，所以音频托管在 GitHub 仓库里，落地页托管在 EdgeOne Pages 上。

---

## 目录结构

```
nfc-player/
├── site/
│   ├── index.html          落地页播放器（单文件，无依赖，响应式）
│   └── config.json        短 ID -> 音频直链 映射
├── audio/                 音频文件（用 raw.githubusercontent 直链引用）
│   └── .gitkeep
├── tools/
│   ├── make_config.py     生成 config.json + 打印标签 URL
│   ├── nfc_write.py       生成 NDEF URI 记录（十六进制 + .ndef 文件）
│   └── deploy_check.py    部署自检（实测直链 Range 支持）
├── docs/
│   └── 08_NFC碰一碰播歌.md   完整部署文档
└── vercel.json            Vercel 部署配置（备用托管）
```

---

## 快速开始

```powershell
# 1. 生成配置（把音频直链填进去）
python tools/make_config.py --site "https://<你的域名>" \
  --song "我的歌=https://raw.githubusercontent.com/<你>/nfc-player/main/audio/song.mp3" \
  --short mysong

# 2. 部署前自检（会实测直链能否访问 + 是否支持 Range）
python tools/deploy_check.py --site "https://<你的域名>"

# 3. 生成要写进 NFC 标签的 NDEF 数据
python tools/nfc_write.py "https://<你的域名>/?id=mysong"
```

写标签：安卓手机装 **NFC Tools**，新建 URI 记录 -> 粘贴短 URL -> 贴近标签。

完整步骤见 [docs/08_NFC碰一碰播歌.md](docs/08_NFC碰一碰播歌.md)。

---

## 实测数据（本方案的技术验证记录）

| 项 | 结果 |
|---|---|
| GitHub **raw** 直链支持 Range | 206 + `Content-Range: bytes 0-511/37206`，MIME `audio/mpeg` |
| GitHub **Release 资产**直链 | 302 跳到 `objects.githubusercontent.com`，**国内 25s 超时** -> 已排除 |
| jsDelivr | 快，但不支持 Release 资产 |
| EdgeOne Pages 落地页 | 285 ms |
| Vercel 落地页 | 323 ms |
| Cloudflare Pages 落地页 | **15414 ms** -> 已排除 |
| NDEF URI 编码长度 | 54 字节（NTAG213 上限 144） |

---

## 已知限制

- **自动播放大概率被拦截，需要点一下**。Chrome/WebView 禁止「无用户手势」播放，
  而 NFC 跳转算导航不算手势。**第一次手动播放后浏览器会记住交互状态，之后碰标签就自动播。**
- 必须联网（音频和落地页都在云端）。
- 锁屏时碰标签不触发（Android 14+ 禁止后台读 NFC）。

---

## License

MIT
