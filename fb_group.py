# -*- coding: utf-8 -*-
import facebook, logging, ConfigParser, sys, json
logging.basicConfig(level=logging.INFO)
from datetime import datetime
import networkx as nx

fb_datetime_format = "%Y-%m-%dT%H:%M:%S" # 2017-03-21T14:18:11+0000

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
    group = graph.get_object(
        id = group_id,
        fields = "id,name,updated_time"
    )
    logging.info("Group: %s" % group['name'])
except facebook.GraphAPIError, e:
    logging.error("Errors during connections to Facebook Graph API: %s." % e)
    exit()

try:
    datetime_format = config.get("Datetime","datetime_format")
except ConfigParser.NoOptionError, e:
    datetime_format = "%Y-%m-%d %H:%M:%S"

try:
    mode = config.get("Graph","mode")
except ConfigParser.NoOptionError, e:
    mode = "archive"

try:
    until_datetime = datetime.strptime(
        config.get("Datetime","until_datetime"),
        datetime_format
    )
except ConfigParser.NoOptionError, e:
    until_datetime = datetime.now()

if mode == "update":

    try:
        file_name = config.get("Graph","file_name").split('.')[0]
    except ConfigParser.NoOptionError, e:
        logging.error("Please provide a valid graph file in update mode.")
        exit()

    G = nx.read_gexf(file_name+'.gexf')
    G.graph['timestamp'] = group['updated_time']

    since_datetime = max([
        datetime.strptime(
            d['timestamp'].split('+')[0],
            fb_datetime_format
        )
        for n,d in G.nodes(data=True)
        if d['mtype'] == 'post'
    ])

else:

    try:
        file_name = "%s_%s" % ( datetime.now().strftime("%Y%m%d%H%M") , config.get("Graph","file_name").split('.')[0] )
    except ConfigParser.NoOptionError, e:
        file_name = "%s_%s" % ( datetime.now().strftime("%Y%m%d%H%M") , group['name'] )

    G = nx.DiGraph()

    G.graph['name'] = group['name']
    G.graph['url'] = "https://www.facebook.com/groups/%s/" % group['id']
    G.graph['timestamp'] = group['updated_time']

    try:
        since_datetime = datetime.strptime(
            config.get("Datetime","since_datetime"),
            datetime_format
        )
    except ConfigParser.NoOptionError, e:
        since_datetime = datetime.fromtimestamp(0)

G.graph['last_update'] = datetime.now().strftime(fb_datetime_format)

# Group members: https://developers.facebook.com/docs/graph-api/reference/v2.8/group/members
num_members = 0
try:
    if config.getboolean("Graph","all_members"):
        members = graph.get_all_connections(
            id = group_id,
            connection_name = "members",
            fields = "id,name,about,age_range,birthday,cover,education,email,gender,hometown,is_verified,work"
        )
    else:
        members = []
except ConfigParser.NoOptionError, e:
    members = []

for member in members:

    logging.debug(member)
    num_members += 1

    member_age_range = member.get('age_range',{})

    G.add_node(
        member['id'],
        mtype = 'user',
        fid = member['id'],
        label = member.get('name','__NA__'),
        url = "https://facebook.com/%s" % member['id'],
        name = member.get('name','__NA__'),
        about = member.get('about','__NA__'),
        age_range = "%d - %d" % ( member_age_range.get('min',0) , member_age_range.get('max',99) ),
        birthyear = member.get('birthday','__NA__/__NA__/__NA__').split('/')[-1],
        birthday = member.get('birthday','__NA__'),
        cover = member.get('cover',{}).get('source','__NA__'),
        education = member.get('education',[{}])[0].get('degree',{}).get('link','__NA__'),
        email = member.get('email','__NA__'),
        gender = member.get('gender','__NA__'),
        hometown = member.get('hometown',{}).get('link','__NA__'),
        is_verified = member.get('is_verified','__NA__'),
        work = member.get('work',[{}])[0].get('position',{}).get('link','__NA__')
    ) # user

    logging.info("- MEMBER: %s" % member['name'])

logging.info("Download graph from %s to %s" % ( since_datetime , until_datetime ))

posts = graph.get_all_connections(
    id = group_id,
    connection_name = "feed",
    fields = "id,message,from,updated_time",
    since = int((since_datetime - datetime(1970, 1, 1)).total_seconds()),
    until = int((until_datetime - datetime(1970, 1, 1)).total_seconds())
)

