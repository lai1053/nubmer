# PK10 Live Dashboard

部署目标：

- 后端：`FastAPI`，监听 `127.0.0.1:18080`
- 前端：`Vite React`，最终由 `nginx` 直接服务
- 公网入口：`http://<host>:5173`
- 权限：`Basic Auth`
- 进程托管：`pm2`
- 静态目录建议发布到：`/var/www/pk10-live`
- Basic Auth 文件建议放到：`/etc/nginx/pk10-live.htpasswd`

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
- 前端入口：`frontend/src/App.jsx`
- pm2 配置：`deploy/ecosystem.config.cjs`
- nginx 配置：`deploy/pk10.nginx.conf`
