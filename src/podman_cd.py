import logging
import subprocess
from pathlib import Path

from difftool import DiffTool, DeploymentStatus, ModificationStatus
from gitforge import GitForge
from podman import Podman
from systemctl import Systemctl

logger = logging.getLogger(__name__)

class PodmanCD:
    def __init__(self, desired_dir: str, deployed_dir: str, user_mode: bool):
        self.desired_dir = Path(desired_dir).resolve()
        self.deployed_dir = Path(deployed_dir).resolve()

        self.forge = GitForge(self.desired_dir)
        self.podman = Podman()
        self.systemctl = Systemctl(user_mode=user_mode)
        self.diff_tool = DiffTool(self.desired_dir, self.deployed_dir)

    def run_update(self):
        logger.info("Checking for updates...")

        changed_dirs = self.diff_tool.list_deployment_differences()

        if len(changed_dirs) == 0:
            logger.info("No changes detected.")
            return

        # Fetch new images in MODIFIED or ADDED directories
        for dir in changed_dirs:
            if dir.status in [ModificationStatus.ADDED, ModificationStatus.MODIFIED]:
                self.fetch_images_in_kube(dir)

        self.diff_tool.commit_changes(changed_dirs)
        self.handle_services_lifecycle(changed_dirs)

    @staticmethod
    def _parse_yaml_for_images(file: Path) -> set[str]:
        images: set[str] = set()

        with open(file, "r") as f:
            for line in f:
                line = line.strip()
                if line.startswith("image:"):
                    image = line.split("image:")[1].strip()
                    images.add(image)

        return images

    def fetch_images_in_kube(self, dir: DeploymentStatus):
        """
            Parse all top-level YAML files in the given directory for container images and pull them.
        """

        images: set[str] = set()
        for file in (self.desired_dir / dir.path).iterdir():
            if file.is_file() and file.name.endswith((".yml", ".yaml")):
                images.union(self._parse_yaml_for_images(file))

        for image in images:
            try:
                logger.info(f"Pulling image: {image}")
                self.podman.pull(image)
                logger.info(f"Done pulling: {image}")
            except subprocess.CalledProcessError as e:
                logger.error(f"Failed to pull image {image}")
                raise e

    def handle_services_lifecycle(self, changed_dirs: list[DeploymentStatus]):
        self.systemctl.daemon_reload()

        for dir in changed_dirs:
            if dir.service_name is None:
                logger.warning(f"No kube service found for {dir.path}, skipping lifecycle management!")
                continue

            if dir.status in [ModificationStatus.ADDED, ModificationStatus.MODIFIED]:
                logger.info(f"Restarting kube {dir.service_name}")
                # restart the service, if it is not running it will be started
                self.systemctl.restart(dir.service_name)

            elif dir.status == ModificationStatus.DELETED:
                self.systemctl.stop(dir.service_name)

            else:
                logger.warning(f"Unsupported file status: {dir.status} for {dir.path}, not doing anything!")
