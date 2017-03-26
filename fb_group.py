# -*- coding: utf-8 -*-
import facebook, logging, ConfigParser, sys, json
logging.basicConfig(level=logging.INFO)
from datetime import datetime
import networkx as nx

fb_datetime_format = "%Y-%m-%dT%H:%M:%S" # 2017-03-21T14:18:11+0000
G = nx.DiGraph()

if len(sys.argv) > 1:
    config_file = sys.argv[1]
else:
    logging.error("Please provide a configuration file.")
    exit()

config = ConfigParser.SafeConfigParser()
try:
    config.read(config_file)
except Exception, e:
    logging.error("Provided configuration file is missing or wrong.")
    exit()

try:
    access_token = config.get("Auth","access_token")
except ConfigParser.NoOptionError, e:
    logging.warning("Missing access_token, I'll try to use app_id and app_secret instead.")
    try:
        app_id = config.get("Auth","app_id")
        app_secret = config.get("Auth","app_secret")
        access_token = "%s|%s" % ( app_id , app_secret )
    except ConfigParser.NoOptionError, e:
        logging.error("No auth token provided.")
        exit()

graph = facebook.GraphAPI(
    access_token = access_token,
    version = "2.8"
)

try:
    group_id = config.get("Group","id")
except ConfigParser.NoOptionError, e:
    logging.error("No group id provided.")
    exit()

try:
    group = graph.get_object(id = group_id)
    G.graph['name'] = group['name']
    G.graph['last_update'] = datetime.now().strftime(fb_datetime_format)
    logging.info("Group: %s" % group['name'])
except facebook.GraphAPIError, e:
    logging.error("Errors during connections to Facebook Graph API: %s." % e)
    exit()

try:
    datetime_format = config.get("Datetime","datetime_format")
except ConfigParser.NoOptionError, e:
    datetime_format = "%Y-%m-%d %H:%M:%S"

try:
    since_datetime = datetime.strptime(
        config.get("Datetime","since_datetime"),
        datetime_format
    )
    G.graph['since'] = since_datetime.strftime(fb_datetime_format)
except ConfigParser.NoOptionError, e:
    since_datetime = None
    G.graph['since'] = datetime.fromtimestamp(0).strftime(fb_datetime_format)

try:
    until_datetime = datetime.strptime(
        config.get("Datetime","until_datetime"),
        datetime_format
    )
    G.graph['until'] = until_datetime.strftime(fb_datetime_format)
except ConfigParser.NoOptionError, e:
    until_datetime = None
    G.graph['until'] = datetime.now().strftime(fb_datetime_format)

# Group members: https://developers.facebook.com/docs/graph-api/reference/v2.8/group/members
num_members = 0
if not since_datetime and not until_datetime:
    members = graph.get_all_connections(
        id = group_id,
        connection_name = "members",
        fields = "id,name"
    )

    for member in members:

        logging.debug(member)
        num_members += 1

        G.add_node(member['id'], type = 'user', **member) # user

        logging.info("- MEMBER: %s" % member['name'])

logging.info("Download graph from %s to %s" % ( G.graph['since'] , G.graph['until'] ))

posts = graph.get_all_connections(
    id = group_id,
    connection_name = "feed",
    fields = "id,message,from,updated_time",
    since = since_datetime and (since_datetime - datetime(1970, 1, 1)).total_seconds(),
    until = until_datetime and (until_datetime - datetime(1970, 1, 1)).total_seconds()
)

