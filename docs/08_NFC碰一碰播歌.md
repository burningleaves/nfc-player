# 08 - NFC 碰一碰播歌（零服务器版）

> 一张 NFC 标签贴在墙上 / 挂在包上，**安卓手机碰一下就播你指定的歌**。
> 不需要服务器、不需要域名、不需要 App、不需要 NFC 读卡器硬件。

---

## 一、先看清楚它的能力边界

| 你想要的 | 能不能 | 为什么 |
|---|---|---|
| 碰一下自动播放 | 需要点一下 | Chrome/WebView 的自动播放策略禁止「无用户手势」播放。NFC 跳转过去算导航，**不算手势** |
| 完全离线播放 | 不行 | 音频托管在 GitHub 上，必须联网 |
| 任意安卓手机都能用 | 可以 | 用浏览器打开，不需要装 App |
| iPhone 也能用 | 需点一下 | iOS Safari 同样拦截自动播放 |
| 一张卡放一首歌 / 多首歌 | 可以 | 每张卡一个短 ID，?id=xxx 区分 |
| 锁屏时碰标签 | 不行 | Android 14+ 禁止后台 App 读 NFC |

**实测结论（本项目已验证）**：

- 自动播放被拦截时，页面自动降级为醒目的「播放」大按钮，一点即播
- 第一次手动点过播放后，浏览器会记住该站点的「已交互」状态，
  **之后再碰标签大概率能直接自动播**
- 所以实际体验是：**第一次点一下，之后一碰就响**

---

## 二、整体架构

```
你的 mp3
   |
   |  提交到 GitHub 仓库的 audio/ 目录
   v
https://raw.githubusercontent.com/<你>/nfc-player/main/audio/song.mp3
   |
   |  写进 site/config.json
   v
config.json  { songs: [ { id: demo, url: <上面那个直链> } ] }
   |
   |  推送到 GitHub -> 托管平台自动部署
   v
https://<你的域名>/
   |
   |  写进 NFC 标签（NDEF URI，约 40 字节）
   v
NFC 标签
```

**分工**：GitHub 当**仓库**（存代码和音频），托管平台只托管**落地页 HTML**。
两者都零成本、零运维。

| 组件 | 选型 | 实测延迟 |
|---|---|---|
| 落地页托管 | **EdgeOne Pages**（腾讯云） | 285 ms |
| 落地页托管（备选） | Vercel | 323 ms |
| ~~落地页托管~~ | ~~Cloudflare Pages~~ | ~~15414 ms 已排除~~ |
| 音频直链 | **raw.githubusercontent.com** | 757 ms |
| 音频直链（回退） | cdn.jsdelivr.net/gh/ | 709 ms |
| ~~音频直链~~ | ~~releases/download~~ | ~~302 跳 objects.githubusercontent.com，25s 超时 已排除~~ |

### 为什么音频不用 Release 资产

`releases/download/` 会 302 跳到 `objects.githubusercontent.com`，
这个域名在国内实测 **25 秒超时**。而 `raw.githubusercontent.com`
走的是另一条 CDN 路径，只要 757 ms，且 **支持 Range**（可拖进度）、
MIME 正确（`audio/mpeg`）。

代价是 raw 单文件上限 100 MB —— 一首歌远远够用。

### 多源回退（重要）

`config.json` 里的 `url` 支持用 `|` 分隔多个候选源：

```json
{
  "id": "mysong",
  "title": "我的歌",
  "url": "https://raw.githubusercontent.com/<你>/nfc-player/main/audio/song.mp3|https://cdn.jsdelivr.net/gh/<你>/nfc-player@main/audio/song.mp3"
}
```

第一个源加载失败会自动换第二个，界面上会显示「标题 2/2」告诉你用的是第几个。
**任何单一 CDN 抽风都不会导致播不出来。**

---

## 三、准备材料

- [ ] 一个 GitHub 账号
- [ ] 一张 **NTAG213** 标签（淘宝搜「NFC 标签 NTAG213 13.56MHz」，几块钱一片）
      - NTAG213 = 144 字节，够用；NTAG215 = 504 字节，也行
      - 认准 **13.56MHz ISO 14443A**，别买 UHF 848MHz（手机读不了）
