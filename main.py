"""A lightweight framework for MediaWiki bots."""
__author__ = "Tamzin Hadasa Kelly"
__copyright__ = "Copyright 2021-2022, Tamzin Hadasa Kelly"
__license__ = "The MIT License"
__email__ = "coding@tamz.in"
__version__ = "0.1.0"

import sys
import time

import api
import antivandalism.massrollback


if __name__ == "__main__":
    print(f"RUNNING (version {__version__})")
    try:
        if sys.argv[1] == "rollback":
            print(api.rollback(sys.argv[2]))
        elif sys.argv[1] == "massrollback":
            antivandalism.massrollback.main(file_name=sys.argv[2],
                                            summary=sys.argv[3],
                                            markbot=sys.argv[4] == 'markbot')
    except IndexError:
       sys.exit()
