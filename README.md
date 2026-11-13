# 控制算法学习

控制理论与嵌入式开发两个母题的学习记录。文档正文按专题整理，配套可运行代码，站点用于公开发布。

站点地址：`https://cjy719hnu.github.io/control-notes/`（仓库名确定后以实际为准）

## 内容构成

| 目录 | 内容 |
|------|------|
| `控制算法学习.md` | 原始总文档，包含全部专题笔记，是站点文章的唯一来源 |
| `卡尔曼滤波学习/` | 专题一代码：光流与加速度计融合滤波，含实时 Q/R 调参界面 |
| `广义动量观测学习/` | 专题二代码：一维刚体外部力观测仿真，含调参界面 |
| `content/` | 站点文章（由脚本从总文档生成，不手工编辑） |
| `assets/scss/custom.scss` | 暖粉配色覆写，主题源码未改动 |
| `scripts/` | 总文档到站点文章的无损拆分工具 |
| `hugo.toml` | 站点配置 |
| `themes/hugo-theme-stack` | Stack 主题（直接收录在仓库内，固定 v4.0.3） |

两个母题对应站点分类：`控制理论` 与 `嵌入式开发`。目前控制理论已有内容，嵌入式开发待补充。

## 本地预览

需要 Hugo extended（编译 SCSS 必须用 extended 版本），Windows 可用：

```powershell
winget install Hugo.Hugo.Extended
```

首次获取仓库：

```bash
git clone <仓库地址>
```

主题已经收录在 `themes/hugo-theme-stack`，不需要额外拉取子模块。

启动本地预览：

```bash
hugo server -D
```

默认地址 `http://localhost:1313/`。带子路径的站点在本地访问时需要加路径，例如 `http://localhost:1313/control-notes/`，以启动日志打印的地址为准。

## 文章如何生成

站点文章不是手写的，由 `控制算法学习.md` 按标题切分而来：

```bash
python scripts/build_content.py        # 生成或更新 content/posts/*.md
python scripts/build_content.py --check # 只校验是否同步，不同步则退出码 1
```

这样做的原因：

1. 总文档是学习时真正在维护的文件，站点只是它的发布视图，避免两处各改一遍；
2. 拆分过程对正文逐字不动，只在切片处统一标题层级、补 front matter；
3. 脚本每次运行都会把切片按原顺序拼回去与原文比对，字节不一致直接报错退出。

切分规则集中在 `scripts/config.py` 的 `POST_RULES`，增补专题时只改这一处。生成的文章**不要手工编辑**，下次运行会被覆盖。

## 发布

1. 在 GitHub 新建仓库（建议 `control-notes`，需为 public 才能用免费 Pages）；
2. 关联并推送：

```bash
git remote add origin git@github.com:<用户名>/control-notes.git
git push -u origin main
```

3. 仓库 Settings → Pages → Build and deployment → Source 选择 **GitHub Actions**；
4. 之后每次 push 到 `main`，`.github/workflows/deploy.yml` 会自动构建并发布。

工作流在构建前会执行 `python3 scripts/build_content.py --check`，如果改了总文档却忘了重新生成文章，发布会直接失败，避免站点内容与文档不一致。

## 换仓库名或换用户名

要改两处，都在配置层，不涉及正文：

1. `hugo.toml` 的 `baseURL`：决定站内链接前缀。工作流构建时会用 `actions/configure-pages` 输出的实际地址覆盖它，所以即使忘了改，线上也能正常访问，改它是为了让本地预览一致；
2. `scripts/config.py` 的 `CODE_REPO_URL`：文章末尾“配套代码”链接指向的仓库地址，这个不会被工作流覆盖，必须与真实仓库一致。

## 换配色

`assets/scss/custom.scss` 覆写的是 Stack 主题的 CSS 变量，浅色与暗色两套都在同一个文件里，不需要改主题源码。主题升级不会冲掉配色。

## 代码说明

两个专题目录保持原有的分层结构（`app/controller/service/model/driver/utils/config/test`），依赖只有 `numpy`、`matplotlib`：

```bash
cd 卡尔曼滤波学习
pip install -r requirements.txt
python kaerm_index.py      # 打开调参界面
python -m unittest discover -s test -t . -v
```

调参界面依赖本机图形环境，在网页上不能直接运行，需要克隆到本地。

## 环境版本

| 组件 | 版本 | 说明 |
|------|------|------|
| Hugo extended | 0.169.0 | 主题要求 >= 0.157.0，工作流里同步固定为该版本 |
| Hugo Theme Stack | v4.0.3 | 收录在 `themes/` 内，升级时用新版本整目录替换 |
| Python | >= 3.10 | 拆分脚本只依赖标准库 |