- [ ] 一部安卓手机（用来写标签）
- [ ] 你的 mp3 文件

---

## 四、步骤

### 4.1 建仓库

```
仓库: nfc-player
  site/      <- 落地页 (index.html + config.json)
  audio/     <- 你的 mp3
  tools/     <- 脚本
  docs/      <- 文档
```

### 4.2 放音频

把你的 mp3 放进 `audio/`，文件名用英文（不要中文和空格）：

```
audio/song.mp3
```

提交后直链就是：

```
https://raw.githubusercontent.com/<你>/nfc-player/main/audio/song.mp3
```

> 分支名不是 main 的话要同步改。
> 注意用 **raw** 直链，**不要**用 `releases/download`（慢 25 秒，见上）。

### 4.3 生成配置

```powershell
cd D:\OpenWrt\nfc-player

python tools/make_config.py `
  --site "https://<你的域名>" `
  --song "我的歌=https://raw.githubusercontent.com/<你>/nfc-player/main/audio/song.mp3|https://cdn.jsdelivr.net/gh/<你>/nfc-player@main/audio/song.mp3" `
  --short mysong
```

输出会写好 `site/config.json`，并打印要写进标签的短 URL：

```
https://<你的域名>/?id=mysong
```

多首歌就多写几个 `--song` 和 `--short`：

```powershell
python tools/make_config.py `
  --site "https://<你的域名>" `
  --song "歌A=https://.../a.mp3" --song "歌B=https://.../b.mp3" `
  --short a --short b
```

### 4.4 部署落地页

**方式 A：EdgeOne Pages（推荐，腾讯云，国内快）**

1. 打开 https://console.cloud.tencent.com/edgeone/pages
2. 新建项目 -> 选择 **GitHub** 作为代码源 -> 授权并选 `nfc-player` 仓库
3. 构建配置：**构建命令留空**，**输出目录填 `site`**
4. 部署完成，拿到 `xxx.edgeone.app` 域名
5. 需要自有域名的话在项目里加 CNAME 记录

**方式 B：Vercel**

```powershell
npm i -g vercel
vercel --prod --yes site
```

**方式 C：GitHub push 自动部署**

在 EdgeOne / Vercel 后台把仓库绑上（方式 A 的第 2 步），
之后每次改完 config.json，只要 push 就会自动重新部署：

```powershell
python tools/deploy.py
```

这条命令会依次尝试 git push / edgeone CLI / vercel CLI。

**本仓库已经内置 GitHub Actions**（`.github/workflows/deploy-pages.yml`），
push 之后 GitHub Pages 会自动重新发布，地址：
https://burningleaves.github.io/nfc-player/

这是当前**已经跑通**的托管路径，可以直接当备用。

### 当前线上地址

| 用途 | 地址 |
|---|---|
| **EdgeOne Pages（主）** | https://nfc-player-dpre48ptcgkc.edgeone.cool/ |
| **播放器完整地址** | **https://nfc-player-dpre48ptcgkc.edgeone.cool/?id=love** |
| GitHub Pages（备用） | https://burningleaves.github.io/nfc-player/ |

**EdgeOne 加速区域：全球可用区（包含中国大陆）** —— 无需 ICP 备案。

### EdgeOne 中国大陆可用区的实测坑

选「全球可用区（包含中国大陆）」后，EdgeOne 会**按访问来源 IP 判断**：

- ✅ 国内网络（校园网 / 宽带 / 5G 移动网络）**直接可访问**
- ❌ 境外 IP 一律返回 `401 UNAUTHORIZED`（响应头 `X-EOP-MSG: eo_time missing`）
- ⚠️ 控制台的「预览」链接带 `?eo_token=...`，**只有 3 小时有效期**，不能写进 NFC 标签

所以标签里必须写**不带 token 的项目域名**：

```
https://nfc-player-dpre48ptcgkc.edgeone.cool/?id=love
```

### 访问时必须带 ?id=xxx

直接打开项目根域名会报「没有指定音频」—— 落地页需要 `?id=` 才知道播哪首。
每个 id 对应 config.json 里的一条 song。

---

## 音频搬国内（腾讯云 COS）

落地页已经在 EdgeOne 上了，音频目前仍走 GitHub raw（国内 1~5 秒波动）。
要进一步提速，把音频放到腾讯云 COS。

