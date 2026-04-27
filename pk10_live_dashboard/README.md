# PK10 Live Dashboard

部署目标：

- 后端：`FastAPI`，监听 `127.0.0.1:18080`
- 前端：`Vite React`，最终由 `nginx` 直接服务
- 公网入口：`http://<host>:5173`
- 权限：应用内登录页 + cookie 会话
- 进程托管：`pm2`
- 静态目录建议发布到：`/var/www/pk10-live`

首次启动时，如果 `PK10_AUTH_STORE` 指向的用户文件不存在，后端会创建一个管理员：

- 用户名：`PK10_ADMIN_USER`，默认 `admin`
- 密码：`PK10_ADMIN_PASSWORD`，默认 `admin123456`

上线前建议在 `.env` 里设置 `PK10_AUTH_SECRET` 和新的初始管理员密码。创建用户后可在页面右上角进入「用户管理」新增、停用、改密或删除用户。

核心冻结口径：

- `face`: `core40_spread_only__exp0_off__oe40_spread_only__cd2`
- `sum`: `intraday_1037`
- `exact`: `late|big|edge_low|same_top1_prev=all + obs=192 + front_pair_major_consensus_only`
- 资金池：`1000 / 10 / shared bankroll`
- `face/sum`: 马丁 `1-2-4-5`
- `exact`: 固定 `10`
- blackout: `06:00-07:00`

主要路径：

- 后端入口：`backend/app/main.py`
- 用户认证：`backend/app/auth.py`
- 前端入口：`frontend/src/App.jsx`
- pm2 配置：`deploy/ecosystem.config.cjs`
- nginx 配置：`deploy/pk10.nginx.conf`
