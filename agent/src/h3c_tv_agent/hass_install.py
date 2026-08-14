"""Deploy bundled h3c_tv_child custom component into Home Assistant over SSH."""

from __future__ import annotations

import io
import json
import posixpath
import tarfile
import threading
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import paramiko

from .logging_setup import get_logger

log = get_logger("hass_install")

CARD_URL = "/h3c_tv_child/lovelace/h3c-tv-child-card.js?v=0.1.1"
CARD_RESOURCE_ID = "h3c_tv_child_card_resource"


@dataclass
class InstallStatus:
    status: str = "unknown"  # unknown|not_installed|installed|installing|ok|error
    message: str = ""
    version: str = ""
    at: str = ""

    def to_payload(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)


class HassChildInstaller:
    """Package local integration files and push them to HA via SSH/SFTP."""

    def __init__(
        self,
        *,
        package_dir: Path,
        host: str,
        port: int,
        username: str,
        password: str,
        remote_components: str,
        restart_ha: bool,
        on_status: Callable[[InstallStatus], None] | None = None,
    ) -> None:
        self.package_dir = package_dir
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.remote_components = remote_components.rstrip("/")
        self.restart_ha = restart_ha
        self.on_status = on_status
        self._lock = threading.Lock()
        self._status = InstallStatus()

    @property
    def status(self) -> InstallStatus:
        return self._status

    def _emit(self, status: str, message: str, version: str = "") -> None:
        self._status = InstallStatus(
            status=status,
            message=message,
            version=version or self._local_version(),
            at=datetime.now(timezone.utc).isoformat(),
        )
        log_fn = log.error if status == "error" else log.info
        log_fn(
            "hass child install status",
            status=status,
            message=message,
            version=self._status.version,
        )
        if self.on_status:
            self.on_status(self._status)

    def _local_version(self) -> str:
        manifest = self.package_dir / "manifest.json"
        if not manifest.is_file():
            return ""
        try:
            return str(json.loads(manifest.read_text(encoding="utf-8")).get("version", ""))
        except Exception:
            return ""

    def enabled(self) -> bool:
        return bool(self.host and self.username and self.package_dir.is_dir())

    def probe(self) -> InstallStatus:
        if not self.enabled():
            self._emit("unknown", "未配置 HA_SSH_* 或缺少集成包")
            return self._status
        try:
            with self._connect() as client:
                remote = f"{self.remote_components}/h3c_tv_child/manifest.json"
                cmd = f"test -f {remote} && cat {remote} || echo MISSING"
                _stdin, stdout, _stderr = client.exec_command(cmd, timeout=30)
                out = stdout.read().decode("utf-8", errors="replace").strip()
                if out == "MISSING" or not out:
                    self._emit("not_installed", "HA 上未安装儿童管理插件")
                else:
                    ver = ""
                    try:
                        ver = str(json.loads(out).get("version", ""))
                    except Exception:
                        ver = ""
                    self._emit("installed", "儿童管理插件已安装", version=ver)
        except Exception as err:
            self._emit("error", f"探测失败: {err}")
        return self._status

    def install_async(self) -> None:
        threading.Thread(target=self.install, name="hass-child-install", daemon=True).start()

    def install(self) -> InstallStatus:
        if not self._lock.acquire(blocking=False):
            self._emit("installing", "安装进行中，请稍候")
            return self._status
        try:
            return self._install_locked()
        finally:
            self._lock.release()

    def _install_locked(self) -> InstallStatus:
        if not self.enabled():
            self._emit("error", "未配置 HA SSH（HA_SSH_HOST/USER/PASSWORD）或集成包不存在")
            return self._status
        if not self.password:
            self._emit("error", "HA_SSH_PASSWORD 为空")
            return self._status

        version = self._local_version()
        self._emit("installing", "正在打包并上传儿童管理插件…", version=version)
        try:
            archive = self._build_tar()
            with self._connect() as client:
                sftp = client.open_sftp()
                try:
                    remote_tar = "/tmp/h3c_tv_child_install.tgz"
                    with sftp.file(remote_tar, "wb") as rf:
                        rf.write(archive)
                    remote_dir = f"{self.remote_components}/h3c_tv_child"
                    cmds = [
                        f"rm -rf {remote_dir}",
                        f"mkdir -p {self.remote_components}",
                        f"tar -xzf {remote_tar} -C {self.remote_components}",
                        f"rm -f {remote_tar}",
                        f"test -f {remote_dir}/manifest.json",
                    ]
                    for cmd in cmds:
                        self._exec(client, cmd)
                    self._ensure_lovelace_resource(client)
                finally:
                    sftp.close()

                if self.restart_ha:
                    self._emit(
                        "ok",
                        "已部署并注册 Lovelace 资源，正在重启 Home Assistant…完成后请确认集成「H3C TV Child (MQTT)」",
                        version=version,
                    )
                    # 先发状态再重启（MQTT 在 HA 上，重启会短暂断连）
                    time.sleep(0.5)
                    self._exec(client, "ha core restart", check=False)
                else:
                    self._emit(
                        "ok",
                        "已部署。请重启 Home Assistant 后添加/重载「H3C TV Child (MQTT)」",
                        version=version,
                    )
        except Exception as err:
            self._emit("error", f"安装失败: {err}", version=version)
        return self._status

    def _build_tar(self) -> bytes:
        skip_dirs = {"frontend", "__pycache__", ".git"}
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w:gz") as tar:
            for path in sorted(self.package_dir.rglob("*")):
                rel = path.relative_to(self.package_dir)
                if any(part in skip_dirs for part in rel.parts):
                    continue
                if path.is_dir():
                    continue
                arcname = posixpath.join("h3c_tv_child", rel.as_posix())
                tar.add(path, arcname=arcname)
        return buf.getvalue()

    def _connect(self) -> paramiko.SSHClient:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(
            hostname=self.host,
            port=self.port,
            username=self.username,
            password=self.password,
            timeout=20,
            allow_agent=False,
            look_for_keys=False,
        )
        return client

    def _exec(self, client: paramiko.SSHClient, cmd: str, *, check: bool = True) -> str:
        _stdin, stdout, stderr = client.exec_command(cmd, timeout=120)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        code = stdout.channel.recv_exit_status()
        if check and code != 0:
            raise RuntimeError(f"远程命令失败 ({code}): {cmd}\n{err or out}")
        return out

    def _ensure_lovelace_resource(self, client: paramiko.SSHClient) -> None:
        """Upsert Lovelace module resource using jq on HA host."""
        path = "/config/.storage/lovelace_resources"
        script = f"""
set -e
if [ ! -f {path} ]; then
  printf '%s\\n' '{{"version":1,"minor_version":1,"key":"lovelace_resources","data":{{"items":[]}}}}' > {path}
fi
cp {path} {path}.bak.h3c_child || true
tmp=/tmp/lovelace_resources.h3c.json
jq --arg url "{CARD_URL}" --arg id "{CARD_RESOURCE_ID}" '
  .data.items = ((.data.items // []) | map(select((.url // "") | test("h3c_tv_child|h3c_tv_control|h3c-tv-child") | not)))
  + [{{id:$id, url:$url, type:"module"}}]
' {path} > "$tmp"
mv "$tmp" {path}
"""
        self._exec(client, script)
