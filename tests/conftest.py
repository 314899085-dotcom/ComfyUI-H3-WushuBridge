# -*- coding: utf-8 -*-
"""tests/conftest.py — pytest 引导。

两个作用：

1. 把仓库根目录放进 ``sys.path``，这样 ``import wushu_bridge.lint`` 在任何 cwd 下都能用。
2. 挡掉 pytest 对**仓库根 __init__.py** 的导入尝试。

第 2 点的原因：ComfyUI 自定义节点仓库根目录有自己的 ``__init__.py``（插件入口，内容为
``from .wushu_bridge.nodes import NODE_CLASS_MAPPINGS, ...``）。pytest 会把根目录当成
Package 节点，并以 ``"__init__"`` 这个名字去 import 它，于是报
``ImportError: attempted relative import with no known parent package``，
整个测试会话在 setup 阶段全红。

这里在 ``sys.modules`` 里预先放一个空壳模块挡掉那次导入：单元测试本来也不该去跑
ComfyUI 插件入口（那需要 ComfyUI 运行时）。**不要删仓库根的 __init__.py**，它是插件入口。
"""

from __future__ import annotations

import pathlib
import sys
import types

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

if "__init__" not in sys.modules:
    sys.modules["__init__"] = types.ModuleType("__init__")
