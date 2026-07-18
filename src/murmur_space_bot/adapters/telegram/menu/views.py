from __future__ import annotations

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

TASKS_BUTTON = "🌸 Tasks"
SHOPPING_BUTTON = "🛒 Shopping"
ADD_TASK_BUTTON = "＋ Add task"
ADD_ITEM_BUTTON = "＋ Add item"
CANCEL_BUTTON = "Cancel"


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text=TASKS_BUTTON),
                KeyboardButton(text=SHOPPING_BUTTON),
            ],
            [
                KeyboardButton(text=ADD_TASK_BUTTON),
                KeyboardButton(text=ADD_ITEM_BUTTON),
            ],
        ],
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="Choose what to organize…",
    )


def cancel_keyboard(prompt: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=CANCEL_BUTTON)]],
        resize_keyboard=True,
        one_time_keyboard=True,
        input_field_placeholder=prompt,
    )


def welcome_text() -> str:
    return (
        "🌸 <b>Murmur Space</b>\n"
        "Design studio / friendly coworking.\n\n I am your assistant, here to help you organize tasks and shopping lists for the studio ✨"
    )
