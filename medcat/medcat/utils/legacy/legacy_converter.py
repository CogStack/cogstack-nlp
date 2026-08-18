from typing import Optional
import os
import argparse
import logging

from medcat.utils.legacy.conversion_all import Converter, logger as clogger
from medcat.storage.serialisers import AvailableSerialisers
from medcat.utils.legacy.helpers import logger as hlogger


def do_conversion(file_from: str, file_to: str,
                  save_format: AvailableSerialisers):
    """Perform the conversion from v1 to v2.

    Args:
        file_from (str): The v1 model pack path.
        file_to (str): The v2/target model pack path.
        save_format (AvailableSerialisers): The type of serialiser for v2.
    """
    converter = Converter(file_from, file_to, save_format)
    converter.convert()


def main(argv: Optional[list[str]] = None):
    parser = argparse.ArgumentParser()
    parser.add_argument('old_model', help='The path to the old model')
    parser.add_argument('new_model', help='The path to the new model')
    parser.add_argument('--format', help='The save format',
                        default=AvailableSerialisers.dill, required=False,
                        choices=list(AvailableSerialisers),
                        type=lambda s: AvailableSerialisers[s.lower()])
    parser.add_argument('--silent', '-s',
                        help='Make the operation silent (no console output)',
                        action='store_true')
    parser.add_argument('--verbose', '--debug',
                        help='Make the operation produce more debug output',
                        action='store_true')
    parser.add_argument('--new-folder', help='Create new folder if folder '
                        'does not exist', action='store_true')
    args = parser.parse_args(args=argv)
    if not args.silent:
        sh = logging.StreamHandler()
        clogger.addHandler(sh)
        hlogger.addHandler(sh)
    if args.verbose:
        clogger.setLevel(logging.DEBUG)
        hlogger.setLevel(logging.DEBUG)
    if not os.path.exists(args.new_model) and args.new_folder:
        print("Creating new folder:", args.new_model)
        os.mkdir(args.new_model)
    do_conversion(args.old_model, args.new_model, args.format)


if __name__ == "__main__":
    main()
