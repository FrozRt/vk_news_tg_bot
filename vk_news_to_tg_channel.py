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
DOMAIN0 = (config.get('VK', 'VK_DOMAIN')).split(', ')
LAST_ID0 = (config.get('Settings', 'LAST_ID')).split(', ')
COUNT = config.get('VK', 'VK_ARTICLES_COUNT')
BOT_TOKEN = config.get('Telegram', 'BOT_TOKEN')
CHANNEL = config.get('Telegram', 'TG_CHANNEL')
INCLUDE_LINK = config.getboolean('Settings', 'INCLUDE_LINK')
PREVIEW_LINK = config.getboolean('Settings', 'PREVIEW_LINK')
VK_TOKEN = config.get('VK', 'TOKEN', fallback=None)


bot = telebot.TeleBot(BOT_TOKEN)


def auth_handler():
    """ При двухфакторной аутентификации вызывается эта функция.
    """

    # Код двухфакторной аутентификации
    key = input("Enter authentication code: ")
    # Если: True - сохранить, False - не сохранять.
    remember_device = True

    return key, remember_device

# Получаем данные из vk.com
def vk_news_sender():
    i = 0
    temp_container_for_last_ids = []
    while i < len(DOMAIN0):
        DOMAIN = DOMAIN0[i]
        LAST_ID = int(LAST_ID0[i].strip("''"))
        check_posts_vk(DOMAIN, LAST_ID)
        sleep(0.5)
        i += 1
        temp_container_for_last_ids.append(config.get('Settings', 'LAST_ID'))
    config.set('Settings', 'LAST_ID', str(temp_container_for_last_ids).strip('[]'))
    with open(config_path, "w") as config_file:
        config.write(config_file)


def get_data(domain_vk, vk_articles_count):
    global LOGIN
    global PASSWORD
    global VK_TOKEN
    global config
    global config_path

    if VK_TOKEN is not None:
        vk_session = vk_api.VkApi(LOGIN, PASSWORD, VK_TOKEN)
        vk_session.auth(token_only=True)
    else:
        vk_session = vk_api.VkApi(LOGIN, PASSWORD, auth_handler=auth_handler)
        vk_session.auth()

    new_token = vk_session.token['access_token']
    if VK_TOKEN != new_token:
        VK_TOKEN = new_token
        config.set('VK', 'TOKEN', new_token)
        with open(config_path, "w") as config_file:
            config.write(config_file)

    vk = vk_session.get_api()
    # Используем метод wall.get из документации по API vk.com
    response = vk.wall.get(domain=domain_vk, count=vk_articles_count)
    return response


#  Проверяем данные по условиям перед отправкой
def check_posts_vk(DOMAIN, LAST_ID):
    response = get_data(DOMAIN, COUNT)
    print(response)
    response = reversed(response['items'])

    for post in response:
        # Сравниваем id, пропускаем уже опубликованные
        if 'is_pinned' in post:
            print(f"The post {post['id']} is pinned")
            continue
        if int(post['id']) <= LAST_ID:
            config.set('Settings', 'LAST_ID', str(post['id']))
            with open(config_path, "w") as config_file:
                config.write(config_file)
            continue

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

        # Записываем id в файл
        config.set('Settings', 'LAST_ID', str(post['id']))
        with open(config_path, "w") as config_file:
            config.write(config_file)


# Символы, на которых можно разбить сообщение
message_breakers = [':', ' ', '\n']
max_message_length = 4091


# Текст
def send_posts_text(text):
    global CHANNEL
    global PREVIEW_LINK
    global bot

    if text == '':
        print('no text')
    else:
        # В телеграмме есть ограничения на длину одного сообщения в 4091 символ, разбиваем длинные сообщения на части
        for msg in split(text):
            bot.send_message(
                CHANNEL, msg, disable_web_page_preview=not PREVIEW_LINK)


def split(text):
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
