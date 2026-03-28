# 信息收集结果管理平台（真实抓取版）

已对接真实抓取数据（非前端假数据）：
- 微信公众号（miku_ai，依赖 `~/.agent-reach-venv`）
- V2EX 热门
- Reddit 搜索

并落库保存：
- `sources`（监听源状态）
- `logs`（源头获取记录）
- `news`（资讯结果）

数据库文件：`data.db`（SQLite）

---

## 环境准备（含公众号抓取依赖）

> 项目里微信公众号抓取是通过 `~/.agent-reach-venv/bin/python` 调用 `miku_ai` 完成。
> 若你只想跑 V2EX/Reddit，可跳过这部分。

### 1) 创建并安装 `~/.agent-reach-venv`

```bash
python3 -m venv ~/.agent-reach-venv
~/.agent-reach-venv/bin/python -m pip install -U pip
~/.agent-reach-venv/bin/python -m pip install -r requirements-agent-reach.txt
```

### 2) 验证安装

```bash
~/.agent-reach-venv/bin/python -c "import miku_ai; print('miku_ai ok')"
```

如果输出 `miku_ai ok`，说明公众号依赖可用。

### 3) 常见问题

- 报错 `~/.agent-reach-venv/bin/python 不存在`
  - 说明虚拟环境没创建成功，重新执行上面的 venv 创建命令。
- 报错 `No module named miku_ai`
  - 说明包未安装到该虚拟环境，重新执行安装命令。

## 启动

```bash
cd /Users/biguncle/project/aihot-source-monitor
python3 -m pip install -r requirements.txt
python3 server.py
```

打开：`http://127.0.0.1:8090`

## 账号与注册

- 默认管理员账号：`bg`
- 默认管理员密码：`dd0131uu`
- 新用户注册地址：`http://127.0.0.1:8090/register`
- 注册时必须填写邀请码（后端校验）
- 邀请码可在登录后“平台管理”页面查看（管理员可见）
- 默认预置邀请码：`AIHOT2026`

## 使用

1. 打开页面后，先看“监听源”“源头获取记录”（初始状态）
2. 点击右上角 **“模拟抓取一批”**（按钮文案沿用，但实际是“真实抓取”）
3. 输入关键词（用于公众号和 Reddit）
4. 抓取完成后检查：
   - 热点资讯：有新增条目
   - 监听源：状态变更（ok/err）
   - 源头获取记录：有每个来源的成功/失败日志

## 验收标准（可跑通）

- 服务可启动、页面可访问
- 能成功发起至少 1 次真实抓取
- 抓取结果和日志可在页面展示
- 重启服务后历史数据仍在（SQLite）

## 说明

- 公众号抓取依赖：`~/.agent-reach-venv/bin/python` + `miku_ai`
- 若该环境不存在，日志中会显示失败原因，但不影响其他源抓取
- 你可在 `server.py` 中继续追加更多 source（如 GitHub/X/小红书）