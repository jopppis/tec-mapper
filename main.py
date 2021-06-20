#!/usr/bin/env python3
"""IONEX file handling."""

import argparse

from application import TecMapperApplication


def main():
    """Main entry point for the application."""
    parser = argparse.ArgumentParser(
        description='Tec Mapper application', formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('-c', '--cache_dir', default=None, help="Path to directorty to use for caching IONEX files")
    parser.add_argument('-s', '--starting_date', default=None, type=str, help="Starting date for the date picker. Use format yyyy-mm-dd")
    args = parser.parse_args()
    app = TecMapperApplication(cache_dir=args.cache_dir, starting_date=args.starting_date)

main()
