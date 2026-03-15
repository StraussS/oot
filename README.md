# OOT

Order of Things（OOT），一个基于 Streamlit 的个人物品与资产管理应用。

核心结构：
- 首页：资产总览 / 状态筛选 / 资产列表
- 心愿：心愿总值 / 心愿列表
- 统计：资产与状态分析
- 设置：分类管理 / 标签管理 / 数据导出
- 新增：统一的资产 / 心愿录入表单

## 本地运行

```bash
cd oot
python3 -m pip install -r requirements.txt
streamlit run app.py
```

## Docker 运行

### 方式 1：直接构建运行

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

### 方式 2：docker compose

```bash
cd oot
docker compose up -d --build
```

## 功能

- SQLite 本地存储
- 资产 / 心愿 双类型
- 分类 / 标签
- 状态管理：服役中 / 已退役 / 已卖出
- 图片上传
- 发票上传 / 下载 / 部分预览
- 到期日期 / 到期提醒字段
- 是否计入总资产 / 日均成本
- 统计页、编辑页、CSV 导出

## 数据持久化

Docker 方式下建议持久化这两个路径：
- `./uploads` → `/app/uploads`
- `./oot.db` → `/app/oot.db`


## 一键脚本

### 启动
```bash
cd /home/porishi/.openclaw/workspace/oot
./run.sh
```

### 更新
```bash
cd /home/porishi/.openclaw/workspace/oot
./update.sh
```
