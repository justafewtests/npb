import logging

formatter = logging.Formatter('%(levelname)s:     %(asctime)s | %(message)s')
handler = logging.StreamHandler()
handler.setFormatter(formatter)
handler.encoding = "utf-8"

app_logger = logging.getLogger("app_logger")
app_logger.addHandler(handler)
app_logger.setLevel(logging.DEBUG)


def get_logger() -> logging.Logger:
    """
    Получить объект логгера.
    :return: Логгер.
    """
    return app_logger
