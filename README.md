# OOT

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE) [![Python 3.13](https://img.shields.io/badge/Python-3.13-blue.svg)](#技术栈) [![Docker Ready](https://img.shields.io/badge/Docker-ready-2496ED.svg)](#docker-运行说明) [![CI](https://img.shields.io/badge/CI-GitHub_Actions-2088FF.svg)](.github/workflows/ci.yml)

> **Order of Things** — 一个基于 Streamlit 的个人物品、资产与心愿管理应用。

OOT 用来记录“我拥有什么、花了多少钱、现在是什么状态、凭证在哪里”。
它适合拿来管理数码产品、家居设备、收藏、订阅资产，或者任何你想系统化整理的物品。

## 特性

- **资产 / 心愿双模式**：既能管理已拥有物品，也能轻量记录想买的东西
- **资产总览**：查看总资产、日均成本、数量与状态分布
- **分类 / 标签**：支持多维整理与筛选
- **状态管理**：服役中 / 已退役 / 已卖出
- **图片与发票**：支持本地上传、预览、下载与替换清理
- **统计分析**：按分类、状态等维度查看资产情况
- **本地优先**：默认使用 SQLite，本地运行即可使用
- **Docker 支持**：可一键容器化部署

## 界面结构

- **首页**：资产总览、搜索、筛选、资产列表
- **心愿**：心愿总值、愿望列表
- **统计**：资产与状态分析
- **设置**：分类管理、标签管理、数据导出
- **侧栏新增**：统一的资产 / 心愿录入入口

## 技术栈

- **Python 3.13**
- **Streamlit**
- **SQLite**
- **Docker / Docker Compose**

## 目录结构

```text
oot/
├── app.py
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── run.sh
├── update.sh
├── README.md
├── CHANGELOG.md
├── CONTRIBUTING.md
├── LICENSE
├── docs/
│   ├── DEPLOYMENT.md
│   └── DEVELOPMENT.md
└── uploads/
```

## 快速开始

### 方式一：本地运行

```bash
cd oot
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py --server.headless true --browser.gatherUsageStats false --server.address 0.0.0.0 --server.port 8502
```

访问：<http://localhost:8502>

### 方式二：Docker Compose

```bash
cd oot
docker compose up -d --build
```

访问：<http://localhost:8502>

### 方式三：一键脚本

```bash
cd oot
./run.sh
```

## Docker 运行说明

### 直接运行

```bash
cd oot
docker build -t oot .
docker run -d \
  --name oot-app \
  -p 8502:8502 \
  -v $(pwd)/uploads:/app/uploads \
  -v $(pwd)/oot.db:/app/oot.db \
  --restart unless-stopped \
  oot
```

### 数据持久化

建议持久化以下路径：

- `./uploads` → `/app/uploads`
- `./oot.db` → `/app/oot.db`

这样在重建容器后：
- 资产数据不会丢失
- 图片与发票不会丢失

## 常用脚本

### 启动项目

```bash
./run.sh
```

### 更新并重建

```bash
./update.sh
```

## 功能说明

### 资产字段

- 名称
- 价格
- 购买日期
- 分类
- 标签
- 状态
- 目标成本
- 备注
- 图片
- 发票
- 是否计入总资产
- 是否计入日均成本
- 到期日期 / 到期提醒

### 心愿字段

保持轻量，仅包含：

- 名称
- 价格
- 图片
- 备注

## 导出能力

设置页支持导出全部数据 CSV，用于：

- 备份
- 迁移
- 二次分析

## 文档

- 部署说明：[`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md)
- 开发说明：[`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md)
- 贡献指南：[`CONTRIBUTING.md`](CONTRIBUTING.md)
- 变更记录：[`CHANGELOG.md`](CHANGELOG.md)

## 路线建议

未来可以继续扩展：

- 多主题切换
- 更细的统计图表
- 数据导入
- 保修 / 到期提醒增强
- 多用户或账户隔离
- 更完整的发票预览支持

## License

MIT
