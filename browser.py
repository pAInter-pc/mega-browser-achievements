import sys
import os
import json
from datetime import datetime, timedelta

from PyQt6.QtCore import Qt, QUrl, QSettings, QStandardPaths, QTimer, QPoint
from PyQt6.QtGui import QAction, QColor, QPalette
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QTabWidget,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLineEdit,
    QToolBar,
    QMessageBox,
    QFileDialog,
    QListWidget,
    QListWidgetItem,
    QDialog,
    QPushButton,
    QLabel,
    QScrollArea,
    QGridLayout,
    QFrame,
)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEngineDownloadRequest


HOME_URL = "https://www.google.com"


# ======================= POPUP АЧИВКИ =======================

class AchievementPopup(QDialog):
    def __init__(self, parent, title: str, desc: str, timeout: int = 3000):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setModal(False)

        main = QVBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0)

        frame = QFrame()
        frame.setStyleSheet(
            """
            QFrame {
                background-color: rgba(32, 33, 36, 235);
                border-radius: 8px;
                border: 1px solid #5F6368;
            }
            QLabel {
                color: white;
            }
            """
        )
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(14, 8, 14, 8)
        layout.setSpacing(4)

        lbl_top = QLabel("Ачивка получена!")
        lbl_top.setStyleSheet("font-size: 11px; color: #A0A0A0;")
        layout.addWidget(lbl_top)

        lbl_title = QLabel(title)
        lbl_title.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(lbl_title)

        lbl_desc = QLabel(desc)
        lbl_desc.setWordWrap(True)
        lbl_desc.setStyleSheet("font-size: 11px; color: #E8EAED;")
        layout.addWidget(lbl_desc)

        main.addWidget(frame)

        self.adjustSize()

        self.timer = QTimer(self)
        self.timer.setInterval(timeout)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.close)
        self.timer.start()

    def show_at_bottom_right(self, parent: QMainWindow, margin: int = 16):
        parent_rect = parent.geometry()
        self.adjustSize()
        x = parent_rect.x() + parent_rect.width() - self.width() - margin
        y = parent_rect.y() + parent_rect.height() - self.height() - margin
        self.move(QPoint(x, y))
        self.show()


# ======================= ДИАЛОГИ =======================