### 为什么用 COS

- COS 默认域名**免备案**，国内直连 100~200ms
- 4MB 音频存储费约 0.01 元/月，流量 10GB/月免费额度绰绰有余
- 音频在 `<audio>` 里播放不受「默认域名强制下载」限制影响

> 2024 年 1 月后新建的桶，用**默认域名**访问 HTML 会被加
> `Content-Disposition: attachment` 强制下载，**所以落地页不能放 COS**。
> 这也是为什么落地页用 EdgeOne、音频用 COS。

### 操作步骤

**1. 开通 COS 并建桶**

```
console.cloud.tencent.com/cos
  -> 新建存储桶
  -> 名称: nfc-player   (会自动加 APPID 后缀)
  -> 所属地域: 选离你近的 (上海/广州/北京)
  -> 访问权限: 公有读私有写   <- 重要, 要让别人能下载音频
  -> 其他默认
```

**2. 拿密钥**

```
console.cloud.tencent.com/cam/capi
  -> 新建密钥
  -> SecretId / SecretKey
```

**3. 上传**

```powershell
cd D:\OpenWrt
fc-player

python tools\cos_upload.py --bucket nfc-player-你的APPID --region ap-shanghai
```

密钥走环境变量更安全 (不进命令行历史):

```powershell
$env:TENCENT_SECRET_ID = "AKIDxxxx"
$env:TENCENT_SECRET_KEY = "xxxx"
python tools\cos_upload.py --bucket nfc-player-你的APPID --region ap-shanghai
```

脚本会输出音频直链, 形如:

```
https://nfc-player-1250000000.cos.ap-shanghai.myqcloud.com/audio/love-cliff.m4a
```

**4. 写进配置并推送**

```powershell
python tools\make_config.py --site "https://nfc-player.edgeone.dev" `
  --song "爱情悬崖=https://nfc-player-你的APPID.cos.ap-shanghai.myqcloud.com/audio/love-cliff.m4a" `
  --short love

python toolspi_push.py
```

推送后 EdgeOne 自动重新部署，**标签不用重写**。


> **推送失败时**：如果 `git push` 报 `Failed to connect to github.com:443`，
> 说明你的网络阻断了 github.com 的 git 端点（但 api.github.com 通常还通）。
> 此时用 GitHub REST API 提交，见本文末尾「推送失败时的替代路径」。

### 4.5 写 NFC 标签

**方式 A（推荐，手机 App）**

1. 安卓手机装 **NFC Tools**（或 *NDEF Tag Editor* / *NFC Tag Writer*）
2. 打开 App -> 新建记录 -> 类型选 **URI/网址**
3. 粘贴短 URL
4. 保存
5. **手机背面贴近标签**，App 提示写入成功

**方式 B（十六进制）**

```powershell
python tools/nfc_write.py "https://<你的域名>/?id=mysong"
```

会打印 HEX，用支持十六进制输入的 App 粘贴。

**方式 C（PC + USB NFC 读卡器）**

把生成的 `tools/tag.ndef` 用 nfcpy / NFC Tools CLI 写到标签。

### 4.6 验收

```powershell
python tools/deploy_check.py --site "https://<你的域名>"
```

会检查：落地页完整性、config 合法性、**每个音频直链是否真的能访问、
是否支持 Range、实测延迟**，以及每张标签的 NDEF 字节数。

延迟超过 3 秒会标「慢!」，提示你换源或加回退。

---

## 五、多张卡 / 多首歌

每首歌一个短 ID，一张卡一个 ID：

| 标签 | 写入的 URL | 效果 |
|---|---|---|
| 客厅那张 | ?id=living | 碰一下播客厅歌单 |
| 车里那张 | ?id=car | 碰一下播车里歌单 |
| 床头那张 | ?id=sleep | 碰一下播助眠曲 |

改歌单只要改 `config.json` 重新推送，**标签不用重写**。

---

## 六、常见问题

**Q：碰标签后没反应 / 页面空白**
- 手机 NFC 开着吗？
- 标签是 13.56MHz 的吗？（有些便宜货是 125kHz 的）
- 浏览器弹了「是否允许打开此应用」吗？点允许

