# 测试目录

用于保存测试记录、原始数据、视频索引和测试报告。

## 软件计算检查

```powershell
python -m unittest discover -s tests -p "test_*.py" -v
```

`test_layout_study.py` 检查质量加权、坐标旋转、重力投影、支撑区内外、非法输入与命令行导出。它验证示例计算程序，不是金属样机或载人试验合格证据。

建议使用以下命名格式：

```text
YYYY-MM-DD_Txx_测试名称_版本号
```

例如：

```text
2026-10-21_T03_门槛测试_V0.1
```