num_posts = 0
num_shares = 0
num_reactions = 0
num_comments = 0
for post in posts:

    logging.debug(post)
    num_posts += 1

    G.add_node(
        post['id'],
        mtype = 'post',
        fid = post['id'],
        label = post.get('message','')[0:12]+'...',
        url = "https://facebook.com/%s/posts/%s" % (post['from']['id'], post['id'].split('_')[1]),
        message = post.get('message',''),
        timestamp = post.get('updated_time','__NA__')
    ) # post

    if not nx.get_node_attributes(G, post['from']['id']):
        G.add_node(
            post['from']['id'],
            mtype = 'user',
            fid = post['from']['id'],
            label = post['from'].get('name','__NA__'),
            url = "https://facebook.com/%s" % post['from']['id'],
            name = post['from'].get('name','__NA__'),
            about = '__NA__',
            age_range = "0 - 99",
            birthyear = '__NA__',
            birthday = '__NA__',
            cover = '__NA__',
            education = '__NA__',
            email = '__NA__',
            gender = '__NA__',
            hometown = '__NA__',
            is_verified = '__NA__',
            work = '__NA__'
        ) # user

    G.add_edge(post['from']['id'], post['id'], mtype = 'is author of') # user -|is author of|> post

    logging.info("- POST: %s" % post.get('message',''))
    logging.info("+ DATETIME: %s" % post['updated_time'])
    logging.info("+ AUTHOR: %s" % post['from']['name'])

    shares = graph.get_all_connections(
        id = post['id'],
        connection_name = "sharedposts",
        fields = "id,from"
    )

    for share in shares:

        logging.debug(share)
        num_shares += 1

        if not nx.get_node_attributes(G, share['from']['id']):
            G.add_node(
                share['from']['id'],
                mtype = 'user',
                fid = share['from']['id'],
                label = share['from'].get('name','__NA__'),
                url = "https://facebook.com/%s" % share['from']['id'],
                name = share['from'].get('name','__NA__'),
                about = '__NA__',
                age_range = "0 - 99",
                birthyear = '__NA__',
                birthday = '__NA__',
                cover = '__NA__',
                education = '__NA__',
                email = '__NA__',
                gender = '__NA__',
                hometown = '__NA__',
                is_verified = '__NA__',
                work = '__NA__'
            ) # user

        G.add_edge(share['from']['id'], post['id'], mtype = 'reacts to', reaction = 'SHARE') # user -|reacts to|> post

        logging.info("++ SHARE: %s" % share['from']['name'])

    post_reactions = graph.get_all_connections(
        id = post['id'],
        connection_name = "reactions"
    )

    for reaction in post_reactions:

        logging.debug(reaction)
        num_reactions += 1

        if not nx.get_node_attributes(G, reaction['id']):
            G.add_node(
                reaction['id'],
                mtype = 'user',
                fid = reaction['id'],
                label = reaction.get('name','__NA__'),
                url = "https://facebook.com/%s" % reaction['id'],
                name = reaction.get('name','__NA__'),
                about = '__NA__',
                age_range = "0 - 99",
                birthyear = '__NA__',
                birthday = '__NA__',
                cover = '__NA__',
                education = '__NA__',
                email = '__NA__',
                gender = '__NA__',
                hometown = '__NA__',
                is_verified = '__NA__',
                work = '__NA__'
            ) # user

        #G.add_edge(reaction['type'], post['id']) # reaction <--> post
        G.add_edge(reaction['id'], post['id'], mtype = 'reacts to', reaction = reaction['type']) # user -|reacts to|> post

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

        if comment_datetime < since_datetime:
            continue

        if comment_datetime > until_datetime:
            continue

        num_comments += 1

        G.add_node(
            comment['id'],
            mtype = 'comment',
            fid = comment['id'],
            label = comment.get('message','')[0:12]+'...',
            url = "https://facebook.com/%s/posts/%s/?comment_id=%s" % (post['from']['id'], post['id'].split('_')[1], comment['id']),
            message = comment.get('message',''),
            timestamp = comment.get('created_time','__NA__')
        ) # comment

        if not nx.get_node_attributes(G, comment['from']['id']):
            G.add_node(
                comment['from']['id'],
                mtype = 'user',
                fid = comment['from']['id'],
                label = comment['from'].get('name','__NA__'),
                url = "https://facebook.com/%s" % comment['from']['id'],
                name = comment['from'].get('name','__NA__'),
                about = '__NA__',
                age_range = "0 - 99",
                birthyear = '__NA__',
                birthday = '__NA__',
                cover = '__NA__',
                education = '__NA__',
                email = '__NA__',
                gender = '__NA__',
                hometown = '__NA__',
                is_verified = '__NA__',
                work = '__NA__'
            ) # user

        G.add_edge(comment['id'], post['id'], mtype = 'in reply to') # comment -|in reply to|> post
        G.add_edge(comment['from']['id'], comment['id'], mtype = 'is author of') # user -|is author of|> comment

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

            if not nx.get_node_attributes(G, like['id']):
                G.add_node(
                    like['id'],
                    mtype = 'user',
                    fid = like['id'],
                    label = like.get('name','__NA__'),
                    url = "https://facebook.com/%s" % like['id'],
                    name = like.get('name','__NA__'),
                    about = '__NA__',
                    age_range = "0 - 99",
                    birthyear = '__NA__',
                    birthday = '__NA__',
                    cover = '__NA__',
                    education = '__NA__',
                    email = '__NA__',
                    gender = '__NA__',
                    hometown = '__NA__',
                    is_verified = '__NA__',
                    work = '__NA__'
                ) # user

            G.add_edge(like['id'], comment['id'], mtype = 'reacts to', reaction = 'LIKE') # user -|reacts to|> comment

            logging.info("++ LIKE: %s" % like['name'])

        replies = graph.get_all_connections(
            id = comment['id'],
            connection_name = "comments"
        )

        for reply in replies:

            logging.debug(reply)
            num_comments += 1

            G.add_node(
                reply['id'],
                mtype = 'comment',
                fid = reply['id'],
                label = reply.get('message','')[0:12]+'...',
                url = "https://facebook.com/%s/posts/%s/?comment_id=%s" % (post['from']['id'], post['id'].split('_')[1], reply['id']),
                message = reply.get('message',''),
                timestamp = reply.get('created_time','__NA__')
            ) # comment

            if not nx.get_node_attributes(G, reply['from']['id']):
                G.add_node(
                    reply['from']['id'],
                    mtype = 'user',
                    fid = reply['from']['id'],
                    label = reply['from'].get('name','__NA__'),
                    url = "https://facebook.com/%s" % reply['from']['id'],
                    name = reply['from'].get('name','__NA__'),
                    about = '__NA__',
                    age_range = "0 - 99",
                    birthyear = '__NA__',
                    birthday = '__NA__',
                    cover = '__NA__',
                    education = '__NA__',
                    email = '__NA__',
                    gender = '__NA__',
                    hometown = '__NA__',
                    is_verified = '__NA__',
                    work = '__NA__'
                ) # user

            G.add_edge(reply['id'], comment['id'], mtype = 'in reply to') # comment -|in reply to|> comment
            G.add_edge(reply['from']['id'], reply['id'], mtype = 'is author of') # user -|is author of|> comment

            logging.info("--- REPLY: %s" % reply.get('message',''))
            logging.info("+++ DATETIME: %s" % reply['created_time'])
            logging.info("+++ AUTHOR: %s" % reply['from']['name'])

            reply_likes = graph.get_all_connections(
                id = reply['id'],
                connection_name = "likes"
            )

            for like in reply_likes:

                logging.debug(like)
                num_reactions += 1

                if not nx.get_node_attributes(G, like['id']):
                    G.add_node(
                        like['id'],
                        mtype = 'user',
                        fid = like['id'],
                        label = like.get('name','__NA__'),
                        url = "https://facebook.com/%s" % like['id'],
                        name = like.get('name','__NA__'),
                        about = '__NA__',
                        age_range = "0 - 99",
                        birthyear = '__NA__',
                        birthday = '__NA__',
                        cover = '__NA__',
                        education = '__NA__',
                        email = '__NA__',
                        gender = '__NA__',
                        hometown = '__NA__',
                        is_verified = '__NA__',
                        work = '__NA__'
                    ) # user

                #G.add_edge('LIKE', reply['id']) # reaction <--> comment
                G.add_edge(like['id'], reply['id'], mtype = 'reacts to', reaction = 'LIKE') # user -|reacts to|> comment

                logging.info("+++ LIKE: %s" % like['name'])

