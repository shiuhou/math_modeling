# 工具參考

查核日期：2026-10-11。以下是工具行為的官方依據；repo 的任務命名、目錄與留言機制是本模板的設計，不是 Codex 原生協作服務。

| 內容 | 官方文件 |
| --- | --- |
| `AGENTS.md` 發現順序與啟動時載入 | [OpenAI：Custom instructions](https://developers.openai.com/codex/guides/agents-md) |
| `.agents/skills/`、`SKILL.md` frontmatter 與按需載入 | [OpenAI：Skills](https://developers.openai.com/codex/skills) |
| CLI 安裝 | [OpenAI：Codex CLI](https://developers.openai.com/codex/cli) |
| 登入方式與裝置碼登入 | [OpenAI：Authentication](https://developers.openai.com/codex/auth) |
| CLI 參數與 `codex resume` | [OpenAI：CLI reference](https://developers.openai.com/codex/cli/reference) |
| 多工作目錄、分支與共用 metadata | [Git：git-worktree](https://git-scm.com/docs/git-worktree) |
| `attach -r`、`attach -d`、socket 和 `server-access` | [tmux：官方手冊](https://man.openbsd.org/tmux) |

部署時以主機已安裝版本的 `codex --help`、`tmux -V`、`man tmux` 為準。模板不綁定特定 Astra 模型 ID，也不宣稱自動建立跨帳號權限或替團隊完成真實 SSH／Codex 實測。
