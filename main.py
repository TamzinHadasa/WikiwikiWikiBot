"""A lightweight framework for MediaWiki bots."""
__author__ = "Tamzin Hadasa Kelly"
__copyright__ = "Copyright 2021-2022, Tamzin Hadasa Kelly"
__license__ = "The MIT License"
__email__ = "coding@tamz.in"
__version__ = "1.0.0"

import sys

import api
import scripts.massrollback


if __name__ == "__main__":
    print(f"RUNNING (version {__version__})")
    try:
        if sys.argv[1] == "rollback":
            print(f"rollbacking {sys.argv[2]}...")
            print(api.rollback(sys.argv[2]))
        elif sys.argv[1] == "massrollback":
            try:
                summary = sys.argv[3]
            except IndexError:
                summary = ""
            try:
                markbot = sys.argv[-1] in ('--markbot','"-b')
            except IndexError:
                markbot = False
            print(f"massrollbacking based on {sys.argv[2]}...")
            scripts.massrollback.main(file_name=sys.argv[2],
                                      summary=summary,
                                      markbot=markbot)
    except IndexError:
        sys.exit()
