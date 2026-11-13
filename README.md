# learning-control-theory-and-embedded-systems

控制理论与嵌入式开发两个母题的学习记录。文档正文按专题整理，配套可运行代码，站点用于公开发布。

站点地址：`https://unw-c.github.io/learning-control-theory-and-embedded-systems/`

## 内容构成

| 目录 | 内容 |
|------|------|
| `控制算法学习.md` | 原始总文档，包含全部专题笔记，是站点文章的唯一来源 |
| `卡尔曼滤波学习/` | 专题一代码：光流与加速度计融合滤波，含实时 Q/R 调参界面 |
| `广义动量观测学习/` | 专题二代码：一维刚体外部力观测仿真，含调参界面 |
| `content/` | 站点内容：首页导语、关于页、由脚本生成的专题文章 |
| `layouts/home.html` | 首页布局覆写，在文章列表上方插入 `content/_index.md` 的导语 |
| `assets/scss/custom.scss` | 暖粉配色与首页导语卡片样式，主题源码未改动 |
| `scripts/` | 总文档到站点文章的无损拆分工具 |
| `hugo.toml` | 站点配置，`baseURL` 唯一需要随仓库改名的地方 |
| `themes/hugo-theme-stack` | Stack 主题（直接收录在仓库内，固定 v4.0.3） |

两个母题对应站点分类：`控制理论` 与 `嵌入式开发`。控制理论已落地卡尔曼滤波与广义动量观测，嵌入式开发待补充。

## 本地预览

需要 Hugo extended（编译 SCSS 必须用 extended 版本），Windows 可用：

```powershell
winget install Hugo.Hugo.Extended
```

首次获取仓库：

```bash
git clone https://github.com/UNW-c/learning-control-theory-and-embedded-systems.git
```

主题已经收录在 `themes/hugo-theme-stack`，不需要额外拉取子模块。

启动本地预览：

```bash
hugo server -D
```

默认地址 `http://localhost:1313/`。带子路径的站点在本地访问时要加路径，例如 `http://localhost:1313/learning-control-theory-and-embedded-systems/`，以启动日志打印的地址为准。

## 文章如何生成

站点文章来自 `控制算法学习.md`，由脚本按标题切分：

```bash
python scripts/build_content.py         # 生成或更新 content/posts/*.md
python scripts/build_content.py --check # 只校验是否同步，不同步则退出码 1
```

这样做的原因：

1. 总文档是学习时真正在维护的文件，站点只是它的发布视图，避免两处各改一遍；
2. 拆分对正文逐字不动，只在切片处统一标题层级、补 front matter；
3. 表格单元格内代码段中的竖线会被转义成 `\|`（GFM 表格里 `|` 一律算分列符，不转义会把 `x_k|k-1` 切成两格），渲染结果与原文一致；
4. 脚本每次运行都会把切片按原顺序拼回去与原文比对，字节不一致直接报错退出。

切分规则集中在 `scripts/config.py` 的 `POST_RULES`，增补专题时只改这一处。生成的文章不要手工编辑，下次运行会被覆盖。

新增一篇专题的步骤：

1. 在 `控制算法学习.md` 里按 `## 专题三：xxx` 的结构追加内容；
2. 在 `POST_RULES` 里加一条规则，指定起止标题、slug、分类与标签；
3. 运行 `python scripts/build_content.py` 重新生成。

嵌入式开发的专题可以单独成文，分类写 `嵌入式开发`，其余流程一致。

## 发布

1. 仓库已就绪（需为 public 才能使用免费 Pages）；
2. 首次推送：

```bash
git remote add origin git@github.com:UNW-c/learning-control-theory-and-embedded-systems.git
git push -u origin main
```

3. 仓库 Settings → Pages → Build and deployment → Source 选择 **GitHub Actions**。
   这一步必须在网页上手动做一次：工作流的 `GITHUB_TOKEN` 没有管理员权限，无法替你创建 Pages 站点（会报 `Resource not accessible by integration`）；
4. 之后每次 push 到 `main`，`.github/workflows/deploy.yml` 会自动构建并发布。

工作流在构建前会执行 `python3 scripts/build_content.py --check`，如果改了总文档却忘了重新生成文章，发布会直接失败，避免站点内容与文档不一致。

## 换仓库名或换用户名

要改两处，都在配置层，不涉及正文：

1. `hugo.toml` 的 `baseURL`：决定站内链接前缀。工作流构建时会用 `actions/configure-pages` 输出的实际地址覆盖它，所以即使忘了改，线上也能正常访问，改它是为了让本地预览一致；
2. `scripts/config.py` 的 `CODE_REPO_URL`：文章末尾「配套代码」链接指向的仓库地址，这个不会被工作流覆盖，必须与真实仓库一致。

## 改文案与配色

- 首页导语：`content/_index.md`，改完直接生效，不需要重新生成文章；
- 关于页：`content/page/about/index.md`；
- 配色：`assets/scss/custom.scss` 覆写 Stack 的 CSS 变量，浅色与暗色两套在同一文件里，主题升级不会冲掉。

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
