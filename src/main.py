#!/usr/bin/env python3
import argparse
import logging

from podman_cd import PodmanCD

logging.basicConfig(level=logging.DEBUG)

def main():
    parser = argparse.ArgumentParser(description='Silly CD')
    parser.add_argument('--repo-dir', type=str, help='Root directory of monitored repository', default=".")
    parser.add_argument('--deploy-dir', type=str, help='Root directory of deployed directory', default=".")

    args = parser.parse_args()

    podmanCD = PodmanCD(args.repo_dir, args.deploy_dir, True)
    podmanCD.run_update()

if __name__ == "__main__":
    main()
