import logging
import shutil
import subprocess
import time
from pathlib import Path
from typing import Callable, Generator, TypeVar

import pytest

from src.podman_cd import PodmanCD
from src.systemctl import Systemctl

logging.basicConfig(level=logging.DEBUG)

TEST_CONTAINER_IMAGE = "localhost/alpine:6"
ALT_TEST_CONTAINER_IMAGE = "localhost/alpine:7"


def kube_yaml_content(name: str, *, image_name: str = TEST_CONTAINER_IMAGE) -> str:
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
        image: {image_name}
        command: ["sleep", "infinity"]
"""


def kube_file_content(name: str) -> str:
    return f"""[Kube]
Yaml={name}.yaml

[Install]
WantedBy=default.target
"""


type ServiceFactory = Callable[[Path, str], None]


class Error(Exception):
    def __init__(self, msg: str) -> None:
        self.msg = msg

    def __str__(self) -> str:
        return self.msg


_T = TypeVar("_T")


def run_subprocess(cmd: list[str]) -> tuple[str, int]:
    ret = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return (ret.stdout.strip(), ret.returncode)


def wait(func: Callable[[], _T | None], *, timeout: int = 5, err_msg: str | None = None) -> _T:
    """
        Repeatedly call func until it returns a truthy value or timeout is reached.

        @param func: Function to call
        @param timeout: Number of seconds to wait (default is 5 seconds)

        @raises Error: If timeout is reached

    """

    for _ in range(timeout * 5):
        val = func()
        if val:
            return val
        time.sleep(0.2)

    raise Error(err_msg or "Time out waiting for predicate to become true")


def wait_service_active(name: str, systemctl: Systemctl, *, timeout: int = 5) -> None:
    """
        Wait until the given service is active

        @param systemctl: Systemctl instance to use
        @param name: Name of the service
        @param timeout: Number of seconds to wait (default is 5 seconds)

        @raises Error: If timeout is reached
    """

    if not name.endswith(".service"):
        name += ".service"

    wait(lambda: systemctl.is_active(name), timeout=timeout,
         err_msg=f"Service {name} did not become active")


def wait_container_running(name: str, *, timeout: int = 5) -> None:
    def _check_podman_ps():
        out, _ = run_subprocess(["podman", "ps", "--format", "{{.Names}}"])

        return name in out.splitlines()

    wait(_check_podman_ps, err_msg=f"Container {name} did not start running", timeout=timeout)


def wait_container_doesnt_exist(name: str, *, timeout: int = 5) -> None:
    def _check_podman_ps():
        out, _ = run_subprocess(["podman", "ps", "-a", "--format", "{{.Names}}"])

        return name not in out.splitlines()

    wait(_check_podman_ps, err_msg=f"Container {name} is still present!", timeout=timeout)


def check_container_version(name: str, expected_ver: str) -> None:
    ver, _ = run_subprocess(["podman", "inspect", name, "--format", "{{.ImageName}}"])
    ver = ver.split(":")[-1]
    if ver == expected_ver:
        return

    raise Error(f"Container version did not match expected version. Expected: {expected_ver}, got: {ver}")


@pytest.fixture(scope="session", autouse=True)
def prepare_test_image():
    run_subprocess(["podman", "pull", "docker.io/library/alpine:latest"])
    run_subprocess(["podman", "tag", "docker.io/library/alpine:latest", TEST_CONTAINER_IMAGE])
    run_subprocess(["podman", "tag", "docker.io/library/alpine:latest", ALT_TEST_CONTAINER_IMAGE])


class TestPodmanCD:
    deployed_dir: Path = Path("~/.config/containers/systemd/pytests_deployed").expanduser()
    systemctl: Systemctl = Systemctl(user_mode=True)

    @staticmethod
    def remove_service(basedir: Path, name: str) -> None:
        """
            Remove subdirectory of a given service from desired_dir
        """
        shutil.rmtree(basedir / name)

    @pytest.fixture(autouse=True)
    def setup_deployed_dir(self):
        """
            Fixture to initialize deploydir with cleanup

            Cleanup of each individual service is handled by the `add_service` fixture
        """

        self.deployed_dir.mkdir(parents=True, exist_ok=True)
        self.systemctl.daemon_reload()

        yield

        shutil.rmtree(self.deployed_dir)
        self.systemctl.daemon_reload()

    @pytest.fixture
    def desired_dir(self, tmp_path: Path) -> Path:
        """
            Setup desired_dir with clean git repository
        """

        subprocess.run(["git", "init", tmp_path], capture_output=True, text=True)

        return tmp_path

    @pytest.fixture
    def add_service(self) -> Generator[ServiceFactory, None, None]:
        """
            Fixture to automatically clean up created services
        """

        def _add_service(basedir: Path, name: str) -> None:
            # create service directory and files
            service_dir = basedir / name
            service_dir.mkdir()

            yaml_file = service_dir / f"{name}.yaml"
            yaml_file.write_text(kube_yaml_content(name))

            kube_file = service_dir / f"{name}.kube"
            kube_file.write_text(kube_file_content(name))

        yield _add_service

        # stop all leftover services in deployed_dir
        # name of the service is the same as directory name
        # TODO: this can probably be done async to reduce cleanup time
        for dirname in self.deployed_dir.iterdir():
            if dirname.is_dir():
                self.systemctl.stop(f"{dirname.name}.service")

    @staticmethod
    def modify_file(file: Path, new_conent: str):
        if not file.is_file():
            raise FileNotFoundError("modify_file only allows modifying existing files")

        file.write_text(new_conent)

    def test_add_remove_container(self, desired_dir: Path, add_service: ServiceFactory) -> None:
        podman_cd = PodmanCD(str(desired_dir), str(self.deployed_dir), user_mode=True)

        add_service(desired_dir, "fancy")
        podman_cd.run_update()

        wait_service_active("fancy.service", self.systemctl)
        wait_container_running("fancy-pod-fancy", timeout=10)

        # add two more
        add_service(desired_dir, "fancier")
        add_service(desired_dir, "fanciest")

        podman_cd.run_update()
        wait_container_running("fancier-pod-fancier", timeout=10)
        wait_container_running("fanciest-pod-fanciest", timeout=10)

        # remove fanciest container
        self.remove_service(desired_dir, "fanciest")

        podman_cd.run_update()

        wait_container_doesnt_exist("fanciest-pod-fanciest", timeout=20)

    def test_add_modify_container(self, desired_dir: Path, add_service: ServiceFactory) -> None:
        podman_cd = PodmanCD(str(desired_dir), str(self.deployed_dir), user_mode=True)

        container_name = "jellyfin-pod-jellyfin"
        add_service(desired_dir, "jellyfin")
        podman_cd.run_update()
        wait_service_active("jellyfin.service", self.systemctl)
        wait_container_running(container_name, timeout=10)
        check_container_version(container_name, "6")

        # Modify container image
        self.modify_file(desired_dir / "jellyfin" / "jellyfin.yaml",
                         kube_yaml_content("jellyfin", image_name=ALT_TEST_CONTAINER_IMAGE))
        podman_cd.run_update()
        wait_service_active("jellyfin.service", self.systemctl)
        wait_container_running(container_name, timeout=10)
        check_container_version(container_name, "7")
