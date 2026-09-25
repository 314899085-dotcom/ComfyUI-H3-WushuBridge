"""ComfyUI-H3-WushuBridge：MiniMax H3 武打语义逻辑翻译桥。

节点注册在 ``MiniMax H3/Wushu Bridge`` 分类下，详见 README。

主线上只有一个节点
------------------
**H3 武打语义优化（判断→优化→输出）** —— 接在 CLIPTextEncode 之后，
它自己走完：Laya 判断武打逻辑 → 不达标就用残差桥优化 conditioning
（必要时叫小模型重写提示词）→ 复评合格后输出。

插件里其它节点（单独的桥 / JEV 评分 / h3lint 体检 / 武打编排 / Laya 裁判分体版 /
训练与诊断工具）默认**不出现在菜单里**——不是不能用，是日常出片用不到，
全列出来只会把主线节点淹掉。

要全部显示::

    set WUSHU_BRIDGE_NODES=all        # Windows cmd
    $env:WUSHU_BRIDGE_NODES="all"     # PowerShell

只有 ``all`` / ``full`` / ``dev`` / ``core-all`` 这几个值算"全开"，
其它值（含不设）都只留 ``CORE_NODES`` 里的常用节点。

注意：过滤只影响**菜单里显不显示**。节点类、权重格式、数据集格式都没动，
老 workflow JSON 里已经存了这些节点的话照旧能加载运行
（ComfyUI 从工作流里按类名实例化，不依赖菜单列表）。
"""

import os

from .wushu_bridge.nodes import (
    NODE_CLASS_MAPPINGS as _ALL_CLASSES,
    NODE_DISPLAY_NAME_MAPPINGS as _ALL_NAMES,
    CORE_NODES,
)

__version__ = "0.2.0"
WEB_DIRECTORY = None

_full = os.environ.get("WUSHU_BRIDGE_NODES", "").strip().lower() in ("all", "full", "dev", "core-all")

if _full:
    NODE_CLASS_MAPPINGS = dict(_ALL_CLASSES)
    NODE_DISPLAY_NAME_MAPPINGS = dict(_ALL_NAMES)
else:
    NODE_CLASS_MAPPINGS = {k: v for k, v in _ALL_CLASSES.items() if k in CORE_NODES}
    NODE_DISPLAY_NAME_MAPPINGS = {k: v for k, v in _ALL_NAMES.items() if k in CORE_NODES}

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
