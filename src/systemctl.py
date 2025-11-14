import logging
import subprocess

logger = logging.getLogger(__name__)


class Systemctl:
    def __init__(self, user_mode: bool = False):
        """
        Initialize Systemctl wrapper.

        Args:
            user_mode: If True, use --user flag for user services
        """
        self.user_mode = user_mode

    def run_systemctl_command(self, *args, user: bool | None = None) -> str:
        """
        Run a systemctl command with the provided arguments.

        Args:
            *args: Systemctl command arguments (e.g., "start", "status", "enable")
            user: If True, add --user flag. If None, use self.user_mode

        Returns:
            str: The stdout output of the command

        Raises:
            subprocess.CalledProcessError: If the systemctl command fails
        """
        cmd = ["systemctl"]

        use_user_mode = user if user is not None else self.user_mode
        if use_user_mode:
            cmd.append("--user")

        cmd.extend(list(args))
        logger.debug(f"Running systemctl command: {cmd}")

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )

        return result.stdout.strip()

    def start(self, service: str, user: bool | None = None) -> str:
        """Start a service."""
        return self.run_systemctl_command("start", service, user=user)

    def stop(self, service: str, user: bool | None = None) -> str:
        """Stop a service."""
        return self.run_systemctl_command("stop", service, user=user)

    def restart(self, service: str, user: bool | None = None) -> str:
        """Restart a service."""
        return self.run_systemctl_command("restart", service, user=user)

    def reload(self, service: str, user: bool | None = None) -> str:
        """Reload a service configuration."""
        return self.run_systemctl_command("reload", service, user=user)

    def enable(self, service: str, user: bool | None = None) -> str:
        """Enable a service to start on boot."""
        return self.run_systemctl_command("enable", service, user=user)

    def disable(self, service: str, user: bool | None = None) -> str:
        """Disable a service from starting on boot."""
        return self.run_systemctl_command("disable", service, user=user)

    def status(self, service: str, user: bool | None = None) -> str:
        """Get the status of a service."""
        return self.run_systemctl_command("status", service, user=user)

    def is_active(self, service: str, user: bool | None = None) -> bool:
        """Check if a service is active."""
        try:
            self.run_systemctl_command("is-active", service, user=user)
            return True
        except subprocess.CalledProcessError:
            return False

    def is_enabled(self, service: str, user: bool | None = None) -> bool:
        """Check if a service is enabled."""
        try:
            self.run_systemctl_command("is-enabled", service, user=user)
            return True
        except subprocess.CalledProcessError:
            return False

    def daemon_reload(self, user: bool | None = None) -> str:
        """Reload systemd manager configuration."""
        return self.run_systemctl_command("daemon-reload", user=user)
