"""Utility functions."""
from typing import Generator


def generate_page_list(file_name: str) -> Generator[tuple[str, int],
                                                    None,
                                                    None]:
    """Create a page list from a file, readable by `massrollback`.

    Each page in the file should be in its own row, consiting of a site
    name (including the TLD), a space, and then a pageid *or* title.
    The two can be mixed.  For instance:
        en.wikipedia.org 15580374
        fr.wikisource.org Wikisource:Accueil
    """
    with open(file_name, 'r', encoding='utf-8') as f:
        for line in f.read().split("\n"):
            if not line:
                continue
            try:
                site, page_id = line.split(" ")
            except ValueError:
                print("Line formatted incorrectly " + line)
                continue
            try:
                yield site, int(page_id)
            except ValueError:
                print(line + " is not an integer")
