# Server Deployed Snapshot

这个目录是从 `ssh tengxun` 上当前部署目录直接抽取的代码快照：

- 来源目录：`/root/pk10/pk10_live_dashboard`

## 包含内容

- `backend/app/`
- `deploy/`
- `frontend/src/`
- `frontend/dist/`
- `frontend/package*.json`
- `frontend/vite.config.js`
- `backend/.env.example`

## 不包含内容

- `.venv/`
- `node_modules/`
- 真实 `.env`
- 密钥、密码、私有配置

## 作用

- 用来保留服务器“当前实际运行版本”的源码与前端发布产物
- 与本地 `code/pk10_live_dashboard/` 相对照时，可以核实线上是否与本地同步
