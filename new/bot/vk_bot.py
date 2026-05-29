import asyncio
import logging
import time
import json
from concurrent.futures import ThreadPoolExecutor
import vk_api
from vk_api.longpoll import VkLongPoll, VkEventType
from bot.config import Config
from bot.vk_handlers import VKHandlers
from bot.vk_menu import EIOS_AUTH_BTN, EIOS_LOGOUT_BTN

logger = logging.getLogger(__name__)



class VKBot:
    bot_message_prefixes = [
                    "Здравствуйте! Это бот расписания",
                    "С возвращением!",
                    "Введите часть названия вашей",
                    "Кто вы?",
                    "Группа закреплена:",
                    "Преподаватель закреплён:",
                    "Введите фамилию или часть ФИО (как в расписании)",
                    "Сначала выберите роль",
                    "Справочники недоступны",
                    "Для взаимодействия с ботом используйте",
                    "На этот день пар нет",
                    "Ошибка, пожалуйста попробуйте позже",
                    "Выберите сохранённого преподавателя",
                    "Введите фамилию или часть ФИО",
                    "Введите номер или название аудитории",
                    "Введите часть названия группы",
                    "Преподаватели по запросу не найдены",
                    "Найдено совпадений:",
                    "Найдено аудиторий:",
                    "Найдено групп:",
                    "Аудитории по запросу не найдены",
                    "Группы по запросу не найдены",
                    "Выбран преподаватель:",
                    "Выбрана аудитория:",
                    "Выбрана группа:",
                    "Сейчас показано расписание преподавателя:",
                    "Сейчас показано расписание аудитории:",
                    "Сейчас показано расписание группы:",
                    "Для поиска по преподавателю",
                    "Действие отменено",
                    "Используйте кнопки меню",
                    "Режим просмотра чужого расписания не включён",
                    "Вы вышли из режима просмотра",
                    "Снова показывается расписание вашей группы",
                    "Снова показывается ваше расписание как преподавателя",
                    "Закреплено:",
                    "Пожалуйста, введите ваш логин",
                    "Теперь введите ваш пароль",
                    "Введен неправильный логин",
                    "Вы успешно вышли",
                    "Для начала вы должны авторизоваться",
                    "Сначала выберите роль и закрепите",
                    "неофициальный бот",
                ]
    def __init__(self, config: Config):
        self.config = config
        self.token = config.vk_token
        self.handlers = VKHandlers(self)
        self.running = False
        self.vk = None
        self.longpoll = None
        self.loop = None
        self._route: dict = {
            "Начать": self.handlers.start_handler,
            "👤 Преподаватель": self.handlers.teacher_menu_handler,
            "🚪 Аудитория": self.handlers.aud_menu_handler,
            "👥 Группа": self.handlers.group_menu_handler,
            "➕ Другой преподаватель": self.handlers.teacher_other_handler,
            "❌ Отмена": self.handlers.cancel_flow_handler,
            "ℹ Помощь": self.handlers.help_handler,
            "🎓 Я студент": self.handlers.student_role_handler,
            "👨‍🏫 Я преподаватель": self.handlers.teacher_role_handler,
            "ПИ ДГТУ": self.handlers.pi_univ_handler,
            "ДГТУ": self.handlers.dgtu_univ_handler,
            "🔄 Сменить профиль": self.handlers.change_profile_handler,
            "🔑 Авторизация": self.handlers.legacy_menu_handler,
            "🚪 Выход": self.handlers.change_profile_handler,
            "_": self.handlers.text_message_handler,
        }

    def _init_vk(self):
        try:
            self.vk = vk_api.VkApi(token=self.token)
            self.longpoll = VkLongPoll(self.vk)
        except Exception as e:
            logger.error(f"Ошибка подключения VK: {e}")
            raise

    def _send_message(self, peer_id: int, text: str, keyboard: dict = None) -> bool:
        try:
            params = {
                'peer_id': peer_id,
                'message': text,
                'random_id': int(time.time() * 1000000) & 0xFFFFFFFF
            }

            if keyboard:
                params['keyboard'] = json.dumps(keyboard)

            self.vk.method('messages.send', params)
            return True
        except Exception as e:
            logger.error(f"Ошибка отправки сообщения: {e}")
            return False

    def _process_event(self, event):
        try:
            if event.type == VkEventType.MESSAGE_NEW:
                if getattr(event, "from_me", False):
                    return
                if event.from_user:
                    peer_id = event.peer_id
                    text = event.text
                    from_id = event.user_id
                elif event.from_chat:
                    peer_id = event.peer_id
                    text = event.text
                    from_id = event.user_id
                else:
                    return

                if not text:
                    return
                if any(text.startswith(prefix) for prefix in self.bot_message_prefixes):
                    return

                context = {
                    'peer_id': peer_id,
                    'text': text,
                    'from_id': from_id
                }

                if self.loop:
                    logger.debug(f"Отправка в _route_message: {text!r}")
                    asyncio.run_coroutine_threadsafe(self._route_message(context), self.loop)
                else:
                    logger.error("Event loop не инициализирован")

        except Exception as e:
            logger.error(f"Ошибка обработки события: {e}", exc_info=True)

    async def _route_message(self, context: dict):
        text = context['text'].strip()
        peer_id = context['peer_id']

        logger.debug(f"_route_message: text={text!r}, peer_id={peer_id}")

        try:
            handler = self._route_by_text(text)
            logger.debug(f"Выбран handler: {handler.__name__ if hasattr(handler, '__name__') else handler}")
            await handler(peer_id, context)
        except Exception as e:
            logger.error(f"Ошибка маршрутизации: {e}", exc_info=True)
            self._send_message(peer_id, "Произошла ошибка. Пожалуйста, попробуйте позже.")

    def _route_by_text(self, text: str):
        t = (text or "").strip()
        if t.startswith("📖 Сегодня"):
            return self.handlers.today_handler
        if t.startswith("📖 Завтра"):
            return self.handlers.tomorrow_handler
        if t.startswith("📖 Неделя"):
            return self.handlers.week_handler
        if t.startswith("📖 Следующая неделя"):
            return self.handlers.next_week_handler
        if t.startswith("📖 Семестр"):
            return self.handlers.all_schedule_handler
        if t.startswith("🔴 ВЫХОД"):
            return self.handlers.focus_exit_handler
        if t.startswith("🔄 Сменить профиль") or t.startswith("🔄 Сменить группу"):
            return self.handlers.change_profile_handler
        if t.startswith("🎓 Я студент"):
            return self.handlers.student_role_handler
        if t.startswith("👨‍🏫 Я преподаватель"):
            return self.handlers.teacher_role_handler
        if t.startswith("ПИ ДГТУ"):
            return self.handlers.pi_univ_handler
        if t == "ДГТУ" or t.startswith("ДГТУ "):
            return self.handlers.dgtu_univ_handler
        if t.startswith("🔑 Авторизация"):
            return self.handlers.legacy_menu_handler
        if t.startswith("🚪 Выход"):
            return self.handlers.change_profile_handler
        if t.startswith(EIOS_AUTH_BTN):
            return self.handlers.eios_auth_handler
        if t.startswith(EIOS_LOGOUT_BTN):
            return self.handlers.eios_logout_handler
        return self._route.get(t, self._route["_"])

    async def start(self):
        try:
            logger.info("Запуск бота...")
            self.running = True
            self.loop = asyncio.get_running_loop()

            self._init_vk()

            if self.config.miniapp_enabled:
                from bot.miniapp.server import start_server
                await start_server(self.config, self.handlers)
                logger.info("VK Mini App HTTP-сервер запущен")

            logger.info("Бот подключён")
            logger.info("LongPoll запущен")

            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(self._run_longpoll)
                await asyncio.wrap_future(future)

        except (KeyboardInterrupt, asyncio.CancelledError):
            logger.info("Остановка бота")
        except Exception as e:
            logger.error(f"Критическая ошибка: {e}", exc_info=True)
        finally:
            await self.shutdown()

    def _run_longpoll(self):
        try:
            for event in self.longpoll.listen():
                if not self.running:
                    break
                self._process_event(event)
        except Exception as e:
            logger.error(f"Ошибка LongPoll: {e}", exc_info=True)

        self.longpoll = None