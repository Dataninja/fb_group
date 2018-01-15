# -*- coding: utf-8 -*-
import facebook, logging, ConfigParser, sys, json, re
logging.basicConfig(level=logging.INFO)
import unicodecsv as csv
from datetime import datetime
from urlparse import urlparse
import tldextract
import networkx as nx

fb_datetime_format = "%Y-%m-%dT%H:%M:%S" # 2017-03-21T14:18:11+0000
fb_hashtag_regex = re.compile( u"#(?:\[[^\]]+\]|\S+)" , re.UNICODE )
fb_url_regex = re.compile( u"(?:(?:https?|ftp)://[^ ]+)" , re.UNICODE )

if len(sys.argv) > 1:
    config_file = sys.argv[1]
else:
    logging.error( "Please provide a configuration file." )
    exit()

config = ConfigParser.SafeConfigParser({
    "datetime_format": "%Y-%m-%d %H:%M:%S",
    "mode": "archive",
    "all_members": False,
    "calc_layout": False,
    "prepend_datetime": True
})

try:
    config.read(config_file)
except Exception, e:
    logging.error( "Provided configuration file is missing or wrong." )
    exit()

try:
    access_token = config.get( "Auth" , "access_token" )
except ConfigParser.NoOptionError, e:
    logging.warning( "Missing access_token, I'll try to use app_id and app_secret instead." )
    try:
        app_id = config.get( "Auth" , "app_id" )
        app_secret = config.get( "Auth" , "app_secret" )
        access_token = "%s|%s" % ( app_id , app_secret )
    except ConfigParser.NoOptionError, e:
        logging.error( "No auth token provided." )
        exit()

graph = facebook.GraphAPI(
    access_token = access_token,
    version = "2.11"
)

try:
    group_id = config.get( "Group" , "id" )
except ConfigParser.NoOptionError, e:
    logging.error( "No group id provided." )
    exit()

try:
    group = graph.get_object(
        id = group_id,
        fields = "id,name,updated_time"
    )
    logging.info( "Group: %s" % group['name'] )
except facebook.GraphAPIError, e:
    logging.error( "Errors during connections to Facebook Graph API: %s." % e )
    exit()

datetime_format = config.get( "Datetime" , "datetime_format" )
mode = config.get( "Graph" , "mode" )

try:
    until_datetime = datetime.strptime(
        config.get( "Datetime" , "until_datetime" ),
        datetime_format
    )
except ConfigParser.NoOptionError, e:
    until_datetime = datetime.now()

if mode == "update":

    try:
        file_name = config.get( "Graph" , "file_name" ).split('.')[0]
    except ConfigParser.NoOptionError, e:
        logging.error( "Please provide a valid graph file in update mode." )
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

elif mode == "archive":

    try:
        if config.getboolean( "Graph" , "prepend_datetime" ):
            file_name = "%s_%s" % ( datetime.now().strftime( "%Y%m%d%H%M" ) , config.get( "Graph" , "file_name" ).split('.')[0] )
        else:
            file_name = "%s" % config.get( "Graph" , "file_name" ).split('.')[0]
    except ConfigParser.NoOptionError, e:
        file_name = "%s_%s" % ( datetime.now().strftime( "%Y%m%d%H%M" ) , group['name'] )

    G = nx.DiGraph()

    G.graph['name'] = group['name']
    G.graph['url'] = "https://www.facebook.com/groups/%s/" % group['id']
    G.graph['timestamp'] = group['updated_time']

    try:
        since_datetime = datetime.strptime(
            config.get( "Datetime" , "since_datetime" ),
            datetime_format
        )
    except ConfigParser.NoOptionError, e:
        since_datetime = datetime.fromtimestamp(0)

G.graph['last_update'] = datetime.now().strftime(fb_datetime_format)

# Group members: https://developers.facebook.com/docs/graph-api/reference/v2.11/group/members
num_members = 0
try:
    if config.getboolean("Graph","all_members"):
        logging.info("Download all members list from %s to %s" % ( since_datetime , until_datetime ))
        members = graph.get_all_connections(
            id = group_id,
            connection_name = "members",
            fields = "id,name"
        )
    else:
        members = []
