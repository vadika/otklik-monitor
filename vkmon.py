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
    poll = ""

    group_name = ""
    group_id = ""
    keywords = ""


conf = Config

conf_file = "app_config.yml"


def parseConfig():
    with open(conf_file, 'r') as ymlfile:
        cfg = yaml.load(ymlfile)

    conf.vk_bot_key = cfg['connect']['vk_bot_key']
    conf.tg_bot_key = cfg['connect']['tg_bot_key']
    conf.poll = cfg['connect']['poll']

    conf.group_name = cfg['info']['group_name']
    conf.group_id = cfg['info']['group_id']
    conf.keywords = cfg['info']['keywords']

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


def tg_send_mess(chat, text):
    params = {'chat_id': chat, 'text': text}
    response = requests.post(tg_url + 'sendMessage', data=params)
    return response


# parse arguments : --init, --conf, --test

parser = argparse.ArgumentParser(description='vkontakte data analyzer (c) 2018 otklik.team')

# Don't forget to parse arguments

parser.add_argument('--init', action='store_true',
                    help='Initialize parameters from VK and tg')

parser.add_argument('--conf', type=str, nargs='?',
                    help='Specify config file (default app_config.yml)')

parser.add_argument('--test', action='store_true',
                    help='Test run (do not post anything, do not move counters)')

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
        print("!!! {}", state_new)

        if post_id in state["posts"]:
            logging.info("duplicate " + str(post_id))
            posts["items"].pop(i)
            post = posts["items"][i]
            post_id = post["id"]
            state_new.append(post_id)
            print("??? {}", state_new)

        logging.info(post["text"])
        logging.info(post["id"])

        # send message to tg

        key_flag = False
        pattern = re.compile("^\s+|\s*,\s*|\s+$")
        for x in pattern.split(conf.keywords):
            if re.search(x, post["text"], re.IGNORECASE):
                key_flag = True

        tg_chat_id = tg_get_chat_id(tg_last_update(tg_get_updates_json(tg_url)))

        if args.test:
            continue

        if key_flag:
            tg_send_mess(tg_chat_id,
                         "ДА " + conf.group_name + ' -- https://vk.com/' + conf.group_id + '?w=wall-' + str(
                             group_id) + '_' + str(
                             post_id))
        else:
            tg_send_mess(tg_chat_id,
                         "НЕТ " + conf.group_name + ' -- https://vk.com/' + conf.group_id + '?w=wall-' + str(
                             group_id) + '_' + str(
                             post_id))

if not args.test:
    with open(conf.group_id + "-state.yml", 'w') as ymlfile:
        if len(state_new) == 0:
            state_new = state["posts"]
        yaml.dump({"lastcount": posts["count"], "posts": state_new}, ymlfile)
