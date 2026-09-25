"""ComfyUI-H3-WushuBridge：MiniMax H3 武打语义逻辑翻译桥。

节点注册在 ``MiniMax H3/Wushu Bridge`` 分类下，详见 README。

关于"菜单里显示哪些节点"
------------------------
插件一共 11 个节点，但日常出片只用其中 5 个：
    语义逻辑桥 / 提示词体检 / 逻辑评分 / 武打编排 / 清空缓存
剩下 6 个是**一次性或诊断**工具（建数据集、采训练对、训桥、训评分头、
降级预览、token 段定位），平时用不到，全列出来会把要用的淹没。

所以默认只把常用的 5 个交给 ComfyUI。要动训练/诊断节点时，设环境变量后
重启 ComfyUI 即可全部显示::

    set WUSHU_BRIDGE_NODES=all        # Windows cmd
    $env:WUSHU_BRIDGE_NODES="all"     # PowerShell

取值 all / full / train / dev 都算全开；其它值（含默认 core）只留常用节点。

注意：过滤只影响**菜单里显不显示**。节点类、权重格式、数据集格式都没动，
老 workflow JSON 里已经存了这些节点的话照旧能加载运行
（ComfyUI 从工作流里按类名实例化，不依赖菜单列表）。
"""

import os

from .wushu_bridge.nodes import (
    NODE_CLASS_MAPPINGS as _ALL_CLASSES,
    NODE_DISPLAY_NAME_MAPPINGS as _ALL_NAMES,
    SETUP_ONLY_NODES,
)

__version__ = "0.1.0"
WEB_DIRECTORY = None

# 需要"全开"时取这些值之一；其余一律按常用节点过滤
_FULL_SETS = ("all", "full", "train", "dev")
_node_set = os.environ.get("WUSHU_BRIDGE_NODES", "core").strip().lower()

if _node_set in _FULL_SETS:
    NODE_CLASS_MAPPINGS = dict(_ALL_CLASSES)
    NODE_DISPLAY_NAME_MAPPINGS = dict(_ALL_NAMES)
else:
    NODE_CLASS_MAPPINGS = {k: v for k, v in _ALL_CLASSES.items() if k not in SETUP_ONLY_NODES}
    NODE_DISPLAY_NAME_MAPPINGS = {k: v for k, v in _ALL_NAMES.items() if k not in SETUP_ONLY_NODES}

# 全量表也导出去，方便测试/脚本按类名直接取（不受菜单过滤影响）
ALL_NODE_CLASS_MAPPINGS = dict(_ALL_CLASSES)
ALL_NODE_DISPLAY_NAME_MAPPINGS = dict(_ALL_NAMES)

__all__ = [
    "NODE_CLASS_MAPPINGS",
    "NODE_DISPLAY_NAME_MAPPINGS",
    "ALL_NODE_CLASS_MAPPINGS",
    "ALL_NODE_DISPLAY_NAME_MAPPINGS",
    "__version__",
]
