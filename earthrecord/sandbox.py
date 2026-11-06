"""Per-question Docker sandbox.

Each run gets a fresh container with no network, the question's view of the record read-only at /data, a writable
/work volume, a read-only root file system, no capabilities, 4 CPUs and 24 GB of memory. The host name and resolver
settings are fixed so that nothing about the host is visible inside the container.
"""

from pathlib import Path

import yaml

IMAGE = "earthrecord-sandbox:1.0"
CPUS = 4
MEMORY = "24g"


def compose_file(view_dir: Path, out_path: Path, image: str = IMAGE) -> str:
    """Write the Docker Compose file of one question view and return its path."""
    service = {
        "image": image,
        "x-local": True,
        "init": True,
        "network_mode": "none",
        "user": "1500:1500",
        "working_dir": "/work",
        "read_only": True,
        "tmpfs": ["/tmp:size=4g,mode=1777", "/var/tmp:size=1g,mode=1777,exec"],
        "cap_drop": ["ALL"],
        "security_opt": ["no-new-privileges:true"],
        "cpus": CPUS,
        "mem_limit": MEMORY,
        "pids_limit": 1024,
        "environment": {"HOME": "/work"},
        "hostname": "sandbox",
        "dns": ["127.0.0.1"],
        "dns_search": ["."],
        "volumes": [
            {"type": "bind", "source": str(Path(view_dir).resolve()), "target": "/data", "read_only": True},
            {"type": "volume", "source": "work", "target": "/work"},
        ],
    }
    doc = {"services": {"default": service}, "volumes": {"work": {}}}
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(yaml.safe_dump(doc, sort_keys=False))
    return str(out_path)
