import facebook, logging, ConfigParser, sys
logging.basicConfig(level=logging.INFO)
from datetime import datetime

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
    group = graph.get_object(id = group_id)
except facebook.GraphAPIError, e:
    logging.error("Errors during connections to Facebook Graph API: %s." % e)

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

try:
    until_datetime = datetime.strptime(
        config.get("Datetime","until_datetime"),
        datetime_format
    )
except ConfigParser.NoOptionError, e:
    until_datetime = datetime.now()

posts = graph.get_all_connections(
    id = group_id,
    connection_name = "feed",
    fields = "id,message,from,updated_time"
)

for post in posts:

    #print post
    post_datetime = datetime.strptime(
            post['updated_time'][:19],
        fb_datetime_format
    )

    if post_datetime > until_datetime:
        continue

    if post_datetime < since_datetime:
        break

    logging.info("- %s" % post['message'])
    logging.info("+ DATETIME: %s" % post['updated_time'])
    logging.info("+ AUTHOR: %s" % post['from']['name'])

    #likes = graph.get_all_connections(
    #    id = post['id'],
    #    connection_name = "likes"
    #)
    #
    #for like in likes:
    #    #print like
    #    logging.info("++ LIKE: %s" % like['name'])

    post_reactions = graph.get_all_connections(
        id = post['id'],
        connection_name = "reactions"
    )

    for reaction in post_reactions:
        #print reaction
        logging.info("+ %s: %s" % ( reaction['type'] , reaction['name']))

    comments = graph.get_all_connections(
        id = post['id'],
        connection_name = "comments"
    )

    for comment in comments:

        #print comment
        logging.info("-- %s" % comment['message'])
        logging.info("++ DATETIME: %s" % comment['created_time'])
        logging.info("++ AUTHOR: %s" % comment['from']['name'])

        comment_likes = graph.get_all_connections(
            id = comment['id'],
            connection_name = "likes"
        )

        for like in comment_likes:
            #print like
            logging.info("++ LIKE: %s" % like['name'])

        responses = graph.get_all_connections(
            id = comment['id'],
            connection_name = "comments"
        )

        for response in responses:

            #print response
            logging.info("--- %s" % response['message'])
            logging.info("+++ DATETIME: %s" % response['created_time'])
            logging.info("+++ AUTHOR: %s" % response['from']['name'])

            response_likes = graph.get_all_connections(
                id = response['id'],
                connection_name = "likes"
            )

            for like in response_likes:
                #print like
                logging.info("+++ LIKE: %s" % like['name'])

