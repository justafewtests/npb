from npb.config import Config

bp = chr(8226)
instagram_text = (
    "Пожалуйста, введите название вашего профиля в Instagram.\nМаксимальная длина - "
    f"{Config.USER_INSTAGRAM_MAX_LENGTH} символов.\nРазрешено использовать *буквы латинского алфавита*, *цифры*, "
    f"*знак нижнего подчеркивания (_)* и *точки (.)*."
)
description_text = (
    "Пожалуйста, расскажите о себе в нескольких предложениях.\nМаксимальная длина текста - "
    f"*{Config.USER_DESCRIPTION_MAX_LENGTH} символов*.\nРазрешено использовать *буквы*, *цифры*, *знак пробел* и *знаки"
    f" -.,!?:)(*.\nПример: Привет! Меня зовут Катя. Я профессионально занимаюсь маникюром и педикюром."
)
telegram_text = (
    "Пожалуйста, введите название вашего профиля в Telegram (его можно увидеть в разделе 'Настройки' -> 'Мой профиль' -"
    "> 'Имя Пользователя'). Или нажмите на кнопку 'Пропустить'."
)
pick_sub_service_text = "Пожалуйста, выберите предоставляемые Вами подуслуги для услуги %s из списка:"
registration_almost_finished_text = "Ваша регистрация почти окончена! Хотите что-нибудь изменить?"
what_do_you_want_to_change_text = "Что Вы хотите изменить?"
pick_service_to_delete_text = "Выберите услугу для удаления:"
