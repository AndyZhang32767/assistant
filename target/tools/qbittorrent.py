#==TOOL=======================================================================
#.       name: qbittorrent
#.       access: pr
#.       title: qBittorrent 下载
#.       description: 通过 qBittorrent Web API 管理 BT 下载，完成后自动打包上传
#.       version: 1.0
#.       sidebar: qbittorrent=qBittorrent下载
#==END TOOL===================================================================

#=======================================================================================
#.       tools/qbittorrent.py — qBittorrent 下载集成
#.       通过 qBittorrent Web API 管理 BT 下载任务：
#.         - 添加磁力链接 / .torrent 种子文件
#.         - 记录任务来源 chat_id，下载完成后自动通知
#.         - 后台轮询下载进度
#.
#.       依赖: pip install qbittorrent-api
#.       qBittorrent 需开启 Web UI（设置 → Web UI → 启用）
#=======================================================================================

import json
import logging
import os
import shutil
import tempfile
import time
import zipfile

import qbittorrentapi

logger = logging.getLogger(__name__)

# 抑制第三方库的 HTTP 请求日志，只在有新任务/下载完成时输出
logging.getLogger("qbittorrentapi").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)

#==CONFIG=======================================================================
#.       qBittorrent Web UI 连接配置（可通过 TUI Tools 菜单编辑）
#==CONFIG=======================================================================
QB_HOST = "127.0.0.1"     # qbittorrent地址
QB_PORT = "8080"          # qbittorrent端口
QB_USER = "AndyZhang123"  # qbittorrent用户名
QB_PASS = "Zba123456"     # qbittorrent密码
QB_POLL_INTERVAL = 30     # 轮询间隔
QB_MAX_UPLOAD_MB = 1024   # 最大上传大小
QB_SPLIT_MB = 48          # 分包大小
#==END CONFIG===================================================================

# -- 任务记录持久化路径
_TASKS_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "qb_tasks.json",
)

# -- 运行时任务记录: {torrent_hash: {"name": str, "chat_id": int, "added": float}}
_tracking: dict[str, dict] = {}


#=============================================================
#.       _get_client() — qbittorrentapi 客户端懒加载单例
#=============================================================
def _get_client() -> qbittorrentapi.Client:
    return qbittorrentapi.Client(
        host=f"http://{QB_HOST}:{QB_PORT}",
        username=QB_USER,
        password=QB_PASS,
    )


#=============================================================
#.       _load_tracking / _save_tracking — 任务记录持久化
#=============================================================
def _load_tracking():
    global _tracking
    if os.path.exists(_TASKS_FILE):
        try:
            with open(_TASKS_FILE) as f:
                _tracking = json.load(f)
        except Exception:
            _tracking = {}


def _save_tracking():
    os.makedirs(os.path.dirname(_TASKS_FILE), exist_ok=True)
    with open(_TASKS_FILE, "w") as f:
        json.dump(_tracking, f, ensure_ascii=False, indent=2)


#=============================================================
#.       _track — 记录任务，等待轮询
#=============================================================
def _track(h: str, name: str, chat_id: int, immediate: bool = False):
    _load_tracking()
    _tracking[h] = {"name": name, "chat_id": chat_id, "added": time.time(), "immediate": immediate}
    _save_tracking()
    if immediate:
        logger.info(f"[qb] 已存在完成文件，直接打包: {name} (hash={h[:8]}...) chat={chat_id}")
    else:
        logger.info(f"[qb] 已跟踪: {name} (hash={h[:8]}...) chat={chat_id}")


#=============================================================
#.       _check_duplicate — 检查是否有同名已完成 torrent
#=============================================================
def _check_duplicate(c: qbittorrentapi.Client, name: str) -> bool:
    """检查 qbittorrent 中是否已有同名且已完成的 torrent。"""
    try:
        for t in c.torrents_info():
            if t.name == name and t.state_enum.is_complete:
                return True
    except Exception:
        pass
    return False


#=============================================================
#.       _find_newest — 添加后找到刚加入的 torrent hash
#=============================================================
def _find_newest(c: qbittorrentapi.Client) -> dict | None:
    for _ in range(5):
        time.sleep(1)
        try:
            torrents = c.torrents_info(sort="added_on", reverse=True, limit=1)
            if torrents:
                return {"hash": torrents[0].hash, "name": torrents[0].name}
        except Exception:
            pass
    return None


#=======================================================================================
#.       Gemini-facing 工具函数
#=======================================================================================