class HistoryDialog(QDialog):
    def __init__(self, parent, history):
        super().__init__(parent)
        self.setWindowTitle("История")
        self.resize(600, 400)
        self.history = history

        layout = QVBoxLayout(self)
        self.list_widget = QListWidget()
        layout.addWidget(self.list_widget)

        for item in self.history:
            text = f"[{item['time']}] {item['title']} - {item['url']}"
            lw = QListWidgetItem(text)
            lw.setData(Qt.ItemDataRole.UserRole, item["url"])
            self.list_widget.addItem(lw)

        btns = QHBoxLayout()
        self.btn_clear = QPushButton("Очистить историю")
        self.btn_close = QPushButton("Закрыть")
        btns.addWidget(self.btn_clear)
        btns.addWidget(self.btn_close)
        layout.addLayout(btns)

        self.btn_close.clicked.connect(self.close)
        self.btn_clear.clicked.connect(self.clearHistory)
        self.list_widget.itemDoubleClicked.connect(self.onItemDoubleClicked)

    def clearHistory(self):
        if QMessageBox.question(
            self,
            "Очистка истории",
            "Удалить всю историю?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        ) == QMessageBox.StandardButton.Yes:
            self.history.clear()
            self.list_widget.clear()
            self.accept()

    def onItemDoubleClicked(self, item: QListWidgetItem):
        url = item.data(Qt.ItemDataRole.UserRole)
        self.parent().openUrlFromExternal(url)
        self.close()


class BookmarksDialog(QDialog):
    def __init__(self, parent, bookmarks):
        super().__init__(parent)
        self.setWindowTitle("Закладки")
        self.resize(600, 400)
        self.bookmarks = bookmarks

        layout = QVBoxLayout(self)
        self.list_widget = QListWidget()
        layout.addWidget(self.list_widget)

        self.refresh()

        btns = QHBoxLayout()
        self.btn_delete = QPushButton("Удалить выбранную")
        self.btn_close = QPushButton("Закрыть")
        btns.addWidget(self.btn_delete)
        btns.addWidget(self.btn_close)
        layout.addLayout(btns)

        self.btn_close.clicked.connect(self.close)
        self.btn_delete.clicked.connect(self.deleteSelected)
        self.list_widget.itemDoubleClicked.connect(self.onItemDoubleClicked)

    def refresh(self):
        self.list_widget.clear()
        for item in self.bookmarks:
            text = f"{item['title']} - {item['url']}"
            lw = QListWidgetItem(text)
            lw.setData(Qt.ItemDataRole.UserRole, item["url"])
            self.list_widget.addItem(lw)

    def deleteSelected(self):
        row = self.list_widget.currentRow()
        if row < 0:
            return
        del self.bookmarks[row]
        self.refresh()

    def onItemDoubleClicked(self, item: QListWidgetItem):
        url = item.data(Qt.ItemDataRole.UserRole)
        self.parent().openUrlFromExternal(url)
        self.parent().achievement_manager.on_bookmark_opened(url)
        self.close()


class DownloadsDialog(QDialog):
    def __init__(self, parent, downloads):
        super().__init__(parent)
        self.setWindowTitle("Загрузки")
        self.resize(600, 300)
        self.downloads = downloads

        layout = QVBoxLayout(self)
        self.list_widget = QListWidget()
        layout.addWidget(self.list_widget)

        self.refresh()

        btn_close = QPushButton("Закрыть")
        layout.addWidget(btn_close)
        btn_close.clicked.connect(self.close)

    def refresh(self):
        self.list_widget.clear()
        for d in self.downloads:
            text = f"{d['filename']} [{d['status']}] -> {d['path']}"
            self.list_widget.addItem(text)


# ======================= ПОДРОБНЫЙ СПИСОК АЧИВОК =======================

class AchievementsGridDialog(QDialog):
    def __init__(self, parent, achievements: dict, unlocked_count: int, total: int):
        super().__init__(parent)
        self.setWindowTitle("Ачивки — подробный список")
        self.resize(800, 520)

        main_layout = QVBoxLayout(self)

        title = QLabel(f"Ачивки ({unlocked_count} / {total})")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 22px; font-weight: bold;")
        main_layout.addWidget(title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        main_layout.addWidget(scroll)

        container = QWidget()
        grid = QGridLayout(container)
        grid.setContentsMargins(10, 10, 10, 10)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(12)

        row = 0
        col = 0
        max_cols = 3

        for key, ach in achievements.items():
            card = self.create_card(ach)
            grid.addWidget(card, row, col)
            col += 1
            if col >= max_cols:
                col = 0
                row += 1

        scroll.setWidget(container)

        btn_close = QPushButton("Закрыть")
        btn_close.clicked.connect(self.close)
        main_layout.addWidget(btn_close, alignment=Qt.AlignmentFlag.AlignRight)

    def create_card(self, ach: dict) -> QFrame:
        frame = QFrame()
        frame.setFrameShape(QFrame.Shape.StyledPanel)
        frame.setMinimumSize(220, 120)

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(10, 8, 10, 8)

        status = "Открыто" if ach["unlocked"] else "Скрыто"
        status_color = "#7CFC00" if ach["unlocked"] else "#888888"

        status_label = QLabel(status)
        status_label.setStyleSheet(f"color: {status_color}; font-weight: bold; font-size: 11px;")
        layout.addWidget(status_label)

        title_label = QLabel(ach["title"])
        title_label.setWordWrap(True)
        title_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(title_label)

        desc_label = QLabel(ach["desc"])
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("font-size: 12px; color: #E8EAED;")
        layout.addWidget(desc_label)

        comment_label = QLabel(ach["comment"])
        comment_label.setWordWrap(True)
        comment_label.setStyleSheet("font-size: 11px; color: #9AA0A6; font-style: italic;")
        layout.addWidget(comment_label)

        frame.setStyleSheet("""
            QFrame {
                background-color: #202124;
                border-radius: 8px;
                border: 1px solid #3C4043;
            }
        """)
        return frame


class AchievementsDialog(QDialog):
    def __init__(self, parent, achievements, unlocked_count, total):
        super().__init__(parent)
        self.setWindowTitle("Ачивки")
        self.resize(420, 320)

        layout = QVBoxLayout(self)
        header = QLabel(f"Получено ачивок: {unlocked_count} / {total}")
        header.setStyleSheet("font-weight: bold; margin-bottom: 4px;")
        layout.addWidget(header)

        self.list_widget = QListWidget()
        layout.addWidget(self.list_widget)

        for key, a in achievements.items():
            status = "✅" if a["unlocked"] else "🔒"
            text = f"{status} {a['title']} — {a['desc']}"
            self.list_widget.addItem(text)

        btn_close = QPushButton("Закрыть")
        layout.addWidget(btn_close)
        btn_close.clicked.connect(self.close)


# ======================= АЧИВКИ: ЛОГИКА =======================

class AchievementManager:
    def __init__(self, main_window):
        self.main_window = main_window
        self.settings = QSettings("Perplexity", "MegaBrowserAchievements")

        self.achievements = {
            # базовые
            "first_run": {
                "title": "Привет, мир!",
                "desc": "Наслаждайся пребыванием!",
                "comment": "Зайди в браузер в первый раз.",
                "unlocked": False,
            },
            "ya_ru": {
                "title": "Другой интернет",
                "desc": "Ты что русский?",
                "comment": "Зайти на ya.ru.",
                "unlocked": False,
            },

            # первые шаги
            "first_manual_url": {
                "title": "Первый шаг",
                "desc": "Ну здравствуй, интернет.",
                "comment": "Ввести любой URL вручную и перейти по нему.",
                "unlocked": False,
            },
            "home_used": {
                "title": "Дом, милый дом",
                "desc": "Тут всё начинается.",
                "comment": "Открыть домашнюю страницу кнопкой.",
                "unlocked": False,
            },
            "ten_sites_session": {
                "title": "Поехали!",
                "desc": "Движение — жизнь.",
                "comment": "Перейти на 10 разных сайтов за одну сессию.",
                "unlocked": False,
            },

            # вкладки
            "five_tabs": {
                "title": "Многозадачник",
                "desc": "Одного сайта мало.",
                "comment": "Открыть 5 вкладок одновременно.",
                "unlocked": False,
            },
            "ten_tabs": {
                "title": "Хаос‑менеджер",
                "desc": "Всё под контролем. Наверное.",
                "comment": "Открыть 10 вкладок одновременно.",
                "unlocked": False,
            },
            "clean_tabs": {
                "title": "Чистый лист",
                "desc": "Иногда нужно закрыть всё.",
                "comment": "Оставить только одну открытую вкладку.",
                "unlocked": False,
            },

            # история и закладки
            "history_50": {
                "title": "Память как у слона",
                "desc": "Ты многое повидал.",
                "comment": "Набрать 50 записей в истории.",
                "unlocked": False,
            },
            "bookmarks_10": {
                "title": "Архивариус",
                "desc": "Каждая страница на своём месте.",
                "comment": "Добавить 10 закладок.",
                "unlocked": False,
            },
            "fav_page": {
                "title": "Любимчик",
                "desc": "Лучшее в избранном.",
                "comment": "Открыть одну и ту же закладку 5 раз.",
                "unlocked": False,
            },

            # загрузки
            "first_download": {
                "title": "Лутер",
                "desc": "Забираешь всё, что лежит.",
                "comment": "Скачать первый файл.",
                "unlocked": False,
            },
            "downloads_10": {
                "title": "Коллекционер файлов",
                "desc": "Всё пригодится. Когда‑нибудь.",
                "comment": "Завершить 10 загрузок.",
                "unlocked": False,
            },

            # навигация
            "back_forward": {
                "title": "Назад в будущее",
                "desc": "История любит повторы.",
                "comment": "Использовать Назад и Вперёд хотя бы по разу.",
                "unlocked": False,
            },
            "reload_spam": {
                "title": "F5‑самурай",
                "desc": "Обновление — лучший багфикс.",
                "comment": "Обновить страницу 20 раз за сессию.",
                "unlocked": False,
            },

            # время
            "night_owl": {
                "title": "Ночной наблюдатель",
                "desc": "Интернет не спит.",
                "comment": "Открыть браузер после полуночи.",
                "unlocked": False,
            },

            # меню
            "menu_master": {
                "title": "Инженер‑испытатель",
                "desc": "Ты тестируешь всё, что видишь.",
                "comment": "Открыть все пункты меню хотя бы по разу.",
                "unlocked": False,
            },

            # НОВЫЕ — время и сессии
            "marathon": {
                "title": "Марафонец",
                "desc": "Сессия длиною в жизнь.",
                "comment": "Продержать браузер открытым 2 часа.",
                "unlocked": False,
            },
            "daily_user": {
                "title": "Ежедневный гость",
                "desc": "Мы видимся каждый день.",
                "comment": "Запускать браузер 7 дней подряд.",
                "unlocked": False,
            },
            "weekend_user": {
                "title": "Выходной онлайн",
                "desc": "Даже в субботу здесь.",
                "comment": "Открыть браузер в выходной.",
                "unlocked": False,
            },

            # НОВЫЕ — тип сайтов
            "wiki_master": {
                "title": "Энциклопедист",
                "desc": "Знания — сила.",
                "comment": "Посетить 5 разных wiki‑доменов.",
                "unlocked": False,
            },
            "video_fan": {
                "title": "Киноман",
                "desc": "Попкорн не прилагается.",
                "comment": "Открыть 5 страниц с видео (url содержит /watch или /video).",
                "unlocked": False,
            },
            "shopaholic": {
                "title": "Шопоголик",
                "desc": "Один клик — и деньги нет.",
                "comment": "Посетить 10 разных магазинов.",
                "unlocked": False,
            },

            # НОВЫЕ — поведение
            "tab_tourist": {
                "title": "Таб‑турист",
                "desc": "Прыжок по вкладкам.",
                "comment": "50 переключений между вкладками за сессию.",
                "unlocked": False,
            },
            "bookmark_speedrun": {
                "title": "Закладочный спидран",
                "desc": "Всё нужное под рукой.",
                "comment": "Добавить 5 закладок за 1 минуту.",
                "unlocked": False,
            },
            "history_spam": {
                "title": "Историк‑ревизионист",
                "desc": "Назад‑вперёд, назад‑вперёд.",
                "comment": "20 раз подряд жать Назад/Вперёд.",
                "unlocked": False,
            },

            # НОВЫЕ — ошибки и сети
            "error_404_hunter": {
                "title": "404 Hunter",
                "desc": "Этой страницы не существует… но ты её нашёл.",
                "comment": "Поймать 3 разные страницы 404.",
                "unlocked": False,
            },
            "bad_connection": {
                "title": "Нестабильное соединение",
                "desc": "Перезагрузка — наше всё.",
                "comment": "10 раз обновить страницу, которая не загрузилась.",
                "unlocked": False,
            },
            "https_only": {
                "title": "SSL‑параноик",
                "desc": "Только безопасные соединения.",
                "comment": "20 открытий https и ни одного http за сессию.",
                "unlocked": False,
            },

            # НОВАЯ — AFK
            "afk_tab": {
                "title": "Tab‑Zombie",
                "desc": "Оставь вкладку — она сама всё сделает.",
                "comment": "Не трогать активную вкладку 10 минут.",
                "unlocked": False,
            },
        }

        self.loadUnlocked()

        self.session_sites = set()
        self.used_back = False
        self.used_forward = False
        self.reload_count = 0
        self.manual_url_entered = False

        self.menu_items_used = {
            "downloads": False,
            "history": False,
            "bookmarks": False,
            "incognito": False,
            "achievements": False,
        }

        self.bookmark_add_count = 0
        self.bookmark_add_times = []  # timestamps
        self.bookmark_open_counter = {}

        self.download_started = 0
        self.download_finished = 0

        # новые счётчики
        self.start_time = datetime.now()
        self.tab_switches = 0
        self.back_forward_chain = 0
        self.failed_reload_chain = 0
        self.https_count = 0
        self.http_count = 0
        self.wiki_domains = set()
        self.video_pages = set()
        self.shop_domains = set()
        self.error_404_urls = set()
        self.last_action_time = datetime.now()

    # --------- служебные ---------

    def loadUnlocked(self):
        for key in self.achievements.keys():
            v = self.settings.value(f"achievements/{key}", False, type=bool)
            self.achievements[key]["unlocked"] = v

    def saveUnlocked(self):
        for key, a in self.achievements.items():
            self.settings.setValue(f"achievements/{key}", a["unlocked"])

    def unlocked_count(self):
        return sum(1 for a in self.achievements.values() if a["unlocked"])

    def total_count(self):
        return len(self.achievements)

    def unlock(self, key: str):
        a = self.achievements.get(key)
        if not a or a["unlocked"]:
            return
        a["unlocked"] = True
        self.saveUnlocked()

        popup = AchievementPopup(self.main_window, a["title"], a["desc"], timeout=3500)
        popup.show_at_bottom_right(self.main_window)
        self.main_window.updateAchievementsMenuTitle()

    # --------- первый запуск + дни ---------

    def checkFirstRunAndDates(self):
        first = self.settings.value("first_run_flag", True, type=bool)
        today = datetime.now().date()
        last_date = self.settings.value("last_open_date", "", type=str)

        if first:
            self.unlock("first_run")
            self.settings.setValue("first_run_flag", False)

        # streak по дням
        streak = self.settings.value("daily_streak", 0, type=int)
        if last_date:
            last = datetime.fromisoformat(last_date).date()
            if today == last:
                pass
            elif today == last + timedelta(days=1):
                streak += 1
            else:
                streak = 1
        else:
            streak = 1

        self.settings.setValue("daily_streak", streak)
        self.settings.setValue("last_open_date", today.isoformat())

        if streak >= 7:
            self.unlock("daily_user")

        # выходной
        if today.weekday() >= 5:
            self.unlock("weekend_user")

    # --------- триггеры URL/загрузки/навигации ---------

    def on_url_loaded(self, url: str, ok: bool, title: str):
        self.last_action_time = datetime.now()

        if ok:
            self.session_sites.add(url)

            if len(self.session_sites) >= 10:
                self.unlock("ten_sites_session")

            lower = url.lower()
            # ya.ru
            if "ya.ru" in lower:
                self.unlock("ya_ru")

            # https/http
            if lower.startswith("https://"):
                self.https_count += 1
            elif lower.startswith("http://"):
                self.http_count += 1

            if self.https_count >= 20 and self.http_count == 0:
                self.unlock("https_only")

            # wiki
            if "wiki" in lower:
                host = lower.split("/")[2]
                self.wiki_domains.add(host)
                if len(self.wiki_domains) >= 5:
                    self.unlock("wiki_master")

            # video
            if "/watch" in lower or "/video" in lower:
                self.video_pages.add(url)
                if len(self.video_pages) >= 5:
                    self.unlock("video_fan")

            # shop
            if any(word in lower for word in ["cart", "checkout", "store", "shop"]):
                host = lower.split("/")[2]
                self.shop_domains.add(host)
                if len(self.shop_domains) >= 10:
                    self.unlock("shopaholic")

            # успешная загрузка сбрасывает цепочку неудачных reload
            self.failed_reload_chain = 0

        else:
            # провал загрузки — потенциальный 404
            if "404" in title or "not found" in title.lower():
                self.error_404_urls.add(url)
                if len(self.error_404_urls) >= 3:
                    self.unlock("error_404_hunter")

    def mark_manual_url(self):
        self.last_action_time = datetime.now()
        if not self.manual_url_entered:
            self.manual_url_entered = True
            self.unlock("first_manual_url")

    def on_tabs_count_changed(self, count: int):
        self.last_action_time = datetime.now()
        if count >= 5:
            self.unlock("five_tabs")
        if count >= 10:
            self.unlock("ten_tabs")
        if count == 1:
            self.unlock("clean_tabs")

    def on_history_size(self, size: int):
        if size >= 50:
            self.unlock("history_50")

    def on_bookmark_added(self):
        now = datetime.now()
        self.bookmark_add_count += 1
        self.bookmark_add_times.append(now)
        if self.bookmark_add_count >= 10:
            self.unlock("bookmarks_10")

        # спидран: 5 закладок за минуту
        one_min_ago = now - timedelta(minutes=1)
        self.bookmark_add_times = [t for t in self.bookmark_add_times if t >= one_min_ago]
        if len(self.bookmark_add_times) >= 5:
            self.unlock("bookmark_speedrun")

    def on_bookmark_opened(self, url: str):
        self.bookmark_open_counter[url] = self.bookmark_open_counter.get(url, 0) + 1
        if self.bookmark_open_counter[url] >= 5:
            self.unlock("fav_page")

    def on_download_started(self):
        self.download_started += 1
        if self.download_started >= 1:
            self.unlock("first_download")

    def on_download_finished(self):
        self.download_finished += 1
        if self.download_finished >= 10:
            self.unlock("downloads_10")

    def mark_back(self):
        self.last_action_time = datetime.now()
        self.used_back = True
        self.back_forward_chain += 1
        self._check_back_forward()

    def mark_forward(self):
        self.last_action_time = datetime.now()
        self.used_forward = True
        self.back_forward_chain += 1
        self._check_back_forward()

    def _check_back_forward(self):
        if self.used_back and self.used_forward:
            self.unlock("back_forward")
        if self.back_forward_chain >= 20:
            self.unlock("history_spam")

    def add_reload(self, last_ok: bool):
        self.last_action_time = datetime.now()
        self.reload_count += 1
        if self.reload_count >= 20:
            self.unlock("reload_spam")

        if not last_ok:
            self.failed_reload_chain += 1
            if self.failed_reload_chain >= 10:
                self.unlock("bad_connection")
        else:
            self.failed_reload_chain = 0

    def mark_menu_item(self, name: str):
        self.last_action_time = datetime.now()
        if name in self.menu_items_used:
            self.menu_items_used[name] = True
            if all(self.menu_items_used.values()):
                self.unlock("menu_master")

    def mark_night_owl(self, current_hour: int):
        if 0 <= current_hour < 5:
            self.unlock("night_owl")

    def mark_tab_switch(self):
        self.tab_switches += 1
        if self.tab_switches >= 50:
            self.unlock("tab_tourist")

    # --------- AFK и марафон ---------

    def check_session_time(self):
        if datetime.now() - self.start_time >= timedelta(hours=2):
            self.unlock("marathon")

    def check_afk(self):
        if datetime.now() - self.last_action_time >= timedelta(minutes=10):
            self.unlock("afk_tab")


# ======================= ВКЛАДКА =======================

class BrowserTab(QWidget):
    def __init__(self, main_window, url=HOME_URL, incognito=False):
        super().__init__()
        self.main_window = main_window
        self.incognito = incognito

        self.last_load_ok = True

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.view = QWebEngineView(self)

        self.view.urlChanged.connect(self.onUrlChanged)
        self.view.titleChanged.connect(self.onTitleChanged)
        self.view.loadFinished.connect(self.onLoadFinished)
        self.view.page().profile().downloadRequested.connect(self.onDownloadRequested)

        self.view.load(QUrl(url))
        layout.addWidget(self.view)

    def onUrlChanged(self, url: QUrl):
        if self is self.main_window.currentBrowserTab():
            self.main_window.updateUrlBar(url.toString())

    def onTitleChanged(self, title: str):
        index = self.main_window.tab_widget.indexOf(self)
        if index != -1:
            prefix = "[Incognito] " if self.incognito else ""
            self.main_window.tab_widget.setTabText(index, prefix + title)

    def onLoadFinished(self, ok: bool):
        self.last_load_ok = ok
        url = self.view.url().toString()
        title = self.view.title() or url
        if ok:
            self.main_window.addToHistory(url, title)
            self.main_window.achievement_manager.on_url_loaded(url, ok=True, title=title)
        else:
            self.main_window.achievement_manager.on_url_loaded(url, ok=False, title=title)

    def onDownloadRequested(self, download: QWebEngineDownloadRequest):
        suggested = download.downloadFileName()
        default_dir = QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.DownloadLocation
        )
        if not os.path.isdir(default_dir):
            os.makedirs(default_dir, exist_ok=True)
        default_path = os.path.join(default_dir, suggested)

        path, ok = QFileDialog.getSaveFileName(
            self,
            "Сохранить файл",
            default_path,
            "Все файлы (*)",
        )
        if not ok or not path:
            download.cancel()
            return

        download.setDownloadDirectory(os.path.dirname(path))
        download.setDownloadFileName(os.path.basename(path))
        download.accept()

        self.main_window.achievement_manager.on_download_started()

        info = {
            "filename": os.path.basename(path),
            "path": path,
            "status": "скачивание...",
        }
        self.main_window.downloads.append(info)

        def finished():
            info["status"] = "готово"
            self.main_window.achievement_manager.on_download_finished()

        download.finished.connect(finished)


# ======================= ГЛАВНОЕ ОКНО =======================

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Mega Browser с ачивками")
        self.resize(1200, 800)

        self.settings = QSettings("Perplexity", "MegaBrowser")
        self.data_dir = os.path.join(
            QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation),
            "MegaBrowserData",
        )
        os.makedirs(self.data_dir, exist_ok=True)
        self.history_file = os.path.join(self.data_dir, "history.json")
        self.bookmarks_file = os.path.join(self.data_dir, "bookmarks.json")

        self.history = self.loadJson(self.history_file, [])
        self.bookmarks = self.loadJson(self.bookmarks_file, [])
        self.downloads = []

        self.achievement_manager = AchievementManager(self)
        self.achievement_manager.checkFirstRunAndDates()
        self.achievement_manager.mark_night_owl(datetime.now().hour)

        self.tab_widget = QTabWidget()
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.tabCloseRequested.connect(self.closeTab)
        self.tab_widget.currentChanged.connect(self.onCurrentTabChanged)
        self.setCentralWidget(self.tab_widget)

        self.createToolBar()
        self.createDropDownMenu()
        self.updateAchievementsMenuTitle()

        self.addNewTab(HOME_URL)

        # таймеры для марафона и AFK
        self.session_timer = QTimer(self)
        self.session_timer.timeout.connect(self.achievement_manager.check_session_time)
        self.session_timer.start(60_000)  # раз в минуту

        self.afk_timer = QTimer(self)
        self.afk_timer.timeout.connect(self.achievement_manager.check_afk)
        self.afk_timer.start(60_000)

    # ---------- JSON ----------

    def loadJson(self, path, default):
        if not os.path.exists(path):
            return default
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default

    def saveJson(self, path, data):
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print("Ошибка сохранения", path, e)

    # ---------- История ----------

    def addToHistory(self, url: str, title: str):
        item = {
            "url": url,
            "title": title,
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        self.history.append(item)
        self.saveJson(self.history_file, self.history)
        self.achievement_manager.on_history_size(len(self.history))

    def openHistoryDialog(self):
        dlg = HistoryDialog(self, self.history)
        if dlg.exec():
            self.saveJson(self.history_file, self.history)

    # ---------- Закладки ----------

    def addCurrentToBookmarks(self):
        tab = self.currentBrowserTab()
        if not tab:
            return
        url = tab.view.url().toString()
        title = tab.view.title() or url
        self.bookmarks.append({"url": url, "title": title})
        self.saveJson(self.bookmarks_file, self.bookmarks)
        self.achievement_manager.on_bookmark_added()
        QMessageBox.information(self, "Закладки", "Страница добавлена в закладки.")

    def openBookmarksDialog(self):
        dlg = BookmarksDialog(self, self.bookmarks)
        dlg.exec()
        self.saveJson(self.bookmarks_file, self.bookmarks)

    # ---------- Загрузки ----------

    def openDownloadsDialog(self):
        dlg = DownloadsDialog(self, self.downloads)
        dlg.exec()

    # ---------- Ачивки ----------

    def openAchievementsDialog(self):
        dlg = AchievementsDialog(
            self,
            self.achievement_manager.achievements,
            self.achievement_manager.unlocked_count(),
            self.achievement_manager.total_count(),
        )
        dlg.exec()

    def openAchievementsGridDialog(self):
        dlg = AchievementsGridDialog(
            self,
            self.achievement_manager.achievements,
            self.achievement_manager.unlocked_count(),
            self.achievement_manager.total_count(),
        )
        dlg.exec()

    def updateAchievementsMenuTitle(self):
        unlocked = self.achievement_manager.unlocked_count()
        total = self.achievement_manager.total_count()
        if hasattr(self, "achievements_menu"):
            self.achievements_menu.setTitle(f"Ачивки ({unlocked}/{total})")

    # ---------- Инкогнито (визуальное) ----------

    def openIncognitoTab(self):
        QMessageBox.information(
            self,
            "Инкогнито",
            "Технический инкогнито не поддерживается в этой версии Qt/PyQt.\n"
            "Открывается обычная вкладка с пометкой [Incognito].",
        )
        self.addNewTab(HOME_URL, incognito=True)

    # ---------- Вкладки ----------

    def currentBrowserTab(self) -> BrowserTab | None:
        w = self.tab_widget.currentWidget()
        return w if isinstance(w, BrowserTab) else None

    def addNewTab(self, url=HOME_URL, incognito=False):
        tab = BrowserTab(self, url=url, incognito=incognito)
        index = self.tab_widget.addTab(tab, "Новая вкладка")
        self.tab_widget.setCurrentIndex(index)
        self.achievement_manager.on_tabs_count_changed(self.tab_widget.count())

    def closeTab(self, index: int):
        if self.tab_widget.count() == 1:
            return
        w = self.tab_widget.widget(index)
        self.tab_widget.removeTab(index)
        w.deleteLater()
        self.achievement_manager.on_tabs_count_changed(self.tab_widget.count())

    def onCurrentTabChanged(self, index: int):
        self.achievement_manager.mark_tab_switch()
        tab = self.currentBrowserTab()
        if tab:
            self.updateUrlBar(tab.view.url().toString())

    def openUrlFromExternal(self, url: str):
        tab = self.currentBrowserTab()
        if tab:
            tab.view.load(QUrl(url))

    # ---------- Навигация ----------

    def updateUrlBar(self, url: str):
        self.url_bar.blockSignals(True)
        self.url_bar.setText(url)
        self.url_bar.blockSignals(False)

    def onUrlEntered(self):
        text = self.url_bar.text().strip()
        if not text:
            return
        if not text.startswith("http://") and not text.startswith("https://"):
            text = "https://" + text

        self.achievement_manager.mark_manual_url()

        tab = self.currentBrowserTab()
        if tab:
            tab.view.load(QUrl(text))
            self.updateUrlBar(text)

    def goBack(self):
        tab = self.currentBrowserTab()
        if tab and tab.view.history().canGoBack():
            tab.view.back()
            self.achievement_manager.mark_back()

    def goForward(self):
        tab = self.currentBrowserTab()
        if tab and tab.view.history().canGoForward():
            tab.view.forward()
            self.achievement_manager.mark_forward()

    def reloadPage(self):
        tab = self.currentBrowserTab()
        if tab:
            last_ok = tab.last_load_ok
            tab.view.reload()
            self.achievement_manager.add_reload(last_ok)

    def goHome(self):
        tab = self.currentBrowserTab()
        if tab:
            tab.view.load(QUrl(HOME_URL))
            self.achievement_manager.unlock("home_used")

    # ---------- Тулбар и меню ----------

    def createToolBar(self):
        toolbar = QToolBar("Навигация", self)
        toolbar.setMovable(False)
        toolbar.setContentsMargins(4, 2, 4, 2)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, toolbar)

        act_back = QAction("◀", self)
        act_back.triggered.connect(self.goBack)
        toolbar.addAction(act_back)

        act_forward = QAction("▶", self)
        act_forward.triggered.connect(self.goForward)
        toolbar.addAction(act_forward)

        act_reload = QAction("⟳", self)
        act_reload.triggered.connect(self.reloadPage)
        toolbar.addAction(act_reload)

        act_home = QAction("🏠", self)
        act_home.triggered.connect(self.goHome)
        toolbar.addAction(act_home)

        toolbar.addSeparator()

        self.url_bar = QLineEdit()
        self.url_bar.setPlaceholderText("Введите адрес или запрос Google")
        self.url_bar.returnPressed.connect(self.onUrlEntered)
        self.url_bar.setMinimumHeight(26)
        toolbar.addWidget(self.url_bar)

        toolbar.addSeparator()

        act_bookmark = QAction("★", self)
        act_bookmark.setToolTip("Добавить в закладки")
        act_bookmark.triggered.connect(self.addCurrentToBookmarks)
        toolbar.addAction(act_bookmark)

        act_new_tab = QAction("+", self)
        act_new_tab.setToolTip("Новая вкладка")
        act_new_tab.triggered.connect(lambda: self.addNewTab(HOME_URL))
        toolbar.addAction(act_new_tab)

    def createDropDownMenu(self):
        menubar = self.menuBar()
        menubar.setNativeMenuBar(False)

        drop = menubar.addMenu("≡")

        act_downloads = QAction("Загрузки", self)
        act_downloads.triggered.connect(self.openDownloadsDialog)
        act_downloads.triggered.connect(
            lambda: self.achievement_manager.mark_menu_item("downloads")
        )
        drop.addAction(act_downloads)

        act_history = QAction("История", self)
        act_history.triggered.connect(self.openHistoryDialog)
        act_history.triggered.connect(
            lambda: self.achievement_manager.mark_menu_item("history")
        )
        drop.addAction(act_history)

        act_bookmarks = QAction("Закладки", self)
        act_bookmarks.triggered.connect(self.openBookmarksDialog)
        act_bookmarks.triggered.connect(
            lambda: self.achievement_manager.mark_menu_item("bookmarks")
        )
        drop.addAction(act_bookmarks)

        drop.addSeparator()

        act_incognito = QAction("Новая вкладка (Инкогнито)", self)
        act_incognito.triggered.connect(self.openIncognitoTab)
        act_incognito.triggered.connect(
            lambda: self.achievement_manager.mark_menu_item("incognito")
        )
        drop.addAction(act_incognito)

        drop.addSeparator()

        # подменю ачивок с счётчиком
        self.achievements_menu = drop.addMenu("")
        self.updateAchievementsMenuTitle()

        act_ach_list = QAction("Список ачивок (списком)", self)
        act_ach_list.triggered.connect(self.openAchievementsDialog)
        act_ach_list.triggered.connect(
            lambda: self.achievement_manager.mark_menu_item("achievements")
        )
        self.achievements_menu.addAction(act_ach_list)

        act_ach_grid = QAction("Список ачивок (карточки)", self)
        act_ach_grid.triggered.connect(self.openAchievementsGridDialog)
        act_ach_grid.triggered.connect(
            lambda: self.achievement_manager.mark_menu_item("achievements")
        )
        self.achievements_menu.addAction(act_ach_grid)


