音频文件放这个目录。

引用方式（用 raw 直链，不要用 releases/download —— 实测国内会 302 跳到
objects.githubusercontent.com，延迟 25 秒）：

    https://raw.githubusercontent.com/<你的用户名>/nfc-player/main/audio/<文件名>

分支名不是 main 的话要同步改。

配置示例见 site/config.json。
一个文件可以放多个候选源, 用 | 分隔, 前一个失效会自动换下一个:

    "url": "https://raw.githubusercontent.com/<你>/nfc-player/main/audio/song.mp3|https://cdn.jsdelivr.net/gh/<你>/nfc-player@main/audio/song.mp3"

注意:
- 单文件上限 100 MB (raw 直链) —— 一首歌远远够用
- 文件名不要用中文和空格, 用英文和短横线
- 改动后重新 push, 托管平台会自动重新部署
