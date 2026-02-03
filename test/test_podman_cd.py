import shutil
from typing import Callable
import pytest
import subprocess
from pathlib import Path

from podman_cd import PodmanCD
from systemctl import Systemctl

def kube_yaml_content(name: str) -> str:
    return f"""apiVersion: apps/v1
kind: Deployment
metadata:
  name: {name}
spec:
  selector:
    matchLabels:
      app: {name}
  template:
    metadata:
      labels:
        app: {name}
    spec:
      containers:
      - name: {name}
        image: docker.io/library/alpine:latest
        command: ["sh"]
"""

def kube_file_content(name: str) -> str:
    return f"""[Kube]
Yaml={name}.yaml

[Install]
WantedBy=default.target
"""

type ServiceFactory = Callable[[Path, str], None]


class TestPodmanCD:
    deployed_dir: Path = Path("~/.config/containers/systemd/pytests_deployed").expanduser()
    systemctl: Systemctl = Systemctl(user_mode=True)

    def check_service_active(self, name: str) -> bool:
        return self.systemctl.is_active(f"{name}.service")

    @pytest.fixture(autouse=True)
    def setup_deployed_dir(self):
        """
            Fixture to initialize deploydir with cleanup

            Cleanup of each individual service is handled by the `add_service` fixture
        """

        self.deployed_dir.mkdir(parents=True, exist_ok=True)
        self.systemctl.daemon_reload()

        yield

        self.deployed_dir.rmdir()
        self.systemctl.daemon_reload()

    @pytest.fixture
    def desired_dir(self, tmp_path: Path) -> Path:
        """
            Setup desired_dir with clean git repository
        """

        subprocess.run(["git", "init", tmp_path], capture_output=True, text=True)

        return tmp_path

    @pytest.fixture
    def add_service(self, request) -> ServiceFactory:
        """
            Fixture to automatically clean up created services
        """

        def _add_service(dir: Path, name: str) -> None:
            # create service directory and files
            service_dir = dir / name
            service_dir.mkdir()

            yaml_file = service_dir / f"{name}.yaml"
            yaml_file.write_text(kube_yaml_content(name))

            kube_file = service_dir / f"{name}.kube"
            kube_file.write_text(kube_file_content(name))

            # register a cleanup function
            def _service_cleanup():
                self.systemctl.stop(f"{name}.service")
                shutil.rmtree(service_dir)

            request.addfinalizer(_service_cleanup)

        return _add_service

    def test_add_container(self, desired_dir: Path, add_service: ServiceFactory) -> None:
        add_service(desired_dir, "fancy-service")
        add_service(desired_dir, "second-service")

        podman_cd = PodmanCD(str(desired_dir), str(self.deployed_dir), True)
        podman_cd.run_update()