# ======================= ТЁМНАЯ ТЕМА =======================

def apply_dark_theme(app: QApplication):
    palette = QPalette()

    palette.setColor(QPalette.ColorRole.Window, QColor("#202124"))
    palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.white)
    palette.setColor(QPalette.ColorRole.Base, QColor("#171717"))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#202124"))
    palette.setColor(QPalette.ColorRole.ToolTipBase, Qt.GlobalColor.white)
    palette.setColor(QPalette.ColorRole.ToolTipText, Qt.GlobalColor.white)
    palette.setColor(QPalette.ColorRole.Text, Qt.GlobalColor.white)
    palette.setColor(QPalette.ColorRole.Button, QColor("#303134"))
    palette.setColor(QPalette.ColorRole.ButtonText, Qt.GlobalColor.white)
    palette.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.red)

    palette.setColor(QPalette.ColorRole.Highlight, QColor("#8AB4F8"))
    palette.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.black)

    app.setPalette(palette)
    app.setStyleSheet("""
        QMainWindow, QDialog {
            background-color: #202124;
            color: #E8EAED;
            font-family: Segoe UI, sans-serif;
            font-size: 10pt;
        }
        QToolBar {
            background-color: #292A2D;
            border: none;
            spacing: 4px;
        }
        QLineEdit {
            background-color: #202124;
            border-radius: 14px;
            border: 1px solid #5F6368;
            padding: 4px 10px;
            color: #E8EAED;
        }
        QLineEdit:focus {
            border: 1px solid #8AB4F8;
        }
        QListWidget {
            background-color: #171717;
            border: 1px solid #3C4043;
        }
        QPushButton {
            background-color: #303134;
            border: 1px solid #5F6368;
            border-radius: 4px;
            padding: 4px 10px;
        }
        QPushButton:hover {
            background-color: #3C4043;
        }
        QTabBar::tab {
            background-color: #292A2D;
            color: #E8EAED;
            padding: 4px 10px;
            border-top-left-radius: 6px;
            border-top-right-radius: 6px;
            margin-right: 2px;
        }
        QTabBar::tab:selected {
            background-color: #202124;
        }
        QTabWidget::pane {
            border-top: 1px solid #3C4043;
        }
        QMenuBar {
            background-color: #292A2D;
            color: #E8EAED;
        }
        QMenuBar::item:selected {
            background-color: #3C4043;
        }
        QMenu {
            background-color: #292A2D;
            color: #E8EAED;
            border: 1px solid #3C4043;
        }
        QMenu::item:selected {
            background-color: #3C4043;
        }
    """)


# ======================= MAIN =======================

if __name__ == "__main__":
    app = QApplication(sys.argv)
    apply_dark_theme(app)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())