def add_qbittorrent_download(magnet: str = ""):
    """将磁力链接添加到 qbittorrent 下载队列。

    当用户发送磁力链接 (magnet:?xt=urn:btih:...) 并要求下载时调用。

    Args:
        magnet: 磁力链接 URL，格式为 magnet:?xt=urn:btih:<hash>。
    """
    if not magnet:
        return "未提供磁力链接。"

    c = _get_client()
    try:
        c.auth_log_in()
    except Exception as e:
        return f"连接 qbittorrent 失败: {e}"

    try:
        c.torrents_add(urls=magnet)
        t = _find_newest(c)
        if t:
            dup = _check_duplicate(c, t["name"])
            _track(t["hash"], t["name"], 0, immediate=dup)
            if dup:
                return f"已存在：{t['name']}，文件已完成，即将打包发送。"
            return f"已添加下载：{t['name']}，下载完成后我会通知你。"
    except Exception as e:
        return f"添加失败: {e}"

    return "已添加下载任务。"


def fetch_qb_status():
    """查看 qbittorrent 下载队列的当前状态。

    当用户询问"下载进度"、"BT 下怎么样了"、"有哪些任务在下载"时调用。
    """
    c = _get_client()
    try:
        c.auth_log_in()
        torrents = c.torrents_info()
    except Exception as e:
        return f"查询 qbittorrent 失败: {e}"

    if not torrents:
        return "当前没有下载任务。"

    lines = ["📥 当前下载任务："]
    for t in torrents:
        emoji = {"downloading": "⬇️", "uploading": "", "stalledDL": "⏸️", "queuedDL": "⏳",
                 "pausedDL": "⏸️", "forcedUP": "", "stalledUP": ""}.get(t.state, "❓")
        prog = round(t.progress * 100, 1)
        size = _fmt_size(t.size)
        lines.append(f"  {emoji} [{prog}%] {t.name}  ({size})")
    return "\n".join(lines)


#=======================================================================================
#.       Handler-facing 函数（由 bot/handlers.py 调用，有 chat_id 上下文）
#=======================================================================================

def add_qbittorrent_magnet_handler(magnet: str, chat_id: int) -> str:
    """添加磁力链接（handler 调用，带 chat_id 用于完成通知）。"""
    if not magnet:
        return "未提供磁力链接。"

    c = _get_client()
    try:
        c.auth_log_in()
    except Exception as e:
        return f"连接 qbittorrent 失败: {e}"

    try:
        c.torrents_add(urls=magnet)
        t = _find_newest(c)
        if t:
            dup = _check_duplicate(c, t["name"])
            _track(t["hash"], t["name"], chat_id, immediate=dup)
            if dup:
                return f"已存在：{t['name']}，文件已完成，即将打包发送。"
            return f"已添加下载：{t['name']}，完成后我会通知你。"
    except Exception as e:
        return f"添加失败: {e}"

    return "已添加下载任务。"


def add_qbittorrent_file_handler(file_bytes: bytes, filename: str, chat_id: int) -> str:
    """通过 .torrent 文件添加下载（handler 调用，带 chat_id 用于完成通知）。"""
    c = _get_client()
    try:
        c.auth_log_in()
    except Exception as e:
        return f"连接 qbittorrent 失败: {e}"

    try:
        c.torrents_add(torrent_files=file_bytes)
        t = _find_newest(c)
        if t:
            dup = _check_duplicate(c, t["name"])
            _track(t["hash"], t["name"], chat_id, immediate=dup)
            if dup:
                return f"已存在：{t['name']}，文件已完成，即将打包发送。"
            return f"已添加下载：{t['name']}，完成后我会通知你。"
    except Exception as e:
        return f"添加种子失败: {e}"

    return "已添加下载任务。"


#=======================================================================================
#.       后台轮询 callback（由 bot/main.py 的 job_queue 调用）
#=======================================================================================

