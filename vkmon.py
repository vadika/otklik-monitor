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


def parseConfig():
    with open("app_config.yml", 'r') as ymlfile:
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


# parse config
parseConfig()

tg_url = "https://api.telegram.org/bot" + conf.tg_bot_key + "/"

logging.info(conf.keywords)

# parse arguments : --init, --conf

# prepare VK api

api = vk_requests.create_api(service_token=conf.vk_bot_key)
group = api.groups.getById(group_id=conf.group_id)

group_id = group[0]["id"]
logging.info("VK group id = "+str(group_id))

# main loop

posts = api.wall.get(owner_id="-" + str(group_id), count=1)
logging.info("Current post count = " + str(posts["count"]))

with open(conf.group_id + ".yml", 'r') as ymlfile:
    cfg = yaml.load(ymlfile)

logging.info("Last run post count = " + str(cfg["lastcount"]))

posts_pending = posts["count"] - cfg["lastcount"]

if (posts_pending) > 0:
    logging.info("Messages pending to process " + str(posts_pending))
    posts = api.wall.get(owner_id="-" + str(group_id), count=posts_pending + 1)

    for post in posts["items"]:
        logging.info(post["text"])
        logging.info(post["id"])
        post_id = post["id"]
        # send message to tg

        key_flag = False
        pattern = re.compile("^\s+|\s*,\s*|\s+$")
        for x in pattern.split(conf.keywords):
            if x in post["text"]:
                key_flag = True

        tg_chat_id = tg_get_chat_id(tg_last_update(tg_get_updates_json(tg_url)))

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

with open(conf.group_id + ".yml", 'w') as ymlfile:
    yaml.dump({"lastcount": posts["count"]}, ymlfile)