**Q：页面打开了但没有声音**
- 看是不是停在「点一下开始播放」——**这是自动播放被拦截，点一下就好**
- 第一次手动播放后，之后再碰一般就自动播了

**Q：显示「音频加载失败」**
- 跑 `deploy_check.py` 看是哪个源挂了
- 如果所有源都挂了，多半是文件名有中文或空格，或者音频没 commit 上去

**Q：界面上显示「我的歌 2/2」是什么意思**
- 说明第一个源（raw.githubusercontent）失败了，系统自动用了第二个（jsDelivr）
- 说明网络对 GitHub 不太友好，但不影响播放

**Q：进度条拖不动 / 时长显示不出来**
- 直链不支持 Range。自建源必须让服务器返回 `Accept-Ranges: bytes`

**Q：能不能离线圈？**
- 不能。音频在 GitHub 上，必须联网。
  要真正离线，只能把音频打包进一个 App 里（见下方「离线变体」）。

---

## 七、离线变体（可选）

```
音频 -> 打包进 APK（res/raw/）
标签 -> 写 mymusic://track/1
App  -> 监听该 scheme -> 播放内置音频
```

- 代价：换歌要重新打包 APK
- 好处：真离线、无需任何服务器
- 局限：每台手机都要装这个 App；Android 14+ 锁屏时碰标签不触发

---

## 八、工具清单

```
nfc-player\
├── site\
│   ├── index.html          落地页播放器（单文件，无依赖）
│   └── config.json        短 ID -> 音频直链 映射
├── audio\                 你的 mp3 放这里
├── tools\
│   ├── make_config.py     生成 config.json + 打印标签 URL
│   ├── nfc_write.py       生成 NDEF URI 记录（十六进制 + .ndef 文件）
│   ├── deploy_check.py    部署自检（含直链 Range 与延迟实测）
│   └── deploy.py          一键部署（git push / edgeone / vercel）
├── docs\08_NFC碰一碰播歌.md   本文件
└── vercel.json            Vercel 部署配置（备用托管）
```

四个脚本都**零第三方依赖**，标准库 Python 3 即可运行。

---

## 九、已验证事项

| 项 | 状态 |
|---|---|
| NDEF URI 记录编码（含前缀缩写） | 单元验证，NTAG213 容量内（约 40 字节） |
| raw.githubusercontent 直链 Range + MIME | 实测 206 / audio/mpeg |
| jsDelivr `gh/` 路径 Range | 实测 206 |
| GitHub Release 资产直链 | 实测 25s 超时 -> 已排除 |
| EdgeOne Pages 落地页 | 实测 285 ms |
| Vercel 落地页 | 实测 323 ms |
| Cloudflare Pages 落地页 | 实测 15414 ms -> 已排除 |
| 落地页 config.json 解析 | 浏览器实测 |
| 播放推进 / 结束 / 重播 | 浏览器实测（0:00 -> 0:03 -> 播放完毕） |
| 自动播放被拦截时的降级按钮 | 浏览器实测 |
| **多源回退（第一个 404 自动换第二个）** | **浏览器实测：显示「回退测试 2/2」** |
| 未知 id 的错误提示 | 浏览器实测 |
| 移动端 390px 布局 | 截图确认 |
| GitHub Actions 自动发布 Pages | 实测 workflow success，线上 index.html + config.json 均 200 |
| 真机 NFC 读写 + 出声 | 待你在真机上确认 |

---

## 十、推送失败时的替代路径

有些网络会阻断 `github.com` 的 git 端点（但 `api.github.com` 仍然通）。
实测表现：`git push` 报 `Failed to connect to github.com:443 after 21000 ms`。

这时可以用 GitHub REST API 提交，完全绕开 git 协议：

```powershell
python tools/api_push.py
```

它会做三件事：

1. 读取 `~/.git-credentials` 里已有的 PAT（不用重新输入密码）
2. 把 `site/`、`tools/`、`audio/`、`docs/` 下的改动提交成一个 commit
3. 推送前打印将要提交的文件列表让你确认

> PAT 需要 `repo` 权限（如果仓库是公开的，`public_repo` 也够）。
> 存在 `~/.git-credentials` 里的话，脚本会自动读取，不用额外配置。