# Contributing

欢迎改进 OOT。

## 建议流程

1. Fork 项目
2. 新建分支
3. 完成修改
4. 本地验证
5. 提交 PR

## 提交前检查

```bash
python3 -m py_compile app.py
```

如果你修改了容器相关内容，也建议验证：

```bash
docker compose config
```

## Commit message 建议

- `feat: add xxx`
- `fix: resolve xxx`
- `docs: improve xxx`
- `style: refine xxx`
- `refactor: simplify xxx`

## 贡献方向

- UI/UX 优化
- 统计能力增强
- 导入/导出能力完善
- 文档完善
- 容器部署改进