async def _check_qbittorrent_torrents(context):
    """PTB job callback: 轮询 qbittorrent，完成后 zip 压缩并发送文件到 Telegram。"""
    _load_tracking()
    if not _tracking:
        return

    c = _get_client()
    try:
        c.auth_log_in()
        all_torrents = {t.hash: t for t in c.torrents_info()}
    except Exception as e:
        logger.error(f"[qb] 轮询查询失败: {e}")
        return

    completed_hashes = []
    for h, task in list(_tracking.items()):
        t = all_torrents.get(h)
        if t is None:
            continue
        # 判断是否需要处理：immediate 任务直接打包，正常任务等下载完成
        is_immediate = task.get("immediate", False)
        is_done = is_immediate or t.state_enum.is_complete or t.progress >= 1.0
        if not is_done:
            continue

        cid = task.get("chat_id", 0)
        name = task.get("name", "?")
        if is_immediate:
            logger.info(f"[qb] 重复文件直接打包: {name} → chat={cid}")
        else:
            logger.info(f"[qb] 下载完成: {name} → chat={cid}")

        if cid:
            sent_ok = False
            try:
                # 获取 torrent 内文件列表
                files = c.torrents_files(torrent_hash=h)
                file_paths = []
                for f in files:
                    full = os.path.join(t.save_path, f.name)
                    if os.path.isfile(full):
                        file_paths.append(full)

                if not file_paths:
                    await context.bot.send_message(
                        chat_id=cid,
                        text=f"✅ 下载完成：{t.name}\n但未找到下载文件（可能尚未移动完成）。",
                    )
                    sent_ok = True  # 无文件是终态，不再重试
                else:
                    # zip 压缩
                    zip_name = f"{t.name}.zip"
                    zip_path = os.path.join(tempfile.gettempdir(), zip_name)
                    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                        for fp in file_paths:
                            arcname = os.path.relpath(fp, t.save_path)
                            zf.write(fp, arcname)

                    zip_size = os.path.getsize(zip_path)
                    logger.info(f"[qb] 打包完成: {zip_name} ({_fmt_size(zip_size)})")

                    # 发送到 Telegram
                    max_total = int(QB_MAX_UPLOAD_MB) * 1024 * 1024
                    split_bytes = int(QB_SPLIT_MB) * 1024 * 1024

                    if zip_size > max_total:
                        # 超总上限 → 放弃上传，发文本通知
                        await context.bot.send_message(
                            chat_id=cid,
                            text=f"✅ 下载完成：{t.name}\n文件过大 ({_fmt_size(zip_size)})，超过上传上限 ({QB_MAX_UPLOAD_MB}MB)，请手动取件。\n路径: {t.save_path}",
                        )
                        sent_ok = True
                    elif zip_size <= split_bytes:
                        # 单卷 → 直接发送
                        with open(zip_path, "rb") as zf:
                            await context.bot.send_document(
                                chat_id=cid,
                                document=zf,
                                filename=zip_name,
                                caption=f"✅ 下载完成：{t.name}",
                            )
                        sent_ok = True
                    else:
                        # 分卷上传（.zip, .z01, .z02...）
                        total_parts = (zip_size + split_bytes - 1) // split_bytes
                        logger.info(f"[qb] 文件 {_fmt_size(zip_size)}，分 {total_parts} 卷上传")
                        with open(zip_path, "rb") as zf:
                            # 第一卷: name.zip
                            part_data = zf.read(split_bytes)
                            await context.bot.send_document(
                                chat_id=cid,
                                document=part_data,
                                filename=zip_name,
                                caption=f"📦 {t.name} [1/{total_parts}]",
                            )
                            # 后续卷: name.z01, name.z02...
                            base = zip_name[:-4]  # 去掉 .zip
                            for part in range(1, total_parts):
                                part_data = zf.read(split_bytes)
                                part_name = f"{base}.z{part:02d}"
                                await context.bot.send_document(
                                    chat_id=cid,
                                    document=part_data,
                                    filename=part_name,
                                    caption=f"📦 {t.name} [{part + 1}/{total_parts}]",
                                )
                        sent_ok = True

                    # 清理临时 zip
                    try:
                        os.remove(zip_path)
                    except Exception:
                        pass

            except Exception as e:
                logger.error(f"[qb] 处理完成文件失败 chat={cid}: {e}（保留任务，下轮重试）")
                # sent_ok 保持 False，不清理，下轮重试

            if sent_ok:
                completed_hashes.append(h)
        else:
            # 无 chat_id 的任务（来自 Gemini），直接清理
            completed_hashes.append(h)

    for h in completed_hashes:
        _tracking.pop(h, None)

    if completed_hashes:
        _save_tracking()
        logger.info(f"[qb] 本轮清理 {len(completed_hashes)} 个已完成任务")


#=============================================================
#.       _fmt_size — 文件大小格式化
#=============================================================
def _fmt_size(b: int) -> str:
    for u in ("B", "KB", "MB", "GB"):
        if b < 1024:
            return f"{b:.1f} {u}"
        b /= 1024
    return f"{b:.1f} TB"
