#!/usr/bin/env python3
import argparse
import logging

from gitforge import GitForge
from podman_cd import PodmanCD

logging.basicConfig(level=logging.DEBUG)

def main():
    parser = argparse.ArgumentParser(description='Silly CD')
    parser.add_argument('--cwd', type=str, help='Root directory of monitored repository', default=".")

    args = parser.parse_args()

    podmanCD = PodmanCD(args.cwd, True)
    podmanCD.run_update()

if __name__ == "__main__":
    main()