G.graph['since'] = min([
    datetime.strptime(d['timestamp'].split('+')[0],fb_datetime_format)
    for n,d in G.nodes(data=True)
    if d['mtype'] == 'post'
]).strftime(fb_datetime_format)

G.graph['until'] = max([
    datetime.strptime(d['timestamp'].split('+')[0],fb_datetime_format)
    for n,d in G.nodes(data=True)
    if d['mtype'] == 'post'
]).strftime(fb_datetime_format)

logging.info("Statistics from %s to %s" % (G.graph['since'], G.graph['until']))
logging.info(
        "Members: %d | Posts: %d | Reactions: %d | Shares: %d | Comments: %d | Nodes: %d | Edges: %d" % (
        len(filter(lambda (n, d): d['mtype'] == 'user', G.nodes(data=True))),
        len(filter(lambda (n, d): d['mtype'] == 'post', G.nodes(data=True))),
        len(filter(lambda (n1, n2, d): d['mtype'] == 'reacts to', G.edges(data=True))),
        num_shares,
        len(filter(lambda (n, d): d['mtype'] == 'comment', G.nodes(data=True))),
        G.number_of_nodes(),
        G.number_of_edges()
    )
)

# node positioning algo
# http://networkx.readthedocs.io/en/latest/reference/drawing.html
try:
    if config.getboolean("Graph","calc_layout"):
        pos = nx.spring_layout(G) # Fruchterman-Reingold
        nx.set_node_attributes( G , 'x' , {str(k): float(v[0]) for k,v in pos.items()} )
        nx.set_node_attributes( G , 'y' , {str(k): float(v[1]) for k,v in pos.items()} )
except ImportError, e:
    logging.warning(e)
except ConfigParser.NoOptionError, e:
    pass

# export also in gexf format, supported by gephi
nx.write_gexf(G, file_name+".gexf")

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

