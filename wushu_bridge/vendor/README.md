# vendor/ —— 内嵌的第三方包

## laya 0.3.5

本目录下的 `laya/` 是 **[Laya](https://github.com/NandhaKishorM/laya)**（作者
Convai Innovations）的 PyPI 发行版 `laya==0.3.5` 的**原样拷贝**，未做任何修改。

### 为什么要内嵌而不是 `pip install`

* 它是**纯 Python、8 个文件、76KB**，依赖只有 `numpy / torch / safetensors /
  transformers / huggingface_hub` —— 这些 ComfyUI 环境本来就全有；
* 装插件时**零安装步骤**（不用 pip、不用重启后装依赖、不会和 ComfyUI 的依赖打架）；
* 版本锁死，不会因为用户环境里 `pip install -U laya` 而换行为。

想改用 pip 装的那份：设环境变量 `WUSHU_LAYA_USE_PIP=1`。

### 许可证与署名

* 上游：[github.com/NandhaKishorM/laya](https://github.com/NandhaKishorM/laya)
* 许可证：**Apache-2.0**（完整文本见同目录 `laya/LICENSE`）
* 版权：Copyright Convai Innovations
* 本仓库对其的使用方式：**原样内嵌调用，未修改源码**；模型权重不在此目录分发，
  由用户在首次使用时自行下载或从本地缓存装配（见 `tools/setup_laya.py`）。

Apache-2.0 要求保留版权与许可声明、并说明是否修改 —— 以上即是。

### 注意：这里没有 `__init__.py`

本目录**故意不建** `__init__.py`：它只作为搜索路径加进 `sys.path`
（见 `wushu_bridge/laya_runtime.py` 的 `_import_laya()`），这样 `import laya`
只解析到一份模块实例。一旦这里也变成包，`laya` 与 `wushu_bridge.vendor.laya`
就会各自加载一遍，出现两份互不相干的模块状态。
