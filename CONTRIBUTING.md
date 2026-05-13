# 贡献指南

感谢你愿意为 CNKI研究助手 添砖加瓦！🎉

---

## 我能贡献什么？

### 🐛 报告Bug
遇到问题？请先确认：
- 使用最新版本的代码（`git pull`）
- 查看 [常见问题](docs/setup-guide.md#常见问题排查)

确认bug后，请提交 [Issue](https://github.com/chonpszhou/cnki-research-helper/issues)，
包含以下信息：
- 你的操作系统和版本
- Python和Node.js版本
- 完整的错误信息
- 复现步骤

### 💡 提出新功能
- 功能是否真正通用？（而不是只有你自己需要）
- 能否用简洁的代码实现？

### 📖 完善文档
- 错别字、语法错误
- 描述不够清晰的地方
- 你觉得新手会遇到困难的地方

### 🧪 优化代码
- 提PR前先跑一遍 `python3 scripts/cnki_downloader.py --help` 确认基本功能正常
- 保持代码风格一致
- 添加必要的注释

---

## 开发流程

### 1. Fork & Clone

```bash
# Fork后在你自己账号下有一个副本
git clone https://github.com/YOUR_USERNAME/cnki-research-helper.git
cd cnki-research-helper
```

### 2. 创建分支

```bash
git checkout -b feature/your-feature-name
# 或
git checkout -b fix/bug-description
```

### 3. 开发 & 测试

```bash
# 测试脚本基本运行
python3 scripts/cnki_downloader.py --help

# 测试CDP连接
curl -s http://127.0.0.1:3456/health
```

### 4. 提交代码

```bash
git add .
git commit -m "简短描述：做了什么事"
git push origin your-branch-name
```

### 5. 提PR

在 GitHub 上发起 Pull Request，描述：
- 这个改动解决了什么问题
- 你是怎么测试的
- 截图（如果有UI变化）

---

## 代码规范

- Python：遵循 [PEP 8](https://pep8.org/)
- JavaScript：使用标准格式（`node scripts/` 目录下的代码）
- 注释：复杂逻辑必须加注释，简洁代码可不加
- 函数命名：清晰表达意图，不要用缩写

---

## 项目待办

- [ ] 多Tab并行下载（提速）
- [ ] Windows适配测试
- [ ] Linux适配测试
- [ ] Obsidian笔记生成脚本完善
- [ ] 支持学位论文（硕士/博士）下载
- [ ] 导出BibTeX格式引用

---

有任何问题？发 [Issue](https://github.com/chonpszhou/cnki-research-helper/issues) 或者直接提PR！

---

*本项目采用 [MIT License](LICENSE)，所有贡献者将永久保留署名权。*
