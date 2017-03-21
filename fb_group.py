import facebook, logging, ConfigParser, sys, json
logging.basicConfig(level=logging.INFO)
from datetime import datetime
import networkx as nx

fb_datetime_format = "%Y-%m-%dT%H:%M:%S" # 2017-03-21T14:18:11+0000
G = nx.Graph()

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
except ConfigParser.NoOptionError, e:
    since_datetime = datetime.fromtimestamp(0)
G.graph['since'] = since_datetime.strftime(fb_datetime_format)

try:
    until_datetime = datetime.strptime(
        config.get("Datetime","until_datetime"),
        datetime_format
    )
except ConfigParser.NoOptionError, e:
    until_datetime = datetime.now()
G.graph['until'] = until_datetime.strftime(fb_datetime_format)

# Group members: https://developers.facebook.com/docs/graph-api/reference/v2.8/group/members
members = graph.get_all_connections(
    id = group_id,
    connection_name = "members",
    fields = "id,name"
)

num_members = 0
for member in members:

    logging.debug(member)
    num_members += 1

    G.add_node(member['id'], node_type = 'user', **member) # user

    logging.info("- MEMBER: %s" % member['name'])

    if not num_members%25:
        break

posts = graph.get_all_connections(
    id = group_id,
    connection_name = "feed",
    fields = "id,message,from,updated_time"
)

num_posts = 0
num_reactions = 0
num_comments = 0
for post in posts:

    logging.debug(post)
    num_posts += 1
    post_datetime = datetime.strptime(
        post['updated_time'][:19],
        fb_datetime_format
    )

    if post_datetime > until_datetime:
        continue

    if post_datetime < since_datetime:
        break

    G.add_node(post['id'], node_type = 'post', **post) # post
    G.add_node(post['from']['id'], node_type = 'user', **post['from']) # user

    G.add_edge(post['id'], post['from']['id']) # post <--> user

    logging.info("- POST: %s" % post['message'])
    logging.info("+ DATETIME: %s" % post['updated_time'])
    logging.info("+ AUTHOR: %s" % post['from']['name'])

    post_reactions = graph.get_all_connections(
        id = post['id'],
        connection_name = "reactions"
    )

    for reaction in post_reactions:

        logging.debug(reaction)
        num_reactions += 1

        G.add_node(reaction['type'], node_type = 'reaction') # reaction
        G.add_node(reaction['id'], node_type = 'user', id = reaction['id'], name = reaction['name']) # user

        G.add_edge(reaction['type'], post['id']) # reaction <--> post
        G.add_edge(reaction['type'], reaction['id']) # reaction <--> user

        logging.info("+ %s: %s" % ( reaction['type'] , reaction['name']))

    comments = graph.get_all_connections(
        id = post['id'],
        connection_name = "comments"
    )

    for comment in comments:

        logging.debug(comment)
        num_comments += 1

        G.add_node(comment['id'], node_type = 'comment', **comment) # comment
        G.add_node(comment['from']['id'], node_type = 'user', **comment['from']) # user

        G.add_edge(comment['id'], post['id']) # comment <--> post
        G.add_edge(comment['id'], comment['from']['id']) # comment <--> user

        logging.info("-- COMMENT: %s" % comment['message'])
        logging.info("++ DATETIME: %s" % comment['created_time'])
        logging.info("++ AUTHOR: %s" % comment['from']['name'])

        comment_likes = graph.get_all_connections(
            id = comment['id'],
            connection_name = "likes"
        )

        for like in comment_likes:

            logging.debug(like)
            num_reactions += 1

            G.add_node('LIKE', node_type = 'reaction') # reaction
            G.add_node(like['id'], node_type = 'user', **like) # user

            G.add_edge('LIKE', comment['id']) # reaction <--> comment
            G.add_edge('LIKE', like['id']) # reaction <--> user

            logging.info("++ LIKE: %s" % like['name'])

        responses = graph.get_all_connections(
            id = comment['id'],
            connection_name = "comments"
        )

        for response in responses:

            logging.debug(response)
            num_comments += 1

            G.add_node(response['id'], node_type = 'comment', **response) # comment
            G.add_node(response['from']['id'], node_type = 'user', **response['from']) # user

            G.add_edge(response['id'], comment['id']) # comment <--> comment
            G.add_edge(response['id'], response['from']['id']) # comment <--> user

            logging.info("--- RESPONSE: %s" % response['message'])
            logging.info("+++ DATETIME: %s" % response['created_time'])
            logging.info("+++ AUTHOR: %s" % response['from']['name'])

            response_likes = graph.get_all_connections(
                id = response['id'],
                connection_name = "likes"
            )

            for like in response_likes:

                logging.debug(like)
                num_reactions += 1

                G.add_node('LIKE', node_type = 'reaction') # reaction
                G.add_node(like['id'], node_type = 'user', **like) # user

                G.add_edge('LIKE', response['id']) # reaction <--> comment
                G.add_edge('LIKE', like['id']) # reaction <--> user

                logging.info("+++ LIKE: %s" % like['name'])

logging.info(
    "Members: %d | Posts: %d | Reactions: %d | Comments: %d\nNodes: %d | Edges: %d" % (
        num_members,
        num_posts,
        num_reactions,
        num_comments,
        G.number_of_nodes(),
        G.number_of_edges()
    )
)

try:
    graph_type = config.get("Graph","graph_type")
except ConfigParser.NoOptionError, e:
    graph_type = "json"

try:
    file_name = config.get("Graph","file_name")
except ConfigParser.NoOptionError, e:
    file_name = "%s.%s" % ( G.graph['name'] , graph_type )

if graph_type == 'json':
    from networkx.readwrite import json_graph
    with open(file_name,'w') as f:
        json.dump(json_graph.node_link_data(G), f)
else:
    try:
        write_graph = getattr(nx, "write_%s" % graph_type)
        write_graph(G, file_name)
    except:
        logging.error("Graph type not supported.")

