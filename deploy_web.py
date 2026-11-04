# -*- coding: utf-8 -*-
"""公网部署入口(部署私有文件,不属于上游代码)。

作用:
1. 在 create_app 外层追加会话持久化策略:登录 Cookie 一律按持久会话处理,
   浏览器关闭不掉登录;每次响应滑动续期,服务器重启也不掉登录
   (签名密钥来自 .env 的 WEBUI_SESSION_SECRET,稳定不变);
2. 会话有效期可通过 .env 的 WEBUI_SESSION_DAYS 调整(默认 30 天,上限 365)。

复用上游 web.py 的全部启动逻辑(参数解析/单实例锁/日志),只替换 create_app。
与上游解耦:本文件为新增文件,不修改上游任何代码;上游更新后只要
webui.app.create_app 与 web.main 的入口约定不变,本文件无需改动。
"""
from __future__ import annotations

import os
from datetime import timedelta

import webui.app as _webui_app
from flask import session

_original_create_app = _webui_app.create_app


def _create_app_with_persistent_session(auth_code=None):
    app = _original_create_app(auth_code)
    try:
        days = int(os.getenv("WEBUI_SESSION_DAYS", "30") or "30")
    except ValueError:
        days = 30
    days = max(1, min(days, 365))
    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=days)
    # 每次响应都续期 Cookie(滑动过期):只要两次访问间隔不超过有效期,就永不掉登录
    app.config["SESSION_REFRESH_EACH_REQUEST"] = True

    @app.after_request
    def _deploy_session_keep_alive(response):
        # 必须用 after_request:上游登录视图会在请求阶段把 permanent 覆写回
        # "记住我"勾选值(False),而 Flask 是在 after_request 之后才序列化
        # Cookie,在这里强制改回持久会话即可稳定生效。
        session.permanent = True
        return response

    return app


# 先替换模块属性,再让 web.py 在导入时取到补丁后的 create_app
_webui_app.create_app = _create_app_with_persistent_session

from web import main  # noqa: E402  (必须在补丁之后再导入,顺序不能换)

if __name__ == "__main__":
    main()
