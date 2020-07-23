import os
import sys
import vk_api
import telebot
import configparser
from time import sleep

config_path = os.path.join(sys.path[0], 'settings.ini')
config = configparser.ConfigParser()
config.read(config_path)
LOGIN = config.get('VK', 'VK_LOGIN')
PASSWORD = config.get('VK', 'VK_PASSWORD')
DOMAIN_LIST = (config.get('VK', 'VK_DOMAIN')).split(', ')
LAST_ID_LIST = (config.get('Settings', 'LAST_ID')).split(', ')
COUNT = config.get('VK', 'VK_ARTICLES_COUNT')
BOT_TOKEN = config.get('Telegram', 'BOT_TOKEN')
CHANNEL = config.get('Telegram', 'TG_CHANNEL')
INCLUDE_LINK = config.getboolean('Settings', 'INCLUDE_LINK')
PREVIEW_LINK = config.getboolean('Settings', 'PREVIEW_LINK')
VK_TOKEN = config.get('VK', 'TOKEN', fallback=None)

# Контейнер для временного хранения последних id постов для последующей их записи в .ini-файл
temp_container_for_last_ids = []

bot = telebot.TeleBot(BOT_TOKEN)


def vk_news_sender():
    """Проверяет каждое сообщество из списка на наличие обновлений"""
    i = 0
    while i < len(DOMAIN_LIST):
        DOMAIN = DOMAIN_LIST[i]
        LAST_ID = int(LAST_ID_LIST[i].strip("''"))
        check_posts_vk(DOMAIN, LAST_ID)
        sleep(0.5)
        i += 1
    config.set('Settings', 'LAST_ID', str(temp_container_for_last_ids).strip('[]'))
    with open(config_path, "w") as config_file:
        config.write(config_file)


def get_data(domain_vk, vk_articles_count):
    """Получает данные через VK API"""
    global LOGIN
    global PASSWORD
    global VK_TOKEN
    global config
    global config_path

    vk_session = vk_api.VkApi(LOGIN, PASSWORD, VK_TOKEN)
    vk = vk_session.get_api()
    # Используем метод wall.get из документации по API vk.com
    response = vk.wall.get(domain=domain_vk, count=vk_articles_count)
    return response


def check_posts_vk(DOMAIN, LAST_ID):
    """Проверяет данные по условиям перед отправкой"""
    global temp_container_for_last_ids
    response = get_data(DOMAIN, COUNT)
    print(response)
    response = reversed(response['items'])
    temp_post_id_list = []
    for post in response:
        # Пропускаем закрепленные посты
        if 'is_pinned' in post:
            print(f"The post {post['id']} is pinned")
            temp_post_id_list.append(post['id'])
            continue
        # Сравниваем id, пропускаем уже опубликованные
        if int(post['id']) <= LAST_ID:
            temp_post_id_list.append(post['id'])
            continue
        temp_post_id_list.append(post['id'])
        print('-----------------------------------------')
        print(post)

        # Текст
        text = post['text']

        # Проверяем есть ли что то прикрепленное к посту
        images = []
        links = []
        attachments = []
        if 'attachments' in post:
            attach = post['attachments']
            for add in attach:
                if add['type'] == 'photo':
                    img = add['photo']
                    images.append(img)
                elif add['type'] == 'audio':
                    # Все аудиозаписи заблокированы везде, кроме оффицальных приложений
                    continue
                elif add['type'] == 'video':
                    video = add['video']
                    if 'player' in video:
                        links.append(video['player'])
                else:
                    for (key, value) in add.items():
                        if key != 'type' and 'url' in value:
                            attachments.append(value['url'])

        if INCLUDE_LINK:
            post_url = "https://vk.com/" + DOMAIN + "?w=wall" + \
                       str(post['owner_id']) + '_' + str(post['id'])
            links.insert(0, post_url)
        text = '\n'.join([text] + links)
        send_posts_text(text)
    temp_container_for_last_ids.append(max(temp_post_id_list))


# Символы, на которых можно разбить сообщение
message_breakers = [':', ' ', '\n']
max_message_length = 4091


def send_posts_text(text):
    global CHANNEL
    global PREVIEW_LINK
    global bot

    if text == '':
        print('no text')
    else:
        for msg in split(text):
            bot.send_message(
                CHANNEL, msg, disable_web_page_preview=not PREVIEW_LINK)


def split(text):
    """
    В телеграмме есть ограничения на длину одного сообщения в 4091 символ, разбиваем длинные
    сообщения на части
    """
    global message_breakers
    global max_message_length

    if len(text) >= max_message_length:
        last_index = max(
            map(lambda separator: text.rfind(separator, 0, max_message_length), message_breakers))
        good_part = text[:last_index]
        bad_part = text[last_index + 1:]
        return [good_part] + split(bad_part)
    else:
        return [text]


if __name__ == '__main__':
    vk_news_sender()