except ConfigParser.NoOptionError, e:
    members = []

if members:
    with open(file_name+'_members.csv','w') as f:
        writer = csv.DictWriter(f, fieldnames = ['id','name','url'], encoding='utf-8')
        writer.writeheader()
        for m in members:
            member = graph.get_object(
                id = m['id'],
                fields = 'id,name'
            )
            writer.writerow({
                'id': member['id'],
                'name': member.get('name',''),
                'url': 'https://www.facebook.com/'+member['id']
            })


exit()

def add_user(graph, user):

    logging.info( "- MEMBER: %s" % user.get('name','__NA__') )

    user_age_range = user.get('age_range',{})

    graph.add_node(
        user['id'],
        mtype = 'user',
        fid = user['id'],
        label = user.get('name','__NA__'),
        url = "https://facebook.com/%s" % user['id'],
        name = user.get('name','__NA__'),
        about = user.get('about','__NA__'),
        age_range = "%d - %d" % ( user_age_range.get('min',0) , user_age_range.get('max',99) ),
        birthyear = user.get('birthday','__NA__/__NA__/__NA__').split('/')[-1],
        birthday = user.get('birthday','__NA__'),
        cover = user.get('cover',{}).get('source','__NA__'),
        education = user.get('education',[{}])[0].get('degree',{}).get('link','__NA__'),
        email = user.get('email','__NA__'),
        gender = user.get('gender','__NA__'),
        hometown = user.get('hometown',{}).get('link','__NA__'),
        is_verified = user.get('is_verified','__NA__'),
        work = user.get('work',[{}])[0].get('position',{}).get('link','__NA__')
    ) # user

def add_domain(graph, link, post):

    uri = urlparse(link)
    tld = tldextract.extract("{uri.netloc}".format(uri=uri))

    graph.add_node(
        tld.registered_domain,
        mtype = 'domain',
        label = tld.registered_domain,
        url = "%s://%s/" % ( uri.scheme , tld.registered_domain )
    ) # domain

    graph.add_edge(
        post['id'],
        tld.registered_domain,
        mtype = 'mentions',
        domain = "{uri.netloc}".format(uri=uri),
        resource = "{uri.scheme}://{uri.netloc}{uri.path}".format(uri=uri),
        url = link
    ) # post -|mentions|> domain

def add_post(graph, post):

    logging.info( "- POST: %s" % post.get('message','') )
    logging.info( "+ DATETIME: %s" % post['updated_time'] )
    logging.info( "+ AUTHOR: %s" % post['from']['name'] )

    graph.add_node(
        post['id'],
        mtype = 'post',
        fid = post['id'],
        label = post.get('message','')[0:12]+'...',
        url = "https://facebook.com/%s/posts/%s" % (
            post['from']['id'],
            post['id'].split('_')[1]
        ),
        message = post.get('message',''),
        hashtags = json.dumps(re.findall( fb_hashtag_regex , post.get('message','') )),
        timestamp = post.get('updated_time','__NA__')
    ) # post

    links = re.findall( fb_url_regex , post.get('message','') )
    logging.debug(links)
    for link in links:
        add_domain(graph, link, post)

def add_comment(graph, comment, post):

    logging.info( "-- COMMENT: %s" % comment.get('message','') )
    logging.info( "++ DATETIME: %s" % comment['created_time'] )
    logging.info( "++ AUTHOR: %s" % comment['from']['name'] )

    graph.add_node(
        comment['id'],
        mtype = 'comment',
        fid = comment['id'],
        label = comment.get('message','')[0:12]+'...',
        url = "https://facebook.com/%s/posts/%s/?comment_id=%s" % (
            post['from']['id'],
            post['id'].split('_')[1],
            comment['id']
        ),
        message = comment.get('message',''),
        hashtags = json.dumps(re.findall( fb_hashtag_regex , comment.get('message','') )),
        timestamp = comment.get('created_time','__NA__')
    ) # comment

    links = re.findall( fb_url_regex , comment.get('message','') )
    logging.debug(links)
    for link in links:
        add_domain(graph, link, comment)

