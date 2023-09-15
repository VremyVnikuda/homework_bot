import os
import time
import logging
import sys
from http import HTTPStatus

import requests
from telegram import Bot
from dotenv import load_dotenv

from exceptions import MissedTokenError, ConnectionError


load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler(sys.stdout)
logger.addHandler(handler)
formatter = logging.Formatter('%(asctime)s, %(levelname)s, %(message)s')
handler.setFormatter(formatter)


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    logger.debug("Отправляю сообщение в телеграм")
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
    except Exception as error:
        logger.error(f'Ошибка при отправке сообщения: {error}')


def get_api_answer(current_timestamp):
    """Делает запрос к API и возвращает преобразованный из JSON словарь."""
    logger.debug("Отправляю запрос к эндпоинту")
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        logger.debug(f"Отправлен запрос на {ENDPOINT}")
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
        if response.status_code != HTTPStatus.OK:
            raise ConnectionError(
                f'Ответ не получен,код ошибки: {response.status_code}')
        logger.debug("Ответ от API успешно получен")
        try:
            return response.json()
        except Exception as error:
            raise Exception(f'Формат полученного ответа - не JSON: {error}')
    except Exception as error:
        raise Exception(f'Ошибка при попытке подключения к эндпоинту: {error}')


def check_response(response):
    """Проверяет ответ API и возвращает список домашних работ."""
    logger.debug("Проверяю, все ли ок с ответом API")
    if not isinstance(response, dict):
        raise TypeError('Ответ, полученный от API, не является словарем')
    if 'homeworks' not in response:
        raise KeyError('В ответе API нет ключа "homeworks"')
    if not isinstance(response['homeworks'], list):
        raise TypeError('Значение по ключу "homeworks" не является списком')
    if 'current_date' not in response:
        raise KeyError('В ответе API нет ключа "current_date"')
    if not isinstance(response['current_date'], int):
        raise TypeError('Значение по ключу "current_date" некорректно')
    logger.debug("Данные о домашних работах получены")
    return response['homeworks']


def parse_status(homework):
    """Определяет и возвращает статус домашней работы."""
    logger.debug("Проверяю статус домашки")
    if not isinstance(homework, dict):
        raise TypeError('Данные о домашке не являются словарем')
    if 'homework_name' not in homework:
        raise KeyError('В данных о домашке нет ключа "homework_name"')
    if 'status' not in homework:
        raise KeyError('В данных о домашке нет ключа "status"')
    homework_name = homework['homework_name']
    homework_status = homework['status']
    if homework_status not in HOMEWORK_VERDICTS:
        raise KeyError(f'Статус {homework_status} не распознан')
    verdict = HOMEWORK_VERDICTS[homework_status]
    logger.debug("Статус домашней работы определен!")
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверяет доступность токенов."""
    logger.debug("Проверяю токены")
    return all((PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID))


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        message = 'Отсутствует один или несколько токенов.'
        logger.critical(message)
        raise MissedTokenError(message)
    bot = Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    last_error_message = None

    while True:
        try:
            response = get_api_answer(current_timestamp)
            homeworks = check_response(response)
            if homeworks:
                message = parse_status(homeworks[0])
                send_message(bot, message)
                logger.info(f'Сообщение {message} успешно отправлено')
            else:
                logger.debug('Статус работы не изменился')
            current_timestamp = response.get('current_date')

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)
            if message != last_error_message:
                send_message(bot, message)
                last_error_message = message
        else:
            last_error_message = None
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
