# FAQ

## 怎么运行测试？

在仓库根目录先安装测试依赖，再执行与 CI 相同的命令：

```sh
python -m pip install pytest stripe
python -m pytest
```

pytest 汇总里没有 `failed` 即表示测试通过。
