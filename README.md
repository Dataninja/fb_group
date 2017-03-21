# Facebook group harvester

Download all data from a Facebook Group: posts, comments (and subcomments), likes, reactions, users, using the [official facebook-sdk module](https://github.com/mobolic/facebook-sdk/) for Python 2.7. WARNING! Under development, not all features are implemented or to be considered stable.

## Installation

Set a virtualenv: `virtualenv facebookend && source facebookenv/bin/activate`.

Install dependencies: `pip install -r requirements.txt`.

## Usage

Copy `example.cnf` to `your_group_name.cnf`.

Edit `your_group_name.cnf` adding your access\_token (or app\_id and app\_secret) e your group\_id.

Run: `python fb_group.py your_group_name.cnf`.

## Thanks to

Marco Goldin.

