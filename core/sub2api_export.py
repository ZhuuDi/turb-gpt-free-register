# -*- coding: utf-8 -*-
"""Codex OAuth 凭证自动导入 sub2api 账号池。

部署私有增强：凭证保存成功后，把 codex session JSON 推送到
sub2api 的 /api/v1/admin/accounts/import/codex-session（幂等，
update_existing=true），使 sub2api 账号池自动获得新号与续期后的 token。

- 认证使用 .env 的 SUB2API_API_KEY（x-api-key 权限管理密钥，
  需含「创建账户 accounts.create」权限并绑定目标分组）。
- 目标分组由 SUB2API_IMPORT_GROUP_ID 指定。
- 全程 fire-and-forget 后台线程：失败只记日志，绝不影响注册/OAuth 主流程。
"""
import json
import logging
import threading
import urllib.request
import urllib.error

logger = logging.getLogger(__name__)


def export_codex_session_async(email: str, storage: dict) -> None:
    """调度后台导入线程（fire-and-forget）。"""
    try:
        threading.Thread(
            target=_export_sync,
            args=(email, storage),
            daemon=True,
            name=f"sub2api-export-{email}",
        ).start()
    except Exception:
        logger.warning("[Sub2Export] %s 导入线程调度失败", email, exc_info=True)


def _export_sync(email: str, storage: dict) -> None:
    try:
        from config.env_loader import load_env
        load_env(override=False)
        from config import sub2api as cfg

        if not bool(getattr(cfg, "SUB2API_IMPORT_OAUTH", True)):
            return
        base = str(getattr(cfg, "SUB2API_API_BASE", "") or "").strip()
        key = str(getattr(cfg, "SUB2API_API_KEY", "") or "").strip()
        if not base or not key:
            logger.info("[Sub2Export] %s 未配置 SUB2API_API_BASE/KEY，跳过导入", email)
            return
        try:
            group_id = int(getattr(cfg, "SUB2API_IMPORT_GROUP_ID", 0) or 0)
        except (TypeError, ValueError):
            group_id = 0

        session = {
            "OPENAI_API_KEY": None,
            "tokens": {
                "id_token": storage.get("id_token"),
                "access_token": storage.get("access_token"),
                "refresh_token": storage.get("refresh_token"),
                "account_id": storage.get("account_id"),
            },
            "last_refresh": storage.get("last_refresh") or "",
        }
        if not session["tokens"].get("access_token"):
            logger.info("[Sub2Export] %s 凭证无 access_token，跳过", email)
            return

        body = {"contents": [json.dumps(session, ensure_ascii=False)], "update_existing": True}
        if group_id > 0:
            body["group_ids"] = [group_id]

        req = urllib.request.Request(
            base.rstrip("/") + "/api/v1/admin/accounts/import/codex-session",
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json", "x-api-key": key},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as r:
            resp = json.loads(r.read().decode("utf-8"))
        inner = resp.get("data") if isinstance(resp.get("data"), dict) else resp
        logger.info(
            "[Sub2Export] %s 导入完成：created=%s updated=%s failed=%s",
            email,
            inner.get("created"), inner.get("updated"), inner.get("failed"),
        )
    except urllib.error.HTTPError as e:
        logger.warning("[Sub2Export] %s 导入失败 HTTP %s：%s", email, e.code, e.read(200).decode(errors="replace"))
    except Exception as exc:
        logger.warning("[Sub2Export] %s 导入异常：%s: %s", email, type(exc).__name__, str(exc)[:160])
