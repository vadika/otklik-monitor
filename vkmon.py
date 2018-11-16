import requests
import vk_requests
import yaml
import re
import argparse
import logging

logging.basicConfig(level=logging.INFO)


class Config:
    vk_bot_key = ""
    tg_bot_key = ""
    tg_chat_id = ""
    poll = ""

    group_name = ""
    group_id = ""
    keywords = ""


conf = Config

conf_file = "app_config.yml"
tg_conf_file = "_telegram.yml"
kw_conf_file = "_keywords.yml"


def parseConfig():
    with open(conf_file, 'r') as ymlfile:
        cfg = yaml.load(ymlfile)

    conf.vk_bot_key = cfg['connect']['vk_bot_key']
    conf.poll = cfg['connect']['poll']

    conf.group_name = cfg['info']['group_name']
    conf.group_id = cfg['info']['group_id']

    with open(kw_conf_file, 'r') as ymlfile:
        cfg = yaml.load(ymlfile)

    conf.keywords = cfg['keywords']

    with open(tg_conf_file, 'r') as ymlfile:
        cfg = yaml.load(ymlfile)

    conf.tg_bot_key = cfg['tg_bot_key']
    conf.tg_chat_id = cfg['tg_chat_id']

    return


def tg_get_updates_json(request):
    response = requests.get(request + 'getUpdates')
    return response.json()


def tg_last_update(data):
    # pprint(data)
    results = data['result']
    total_updates = len(results) - 1
    return results[total_updates]


def tg_get_chat_id(update):
    chat_id = update['message']['chat']['id']
    return chat_id


def tg_send_mess(chat, text, silent=False, no_preview=False, parse="Markdown"):
    params = {'chat_id': chat, 'text': text, 'disable_notification': silent, 'disable_web_page_preview': no_preview,
              "parse_mode": parse}
    response = requests.post(tg_url + 'sendMessage', data=params)
    return response


# supplementary functions

def strstrip(s, count):
    s = s.replace("\r", "")
    s = s.replace("\n", "")
    w = s.split(" ")
    logging.debug("str len" + str(len(w)))
    # if len(w) < count:
    #     return s
    # else:
    return ' '.join(w[0:count - 1])


# digest functions
def digest_truncate(digest_name):
    with open(str(digest_name)+".digest", "w") as f:
        f.close()

def digest_append(digest_name, record):
    with open(str(digest_name)+".digest", "a") as f:
        f.write(record)
        f.close()

def digest_load(digest_name):
    with open(str(digest_name) + ".digest", "r") as f:
        buf = f.read()
        f.close()
        return buf


# parse arguments : --init, --conf, --test

parser = argparse.ArgumentParser(description='vkontakte data analyzer (c) 2018 otklik.team')

# Don't forget to parse arguments

parser.add_argument('--init', action='store_true',
                    help='Initialize parameters from VK and tg')

parser.add_argument('--conf', type=str, nargs='?',
                    help='Specify config file (default app_config.yml)')

parser.add_argument('--test', action='store_true',
                    help='Test run (do not post anything, do not move counters)')

parser.add_argument('--loud', action='store_true',
                    help='Publish all records, not only positive ')

parser.add_argument('--digest', action='store_true',
                    help='Publish and rotate digest ')

args = parser.parse_args()

if (args.conf):
    conf_file = args.conf

# parse config
parseConfig()

tg_url = "https://api.telegram.org/bot" + conf.tg_bot_key + "/"

logging.info("Filtering by keywords = " + conf.keywords)

# prepare VK api

api = vk_requests.create_api(service_token=conf.vk_bot_key)
group = api.groups.getById(group_id=conf.group_id)

group_id = group[0]["id"]
logging.info("VK group id = " + str(group_id))

# main loop

posts = api.wall.get(owner_id="-" + str(group_id), count=1)
logging.info("Current post count = " + str(posts["count"]))

# state={}
# state["posts"] = [1,2]

if (args.init):
    with open(conf.group_id + "-state.yml", 'w') as ymlfile:
        yaml.dump({"lastcount": posts["count"], "posts": []}, ymlfile)

with open(conf.group_id + "-state.yml", 'r') as ymlfile:
    state = yaml.load(ymlfile)

logging.info("Last run post count = " + str(state["lastcount"]))

posts_pending = posts["count"] - state["lastcount"]

# protection against post deletion
if posts_pending < 0:
    logging.info("Negative post count, looks like some posts were deleted")
    posts_pending = 0

# protection against long pause in sync
if posts_pending > 99:
    logging.info("Too many unsynced posts, resetting to last 50")
    posts_pending = 50

state_new = []

if (posts_pending) > 0:
    logging.info("Messages pending to process " + str(posts_pending))
    posts = api.wall.get(owner_id="-" + str(group_id), count=50)

    for i in range(0, posts_pending):

        post = posts["items"][i]
        post_id = post["id"]

        # duplicate or pinned post protection
        state_new.append(post_id)
        logging.debug("!!! {}", state_new)

        if post_id in state["posts"]:
            logging.info("duplicate " + str(post_id))
            posts["items"].pop(i)
            post = posts["items"][i]
            post_id = post["id"]
            state_new.append(post_id)
            logging.debug("??? {}", state_new)

        logging.info(post["text"])
        logging.info(post["id"])

        # send message to tg

        key_flag = False
        key_word = ""
        pattern = re.compile("^\s+|\s*,\s*|\s+$")
        for x in pattern.split(conf.keywords):
            if re.search(x, post["text"], re.IGNORECASE):
                key_flag = True
                key_word = x

        # tg_chat_id = tg_get_chat_id(tg_last_update(tg_get_updates_json(tg_url)))

        tg_chat_id = conf.tg_chat_id


        digest_append(conf.group_id, str("ДА " if key_flag else "НЕТ ") + 'https://vk.com/' + conf.group_id + '?w=wall-' + str(
                                 group_id) + '_' + str(post_id) + " -- " + strstrip(post["text"], 30) + "\n")


        if args.test:
            continue

        if key_flag:
            tg_send_mess(tg_chat_id,
                         "*ДА " + key_word + " [" + conf.group_name + '](https://vk.com/' + conf.group_id + '?w=wall-' + str(
                             group_id) + '_' + str(
                             post_id) + ") *")
        else:
            if args.loud:
                tg_send_mess(tg_chat_id,
                             "НЕТ [" + conf.group_name + '](https://vk.com/' + conf.group_id + '?w=wall-' + str(
                                 group_id) + '_' + str(post_id) + ') -- ' + strstrip(post["text"], 12), silent=True,
                             no_preview=True)

        if not args.test:
            with open(conf.group_id + "-state.yml", 'w') as ymlfile:
                if len(state_new) == 0:
                    state_new = state["posts"]
                yaml.dump({"lastcount": posts["count"], "posts": state_new}, ymlfile)
