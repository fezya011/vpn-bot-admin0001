import time
from datetime import UTC, datetime

import docker

from app.config import Settings
from app.system import uptime


class Docker:

    def __init__(self, s: Settings):
        self._s = s
        self.client = docker.DockerClient(base_url="unix://var/run/docker.sock", timeout=120)

    def can_restart(self, name: str) -> bool:
        return name != self._s.self_container and name not in self._s.protected_containers

    def list_containers(self) -> list[dict]:
        out = [
            {
                "id": c.short_id,
                "name": c.name,
                "status": c.status,
                "unhealthy": "unhealthy" in (c.attrs.get("Status") or ""),
            }
            for c in self.client.containers.list(all=True)
        ]
        return sorted(out, key=lambda x: x["name"])

    def basic(self, cid: str) -> dict:
        c = self.client.containers.get(cid)
        return {"id": c.short_id, "name": c.name, "status": c.status}

    def detail(self, cid: str) -> dict:
        c = self.client.containers.get(cid)
        st = c.attrs["State"]
        info = {
            "id": c.short_id,
            "name": c.name,
            "status": c.status,
            "health": (st.get("Health") or {}).get("Status"),
            "restarts": c.attrs.get("RestartCount", 0),
            "exit_code": st.get("ExitCode"),
            "image": c.attrs["Config"]["Image"],
            "uptime": None,
            "cpu": None,
            "mem": None,
            "mem_limit": None,
        }
        if c.status == "running":
            started = datetime.strptime(st["StartedAt"][:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=UTC)
            info["uptime"] = uptime(time.time() - started.timestamp())
            s = c.stats(stream=False)
            cpu_s, pre = s.get("cpu_stats", {}), s.get("precpu_stats", {})
            cpu_d = cpu_s.get("cpu_usage", {}).get("total_usage", 0) - pre.get("cpu_usage", {}).get("total_usage", 0)
            sys_d = cpu_s.get("system_cpu_usage", 0) - pre.get("system_cpu_usage", 0)
            ncpu = cpu_s.get("online_cpus") or 1
            info["cpu"] = cpu_d / sys_d * ncpu * 100 if sys_d > 0 and cpu_d >= 0 else 0.0
            ms = s.get("memory_stats", {})
            cache = ms.get("stats", {}).get("inactive_file", ms.get("stats", {}).get("total_inactive_file", 0))
            info["mem"] = max(ms.get("usage", 0) - cache, 0)
            info["mem_limit"] = ms.get("limit")
        return info

    def logs(self, cid: str, tail: int = 40) -> str:
        return self.client.containers.get(cid).logs(tail=tail).decode(errors="replace")

    def restart(self, cid: str) -> None:
        self.client.containers.get(cid).restart(timeout=20)

    def reboot_host(self) -> None:
        self.client.containers.run(
            "alpine",
            ["nsenter", "-t", "1", "-m", "-u", "-n", "-i", "reboot"],
            privileged=True,
            pid_mode="host",
            detach=True,
            auto_remove=True,
        )
