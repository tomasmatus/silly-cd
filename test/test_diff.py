import shutil
import pytest
import subprocess
from pathlib import Path

from difftool import DeploymentStatus, DiffTool, ModificationStatus

SAMPLE_FILE_CONTENT = """This is a sample file :)"""
DIFFERENT_FILE_CONTENT = """This file has different content :o"""


class TestDiff:
    @pytest.fixture
    def tmpdirs(self, tmp_path: Path) -> tuple[Path, Path]:
        """
            Initialize empty directories. Cleanup both directories after test finished.
        """

        desired_dir = tmp_path / "desired"
        desired_dir.mkdir()

        deployed_dir = tmp_path / "deployed"
        deployed_dir.mkdir()

        return (desired_dir, deployed_dir)

    @staticmethod
    def list_dir(dir_path: Path) -> None:
        print(subprocess.run(["ls", "-la", dir_path], capture_output=True, text=True).stdout)

    @staticmethod
    def write_file(file_path: Path, content: str) -> None:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content)

    @staticmethod
    def delete_file(file_path: Path) -> None:
        file_path.unlink()

    def add_service(self, dir: Path, service_name: str) -> None:
        service_dir = dir / service_name
        service_dir.mkdir(parents=True, exist_ok=True)
        self.write_file(service_dir  / f"{service_name}-kube.yaml", SAMPLE_FILE_CONTENT)
        self.write_file(service_dir  / f"{service_name}-kube.kube", SAMPLE_FILE_CONTENT)

    @staticmethod
    def delete_service(dir: Path, service_name: str) -> None:
        shutil.rmtree(dir / service_name)

    @staticmethod
    def commit_and_assert_zero(changes: list[DeploymentStatus], diff: DiffTool) -> None:
        diff.commit_changes(changes)
        changes = diff.list_deployment_differences()
        assert len(changes) == 0

    def test_add_service(self, tmpdirs: tuple[Path, Path]) -> None:
        desired_dir, deployed_dir = tmpdirs
        # add first service
        self.add_service(desired_dir, "service1")

        diff = DiffTool(desired_dir, deployed_dir)
        changes = diff.list_deployment_differences()

        assert len(changes) == 1
        assert changes[0].path.name == "service1"
        assert changes[0].service_name == "service1-kube.service"

        # add more services
        self.add_service(desired_dir, "service2")
        self.add_service(desired_dir, "service3")

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

        self.commit_and_assert_zero(changes, diff)

    def test_modify_service(self, tmpdirs: tuple[Path, Path]) -> None:
        desired_dir, deployed_dir = tmpdirs
        diff = DiffTool(desired_dir, deployed_dir)

        self.add_service(desired_dir, "service1")
        self.add_service(desired_dir, "service2")

        changes = diff.list_deployment_differences()
        assert len(changes) == 2

        self.commit_and_assert_zero(changes, diff)

        # modify service1-kube.yaml
        self.write_file(desired_dir / "service2" / "service2-kube.yaml", DIFFERENT_FILE_CONTENT)
        changes = diff.list_deployment_differences()
        assert len(changes) == 1
        assert changes[0].path.name == "service2"

        self.commit_and_assert_zero(changes, diff)

        # add a new file to service1
        self.write_file(desired_dir / "service1" / "service1-configmap.yaml", SAMPLE_FILE_CONTENT)
        changes = diff.list_deployment_differences()
        assert len(changes) == 1
        assert changes[0].path.name == "service1"

        # do multiple modifications
        self.write_file(desired_dir / "service1" / "service1-kube.kube", DIFFERENT_FILE_CONTENT)
        self.write_file(desired_dir / "service1" / "service1-secrets.yaml", SAMPLE_FILE_CONTENT)
        self.write_file(desired_dir / "service2" / "service2-configmap-asd.yaml", SAMPLE_FILE_CONTENT)
        self.write_file(desired_dir / "service2" / "service2-configmap-qwe.yaml", SAMPLE_FILE_CONTENT)

        changes = diff.list_deployment_differences()
        assert len(changes) == 2

        self.commit_and_assert_zero(changes, diff)

        # delete a file
        self.delete_file(desired_dir / "service2" / "service2-configmap-asd.yaml")
        changes = diff.list_deployment_differences()
        assert len(changes) == 1

        self.commit_and_assert_zero(changes, diff)

    def test_delete_service(self, tmpdirs: tuple[Path, Path]) -> None:
        desired_dir, deployed_dir = tmpdirs
        diff = DiffTool(desired_dir, deployed_dir)

        self.add_service(desired_dir, "service1")
        self.add_service(desired_dir, "service2")
        changes = diff.list_deployment_differences()
        assert len(changes) == 2
        self.commit_and_assert_zero(changes, diff)

        # delete a service
        self.delete_service(desired_dir, "service1")

        changes = diff.list_deployment_differences()
        assert len(changes) == 1
        self.commit_and_assert_zero(changes, diff)

        # add it back
        self.add_service(desired_dir, "service1")
        changes = diff.list_deployment_differences()
        assert len(changes) == 1
        self.commit_and_assert_zero(changes, diff)

        # add more
        self.add_service(desired_dir, "service3")
        self.add_service(desired_dir, "service4")
        changes = diff.list_deployment_differences()
        assert len(changes) == 2
        self.commit_and_assert_zero(changes, diff)

        # add and delete at the same time
        self.add_service(desired_dir, "service5")
        self.delete_service(desired_dir, "service2")
        self.delete_service(desired_dir, "service3")
        changes = diff.list_deployment_differences()
        assert len(changes) == 3
        self.commit_and_assert_zero(changes, diff)

        # add back
        self.add_service(desired_dir, "service2")
        self.add_service(desired_dir, "service3")
        changes = diff.list_deployment_differences()
        assert len(changes) == 2
        self.commit_and_assert_zero(changes, diff)

        # modify and delete services at the same time
        self.write_file(desired_dir / "service1" / "service1-kube.yaml", DIFFERENT_FILE_CONTENT)
        self.write_file(desired_dir / "service3" / "service3-kube.yaml", DIFFERENT_FILE_CONTENT)
        self.delete_service(desired_dir, "service4")
        self.delete_service(desired_dir, "service5")
        changes = diff.list_deployment_differences()
        assert len(changes) == 4
        self.commit_and_assert_zero(changes, diff)

        # delete all services
        self.delete_service(desired_dir, "service1")
        self.delete_service(desired_dir, "service2")
        self.delete_service(desired_dir, "service3")
        changes = diff.list_deployment_differences()
        assert len(changes) == 3
        self.commit_and_assert_zero(changes, diff)
        # assert that dirs are empty
        assert len(list(desired_dir.iterdir())) == 0
        assert len(list(deployed_dir.iterdir())) == 0
