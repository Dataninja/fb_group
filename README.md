# Facebook group harvester

Download all data from a Facebook Group: posts, comments (and subcomments), likes, reactions, users, shares, user mentions and shared links using the [official facebook-sdk module](https://github.com/mobolic/facebook-sdk/) for Python 2.7. WARNING! Under development, not all features are implemented or to be considered stable.

## Installation

Set a [virtual environment](https://virtualenv.pypa.io/en/stable/): `virtualenv facebookenv && source facebookenv/bin/activate`.
I suggest to use the [virtualenvwrapper utility](https://virtualenvwrapper.readthedocs.io/en/latest/):
`mkvirtualenv facebookenv && workon`.

Install dependencies: `pip install -r requirements.txt`.

## Configuration

Copy `example.cnf` to `your_group_name.cnf`.

Edit `your_group_name.cnf` adding your `access_token` (or `app_id` and `app_secret`) and your `group_id`.
You must create a Facebook App to obtain the first three parameters: https://developers.facebook.com/.
If you don't know your group id, you can find it [in the source of the page](http://stackoverflow.com/a/33094493).

You can choose between two modes: the `archive` one downloads all elements in the time window selected,
the `update` one takes an existing gexf file and download only new elements since the last post found
and until the `until_datetime` or now.

Other optional options are `since_datetime` and `until_datetime` to narrow the time window and filter harvested posts.
You can use your favorite format to write datetime, describing it in `datetime_format` option using the *strftime*
syntax: http://strftime.org/. Please escape `%` char with another `%`, so use double `%%` (sic).

You can also enable or disable two features: download of all members (and not only the active ones in the
time window) with `all_members`, and layout computing ([Fruchterman-Reingold force-directed](http://networkx.github.io/documentation/development/reference/generated/networkx.drawing.layout.spring_layout.html) layout) with `calc_layout`.

All harvested data will be saved in two files: `file_name`.gexf and `file_name`.json. You can customize `file_name` value,
but the default value is `{YYYYmmddHHMM}_{group name}`.

## Usage

Run: `python fb_group.py your_group_name.cnf`. Standard output is quite verbose.

Harvested data are organized in a graph structure:

* nodes: users, posts, comments, domains;
* edges:
  * user -|is author of|-> post,
  * user -|is author of|-> comment,
  * user -|reacts to|-> post,
  * user -|reacts to|-> comment,
  * post -|mentions|-> user,
  * post -|mentions|-> domain,
  * comment -|in reply to|-> post,
  * comment -|in reply to|-> comment,
  * comment -|mentions|-> user,
  * comment -|mentions|-> domain.

There are four types of nodes and four types of edges. Nodes have additional attributes (ie. name of user, message for posts and comments). The -|reacts to|-> edge has an attribute for both posts and comments, the [type of reaction](https://developers.facebook.com/docs/graph-api/reference/post/reactions) (LIKE, LOVE, WOW, HAHA, SAD, ANGRY, THANKFUL[, SHARE]), and the -|mentions|-> one directed to a domain has many attributs, including original link.

This graph is saved in two formats: [GEXF](https://networkx.github.io/documentation/development/reference/generated/networkx.readwrite.gexf.write_gexf.html#networkx.readwrite.gexf.write_gexf) and [JSON](https://networkx.github.io/documentation/development/reference/generated/networkx.readwrite.json_graph.node_link_data.html#networkx.readwrite.json_graph.node_link_data).

### GEXF

It's a [XML based format](https://gephi.org/gexf/format/) suitable to be imported and managed by [Gephi](https://gephi.org/).

### JSON

It's a simple JSON representation of the network: `{ "nodes": [...], "edges": [...] }`. Single nodes are objects with an id and some additional attributes. Singles edges are objects with a source and a target containing nodes' ids. You can use it directly in javascript visualizations, ie. powered by the [d3js library](http://bl.ocks.org/mbostock/4062045).

## Thanks to

Marco Goldin.