num_posts = 0
num_reactions = 0
num_comments = 0
for post in posts:

    logging.debug(post)
    num_posts += 1

    G.add_node(post['id'], type = 'post', **post) # post
    G.add_node(post['from']['id'], type = 'user', **post['from']) # user

    G.add_edge(post['from']['id'], post['id'], type = 'is author of') # user -|is author of|> post

    logging.info("- POST: %s" % post.get('message',''))
    logging.info("+ DATETIME: %s" % post['updated_time'])
    logging.info("+ AUTHOR: %s" % post['from']['name'])

    post_reactions = graph.get_all_connections(
        id = post['id'],
        connection_name = "reactions"
    )

    for reaction in post_reactions:

        logging.debug(reaction)
        num_reactions += 1

        #G.add_node(reaction['type'], type = 'reaction') # reaction
        G.add_node(reaction['id'], type = 'user', id = reaction['id'], name = reaction['name']) # user

        #G.add_edge(reaction['type'], post['id']) # reaction <--> post
        G.add_edge(reaction['id'], post['id'], type = 'reacts to', reaction = reaction['type']) # user -|reacts to|> post

        logging.info("+ %s: %s" % ( reaction['type'] , reaction['name']))

    comments = graph.get_all_connections(
        id = post['id'],
        connection_name = "comments"
    )

    for comment in comments:

        logging.debug(comment)

        comment_datetime = datetime.strptime(
            comment['created_time'][:19],
            fb_datetime_format
        )

        if since_datetime and comment_datetime < since_datetime:
            continue

        if until_datetime and comment_datetime > until_datetime:
            continue

        num_comments += 1

        G.add_node(comment['id'], type = 'comment', **comment) # comment
        G.add_node(comment['from']['id'], type = 'user', **comment['from']) # user

        G.add_edge(comment['id'], post['id'], type = 'in reply to') # comment -|in reply to|> post
        G.add_edge(comment['from']['id'], comment['id'], type = 'is author of') # user -|is author of|> comment

        logging.info("-- COMMENT: %s" % comment.get('message',''))
        logging.info("++ DATETIME: %s" % comment['created_time'])
        logging.info("++ AUTHOR: %s" % comment['from']['name'])

        comment_likes = graph.get_all_connections(
            id = comment['id'],
            connection_name = "likes"
        )

        for like in comment_likes:

            logging.debug(like)
            num_reactions += 1

            #G.add_node('LIKE', type = 'reaction') # reaction
            G.add_node(like['id'], type = 'user', **like) # user

            #G.add_edge('LIKE', comment['id']) # reaction <--> comment
            G.add_edge(like['id'], comment['id'], type = 'reacts to', reaction = 'LIKE') # user -|reacts to|> comment

            logging.info("++ LIKE: %s" % like['name'])

        replies = graph.get_all_connections(
            id = comment['id'],
            connection_name = "comments"
        )

        for reply in replies:

            logging.debug(reply)
            num_comments += 1

            G.add_node(reply['id'], type = 'comment', **reply) # comment
            G.add_node(reply['from']['id'], type = 'user', **reply['from']) # user

            G.add_edge(reply['id'], comment['id'], type = 'in reply to') # comment -|in reply to|> comment
            G.add_edge(reply['from']['id'], reply['id'], type = 'is author of') # user -|is author of|> comment

            logging.info("--- reply: %s" % reply.get('message',''))
            logging.info("+++ DATETIME: %s" % reply['created_time'])
            logging.info("+++ AUTHOR: %s" % reply['from']['name'])

            reply_likes = graph.get_all_connections(
                id = reply['id'],
                connection_name = "likes"
            )

            for like in reply_likes:

                logging.debug(like)
                num_reactions += 1

                #G.add_node('LIKE', type = 'reaction') # reaction
                G.add_node(like['id'], type = 'user', **like) # user

                #G.add_edge('LIKE', reply['id']) # reaction <--> comment
                G.add_edge(like['id'], reply['id'], type = 'reacts to', reaction = 'LIKE') # user -|reacts to|> comment

                logging.info("+++ LIKE: %s" % like['name'])

logging.info(
    "Members: %d | Posts: %d | Reactions: %d | Comments: %d\nNodes: %d | Edges: %d" % (
        len(filter(lambda (n, d): d['type'] == 'user', G.nodes(data=True))),
        len(filter(lambda (n, d): d['type'] == 'post', G.nodes(data=True))),
        len(filter(lambda (n1, n2, d): d['type'] == 'reacts to', G.edges(data=True))),
        len(filter(lambda (n, d): d['type'] == 'comment', G.nodes(data=True))),
        G.number_of_nodes(),
        G.number_of_edges()
    )
)

# node positioning algo
# http://networkx.readthedocs.io/en/latest/reference/drawing.html
pos=nx.spring_layout(G) # Fruchterman-Reingold

nx.set_node_attributes(G,'pos',pos)

try:
    graph_type = config.get("Graph","graph_type")
except ConfigParser.NoOptionError, e:
    graph_type = "json"

try:
    file_name = "%s_%s" % ( datetime.now().strftime("%Y%m%d%H%M") , config.get("Graph","file_name").split('.')[0] )
except ConfigParser.NoOptionError, e:
    file_name = "%s_%s" % ( datetime.now().strftime("%Y%m%d%H%M") , G.graph['name'] )

from networkx.readwrite import json_graph

# node_link_data() sets links' target and source to nodes' indices in nodes array,
# not to real nodes' ids... this workaround fix this issue
json_data = json_graph.node_link_data(G)
for i,l in enumerate(json_data['links']):
    json_data['links'][i]['target'] = json_data['nodes'][l['target']]['id']
    json_data['links'][i]['source'] = json_data['nodes'][l['source']]['id']
# end workaround
with open(file_name+".json",'w') as f:
    json.dump(json_data, f)

# export also in gexf format, supported by gephi
nx.write_gexf(G, file_name+".gexf")

