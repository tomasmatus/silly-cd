import logging
import shutil
from pathlib import Path
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

class ModificationStatus(Enum):
    ADDED = "ADDED"
    MODIFIED = "MODIFIED"
    DELETED = "DELETED"

@dataclass
class DeploymentStatus:
    path: Path
    status: ModificationStatus
    service_name: str | None

class DiffTool:
    desired_dir: Path
    deployed_dir: Path

    def __init__(self, desired_dir: Path, deployed_dir: Path) -> None:
        self.desired_dir = desired_dir
        self.deployed_dir = deployed_dir

        if (self.desired_dir.exists() is False) or (self.desired_dir.is_dir() is False):
            raise NotADirectoryError(f"Desired directory does not exist or is not a directory: {self.desired_dir}")
        if (self.deployed_dir.exists() is False) or (self.deployed_dir.is_dir() is False):
            raise NotADirectoryError(f"deployed directory does not exist or is not a directory: {self.deployed_dir}")

    @staticmethod
    def _file_condition(file: Path) -> bool:
        """
            Only consider regular files that are not hidden.
        """
        return file.is_file() and not file.name.startswith(".")

    @staticmethod
    def _dir_condition(file: Path) -> bool:
        """
            Only consider directories that are not hidden.
        """
        return file.is_dir() and not file.name.startswith(".")

    def get_service_name(self, dir: Path) -> str | None:
        # dir is relative to self.desired_dir
        full_path = self.desired_dir / dir
        for file in full_path.iterdir():
            if file.is_file() and file.suffix == ".kube":
                return file.stem + ".service"

        return None

    def _check_modification(self, dirs: set[Path]) -> list[DeploymentStatus]:
        result: list[DeploymentStatus] = []
        for dir in dirs:
            desired_subdir = self.desired_dir / dir
            deployed_subdir = self.deployed_dir / dir

            # Get all files recursively in both subdirectories (using relative paths)
            desired_files = {f.relative_to(desired_subdir) for f in desired_subdir.rglob('*') if self._file_condition(f)}
            deployed_files = {f.relative_to(deployed_subdir) for f in deployed_subdir.rglob('*') if self._file_condition(f)}

            added_files = desired_files - deployed_files
            deleted_files = deployed_files - desired_files

            # Check for modified files
            common_files = desired_files.intersection(deployed_files)

            modified_files = set()
            for file in common_files:
                desired_file = desired_subdir / file
                deployed_file = deployed_subdir / file
                # Compare file contents
                if desired_file.read_bytes() != deployed_file.read_bytes():
                    modified_files.add(file)

            # Mark directory as modified if there are any changes, during commit the original subdir is deleted
            if added_files or deleted_files or modified_files:
                # store the relative path
                result.append(DeploymentStatus(dir, ModificationStatus.MODIFIED, self.get_service_name(desired_subdir)))

        return result

    def list_deployment_differences(self) -> list[DeploymentStatus]:
        """
            List modifications on top level subdirectories in deployed state
        """
        desired_subdirs = set(f.relative_to(self.desired_dir) for f in self.desired_dir.iterdir() if self._dir_condition(f))
        deployed_subdirs = set(f.relative_to(self.deployed_dir) for f in self.deployed_dir.iterdir() if self._dir_condition(f))

        deleted_dirs = deployed_subdirs - desired_subdirs
        added_dirs = desired_subdirs - deployed_subdirs
        other_dirs = desired_subdirs.intersection(deployed_subdirs)

        dir_status = [DeploymentStatus(dir, ModificationStatus.DELETED, self.get_service_name(dir)) for dir in deleted_dirs]
        dir_status.extend([DeploymentStatus(dir, ModificationStatus.ADDED, self.get_service_name(dir)) for dir in added_dirs])
        dir_status.extend(self._check_modification(other_dirs))

        return dir_status

    def commit_changes(self, changed_dirs: list[DeploymentStatus]):
        """
            Recursively copy files from desired directory to the deployed directory.

            @param changed_dirs: List of DeploymentStatus, path is relative to self.desired_dir
        """

        for dir_status in changed_dirs:
            if dir_status.status in [ModificationStatus.ADDED, ModificationStatus.MODIFIED]:
                src_dir = self.desired_dir / dir_status.path
                dst_dir = self.deployed_dir / dir_status.path

                # Delete the current deployed dir and replace it with a new one
                logger.info(f"Copying {src_dir} to {dst_dir}")
                if dst_dir.exists():
                    shutil.rmtree(dst_dir)

                shutil.copytree(src_dir, dst_dir, dirs_exist_ok=True)

            elif dir_status.status == ModificationStatus.DELETED:
                dst_dir = self.deployed_dir / dir_status.path.name
                if dst_dir.exists():
                    logger.info(f"Removing {dst_dir}")
                    shutil.rmtree(dst_dir)
