import pytest
import subprocess
from pathlib import Path

from src.difftool import DiffTool, ModificationStatus

SAMPLE_FILE_CONTENT = """This is a sample file :)"""


class TestDiff:
    @pytest.fixture
    def tmpdirs(self, tmp_path: Path) -> tuple[Path, Path]:
        """
            Initialize an empty git repository in desired_dir before running tests.
            Cleanup both directories after test finished.
        """

        desired_dir = tmp_path / "desired"
        desired_dir.mkdir()
        self.run_git(["init"], desired_dir)

        deployed_dir = tmp_path / "deployed"
        deployed_dir.mkdir()

        return (desired_dir, deployed_dir)

    @staticmethod
    def list_dir(dir_path: Path) -> None:
        print(subprocess.run(["ls", "-la", dir_path], capture_output=True, text=True).stdout)

    def run_git(self, cmd: list[str], cwd: Path) -> subprocess.CompletedProcess:
        return subprocess.run(["git"] + cmd, cwd=cwd, check=True, capture_output=True, text=True)

    def write_file(self, file_path: Path, content: str) -> None:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content)

    def git_add_file(self, filepath: Path, content: str, cwd: Path) -> None:
        self.write_file(filepath, content)
        self.run_git(["add", str(filepath)], cwd)

    def test_add_service(self, tmpdirs: tuple[Path, Path]):
        desired_dir, deployed_dir = tmpdirs
        # add first service
        self.git_add_file(desired_dir / "service1" / "service1-kube.yaml", SAMPLE_FILE_CONTENT, desired_dir)
        self.git_add_file(desired_dir / "service1" / "service1-kube.kube", SAMPLE_FILE_CONTENT, desired_dir)

        diff = DiffTool(desired_dir, deployed_dir)
        changes = diff.list_deployment_differences()

        assert len(changes) == 1
        assert changes[0].path.name == "service1"
        assert changes[0].service_name == "service1-kube.service"

        # add more services
        self.git_add_file(desired_dir / "service2" / "service2-kube.yaml", SAMPLE_FILE_CONTENT, desired_dir)
        self.git_add_file(desired_dir / "service2" / "service2-kube.kube", SAMPLE_FILE_CONTENT, desired_dir)
        self.git_add_file(desired_dir / "service3" / "service3-kube.yaml", SAMPLE_FILE_CONTENT, desired_dir)
        self.git_add_file(desired_dir / "service3" / "service3-kube.kube", SAMPLE_FILE_CONTENT, desired_dir)

        changes = diff.list_deployment_differences()

        assert len(changes) == 3
        expected_dirs = ["service1", "service2", "service3"]
        expected_services = ["service1-kube.service", "service2-kube.service", "service3-kube.service"]
        for change in changes:
            # make sure each dir and service is present exactly once
            assert change.path.name in expected_dirs
            expected_dirs.remove(change.path.name)
            assert change.service_name in expected_services
            expected_services.remove(change.service_name)
            assert change.status == ModificationStatus.ADDED

    def test_vodes(self, tmpdirs: tuple[Path, Path]):
        desired_dir, deployed_dir = tmpdirs
        self.list_dir(desired_dir)
