# Deployment Guide

## 1. Requirements

- Docker
- Docker Compose
- 可用的 `8502` 端口

## 2. Recommended deployment

```bash
cd oot
docker compose up -d --build
```

## 3. Check service

```bash
docker compose ps
docker compose logs -f
```

默认访问地址：
- `http://localhost:8502`

## 4. Data persistence

项目使用以下持久化路径：

- `./uploads`：图片、发票等上传文件
- `./oot.db`：SQLite 数据库

如果迁移服务器，请至少备份这两个路径。

## 5. Update project

```bash
./update.sh
```

或手动执行：

```bash
git pull --rebase
docker compose up -d --build
```

## 6. Stop project

```bash
docker compose down
```

## 7. Reverse proxy (optional)

如果要对外提供服务，建议在前面加 Nginx / Caddy，并处理：

- HTTPS
- 域名绑定
- 基础认证
- 访问控制
