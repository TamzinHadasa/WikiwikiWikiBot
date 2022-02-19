# Wikiwiki Wikibot: A lightweight solution to automated MediaWiki editing

The word "wiki", to mean collaboratively editable project, originally comes
from the Hawaiian term "wikiwiki" meaning very fast.  This is a wikibot
meant to be straightforward and easy to use.

## Setup and configuration

`pip install -r requirements.txt`

Create a `config.py` file, following the instructions in `config_example.py`.

## Running

The following assume you are in the correct directory.

### rollback

`python main.py rollback <page ID>`

A page's ID can be found through `?action=info` (the "Page information" link).

@TODO: Support summaries and markbot like massrollback does.

### massrollback

Create a file with a format like this
> en.wikipedia.org 12345  
> fr.wikisource.org 67890

Where the first word is the full site name and the second is the page ID.
Save it in a folder called `data`.

Then run
`python main.py massrollback <file name> [summary] [args]`

* The <file name> should be the name of the file in `data/`, not including
  `data/` itself.
* The [summary] will become the rollback summary.  If it's more than one word,
  wrap it in quotation marks.  If not specified or if an empty string is
  given, the default rollback summary for that wiki will be used instead.
* Currently only one arg is supported, `-b` or `--markbots`, which will mark
  the rollbacks as bot edits, for the purposes of RecentChanges and
  watchlists.