def add_reaction(graph, reaction, post):

    if not nx.get_node_attributes( graph , reaction['id'] ):
        add_user( graph , reaction )

    graph.add_edge(
        reaction['id'],
        post['id'],
        mtype = 'reacts to',
        reaction = reaction['type']
    ) # user -|reacts to|> post

    logging.info( "+ %s: %s" % ( reaction['type'] , reaction['name'] ) )

for member in members:

    logging.debug(member)
    num_members += 1

    add_user(G,member)

logging.info( "Download graph from %s to %s" % ( since_datetime , until_datetime ))

posts = graph.get_all_connections(
    id = group_id,
    connection_name = "feed",
    fields = "id,message,from,updated_time,to,link",
    since = int((since_datetime - datetime(1970, 1, 1)).total_seconds()),
    until = int((until_datetime - datetime(1970, 1, 1)).total_seconds())
)

num_posts = 0
num_shares = 0
num_reactions = 0
num_mentions = 0
num_comments = 0
for post in posts:

    logging.debug(post)
    num_posts += 1

    add_post( G , post )

    if not nx.get_node_attributes( G , post['from']['id'] ):
        add_user( G , post['from'] )

    G.add_edge(
        post['from']['id'],
        post['id'],
        mtype = 'is author of'
    ) # user -|is author of|> post

    for mention in post.get('to',{}).get('data',[]):

        logging.debug(mention)

        if mention['id'] == group['id']:
            continue

        num_mentions += 1

        if not nx.get_node_attributes( G , mention['id'] ):
            add_user( G , mention )

        G.add_edge(
            post['id'],
            mention['id'],
            mtype = 'mentions'
        ) # post -|mentions|> user

        logging.info( "++ MENTIONS: %s" % mention.get('name','__NA__') )

    shares = graph.get_all_connections(
        id = post['id'],
        connection_name = "sharedposts",
        fields = "id,from"
    )

    for share in shares:

        logging.debug(share)
        num_shares += 1

        if not nx.get_node_attributes( G , share['from']['id'] ):
            add_user( G , share['from'] )

        G.add_edge(
            share['from']['id'],
            post['id'],
            mtype = 'reacts to',
            reaction = 'SHARE'
        ) # user -|reacts to|> post

        logging.info( "++ SHARE: %s" % share['from']['name'] )

    post_reactions = graph.get_all_connections(
        id = post['id'],
        connection_name = "reactions"
    )

    for reaction in post_reactions:

        logging.debug(reaction)
        num_reactions += 1

        add_reaction( G , reaction , post )

    comments = graph.get_all_connections(
        id = post['id'],
        connection_name = "comments",
        fields = "id,message,from,created_time,message_tags"
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

        add_comment( G , comment , post )

        if not nx.get_node_attributes( G , comment['from']['id'] ):
            add_user( G , comment['from'] )

        G.add_edge(
            comment['id'],
            post['id'],
            mtype = 'in reply to'
        ) # comment -|in reply to|> post

        G.add_edge(
            comment['from']['id'],
            comment['id'],
            mtype = 'is author of'
        ) # user -|is author of|> comment

        for mention in comment.get('message_tags',[]):

            logging.debug(mention)

            if mention['id'] == group['id']:
                continue

            num_mentions += 1

            if not nx.get_node_attributes( G , mention['id'] ):
                add_user( G , mention )

            G.add_edge(
                comment['id'],
                mention['id'],
                mtype = 'mentions'
            ) # comment -|mentions|> user

            logging.info( "++ MENTIONS: %s" % mention.get('name','__NA__') )

        comment_reactions = graph.get_all_connections(
            id = comment['id'],
            connection_name = "reactions"
        )

        for reaction in comment_reactions:

            logging.debug(reaction)
            num_reactions += 1

            add_reaction( G , reaction , comment )

        replies = graph.get_all_connections(
            id = comment['id'],
            connection_name = "comments",
            fields = "id,message,from,created_time,message_tags"
        )

        for reply in replies:

            logging.debug(reply)
            num_comments += 1

            add_comment( G , reply , post)

            if not nx.get_node_attributes( G , reply['from']['id'] ):
                add_user( G , reply['from'] )

            G.add_edge(
                reply['id'],
                comment['id'],
                mtype = 'in reply to'
            ) # comment -|in reply to|> comment

            G.add_edge(
                reply['from']['id'],
                reply['id'],
                mtype = 'is author of'
            ) # user -|is author of|> comment

            for mention in reply.get('message_tags',[]):

                logging.debug(mention)

                if mention['id'] == group['id']:
                    continue

                num_mentions += 1

                if not nx.get_node_attributes( G , mention['id'] ):
                    add_user( G , mention )

                G.add_edge(
                    reply['id'],
                    mention['id'],
                    mtype = 'mentions'
                ) # comment -|mentions|> user

                logging.info( "++ MENTIONS: %s" % mention.get('name','__NA__') )

            reply_reactions = graph.get_all_connections(
                id = reply['id'],
                connection_name = "reactions"
            )

            for reaction in reply_reactions:

                logging.debug(reaction)
                num_reactions += 1

                add_reaction( G , reaction , reply )

G.graph['since'] = min([
    datetime.strptime( d['timestamp'].split('+')[0] , fb_datetime_format )
    for n,d in G.nodes(data=True)
    if d['mtype'] == 'post'
]).strftime(fb_datetime_format)

G.graph['until'] = max([
    datetime.strptime( d['timestamp'].split('+')[0] , fb_datetime_format )
    for n,d in G.nodes(data=True)
    if d['mtype'] == 'post'
]).strftime(fb_datetime_format)

logging.info( "Statistics from %s to %s" % ( G.graph['since'] , G.graph['until'] ) )
logging.info(
        "Members: %d | Posts: %d | Reactions: %d | Shares: %d | Mentions: %d | Comments: %d | Nodes: %d | Edges: %d" % (
        len(filter(lambda (n, d): d['mtype'] == 'user', G.nodes(data=True))),
        len(filter(lambda (n, d): d['mtype'] == 'post', G.nodes(data=True))),
        len(filter(lambda (n1, n2, d): d['mtype'] == 'reacts to', G.edges(data=True))),
        num_shares,
        len(filter(lambda (n1, n2, d): d['mtype'] == 'mentions', G.edges(data=True))),
        len(filter(lambda (n, d): d['mtype'] == 'comment', G.nodes(data=True))),
        G.number_of_nodes(),
        G.number_of_edges()
    )
)

# node positioning algo
# http://networkx.readthedocs.io/en/latest/reference/drawing.html
try:
    if config.getboolean( "Graph" , "calc_layout" ):
        pos = nx.spring_layout(G) # Fruchterman-Reingold
        nx.set_node_attributes( G , 'x' , {str(k): float(v[0]) for k,v in pos.items()} )
        nx.set_node_attributes( G , 'y' , {str(k): float(v[1]) for k,v in pos.items()} )
except ImportError, e:
    logging.warning(e)

# export also in gexf format, supported by gephi
nx.write_gexf( G , file_name+".gexf" )

from networkx.readwrite import json_graph
# node_link_data() sets links' target and source to nodes' indices in nodes array,
# not to real nodes' ids... this workaround fix this issue
json_data = json_graph.node_link_data(G)
for i,l in enumerate(json_data['links']):
    json_data['links'][i]['target'] = json_data['nodes'][l['target']]['id']
    json_data['links'][i]['source'] = json_data['nodes'][l['source']]['id']
for i,n in enumerate(json_data['nodes']):
#    if 'links' in json_data['nodes'][i]:
#        json_data['nodes'][i]['links'] = json.loads(json_data['nodes'][i]['links'])
    if 'hashtags' in json_data['nodes'][i]:
        json_data['nodes'][i]['hashtags'] = json.loads(json_data['nodes'][i]['hashtags'])
# end workaround
with open(file_name+".json",'w') as f:
    json.dump(json_data, f)

