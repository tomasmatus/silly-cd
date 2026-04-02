import logging
import subprocess
from pathlib import Path

from .difftool import DeploymentStatus, DiffTool, ModificationStatus
from .gitforge import GitForge
from .podman import Podman
from .systemctl import Systemctl

logger = logging.getLogger(__name__)


class PodmanCD:
    def __init__(self, desired_dir: str, deployed_dir: str, *, user_mode: bool):
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
        for changed_dir in changed_dirs:
            if changed_dir.status in [ModificationStatus.ADDED, ModificationStatus.MODIFIED]:
                self.fetch_images_in_kube(changed_dir)

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

    def fetch_images_in_kube(self, kube_dir: DeploymentStatus):
        """
            Parse all top-level YAML files in the given directory for container images and pull them.
        """

        images: set[str] = set()
        for file in (self.desired_dir / kube_dir.path).iterdir():
            if file.is_file() and file.name.endswith((".yml", ".yaml")):
                images.union(self._parse_yaml_for_images(file))

        for image in images:
            try:
                logger.info("Pulling image: %s", image)
                self.podman.pull(image)
                logger.info("Done pulling: %s", image)
            except subprocess.CalledProcessError as e:
                logger.error("Failed to pull image %s", image)
                raise e

    def handle_services_lifecycle(self, changed_dirs: list[DeploymentStatus]):
        # first stop all deleted services
        for changed_dir in changed_dirs:
            if changed_dir.service_name is None:
                logger.warning("No kube service found for %s, skipping lifecycle management!", changed_dir.path)
                continue

            if changed_dir.status == ModificationStatus.DELETED:
                self.systemctl.stop(changed_dir.service_name)

        # commit changes to deployed_dir and perform daemon-reload to sync changes into systemd
        self.diff_tool.commit_changes(changed_dirs)
        self.systemctl.daemon_reload()

        for changed_dir in changed_dirs:
            if changed_dir.service_name is None:
                logger.warning("No kube service found for %s, skipping lifecycle management!", changed_dir.path)
                continue

            if changed_dir.status in [ModificationStatus.ADDED, ModificationStatus.MODIFIED]:
                logger.info("Restarting kube %s", changed_dir.service_name)
                # restart the service, if it is not running it will be started
                self.systemctl.restart(changed_dir.service_name)

            else:
                logger.warning("Unsupported file status: %s for %s, not doing anything!",
                               changed_dir.status, changed_dir.path)
