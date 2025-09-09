"""Все клавиатуры и inline-клавиатуры."""
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from typing import List


# Главная клавиатура
def main_menu() -> ReplyKeyboardMarkup:
kb = ReplyKeyboardMarkup(keyboard=[
[KeyboardButton(text='📚 Курсы'), KeyboardButton(text='ℹ️ О боте')]
], resize_keyboard=True)
return kb


# Admin keyboard (reply)
def admin_menu() -> ReplyKeyboardMarkup:
kb = ReplyKeyboardMarkup(keyboard=[
[KeyboardButton(text='Управление курсами')],
[KeyboardButton(text='Добавить курс')],
[KeyboardButton(text='Управление категориями')],
[KeyboardButton(text='❌ Отмена')]
], resize_keyboard=True)
return kb


# Inline: categories list
def categories_inline(categories: List[dict]) -> InlineKeyboardMarkup:
kb = InlineKeyboardMarkup()
for c in categories:
kb.add(InlineKeyboardButton(text=c['title'], callback_data=f'category:{c["id"]}'))
return kb


# Inline: courses list with pay buttons
def courses_inline(courses: List[dict]) -> InlineKeyboardMarkup:
kb = InlineKeyboardMarkup()
for course in courses:
kb.add(InlineKeyboardButton(text=f"{course['title']} — {course['price']/100:.2f} {course['currency']}", callback_data=f'course_show:{course["id"]}'))
kb.add(InlineKeyboardButton(text='Оплатить', callback_data=f'course_pay:{course["payload"]}'))
return kb


# Inline: single course show with pay
def course_detail_inline(course: dict) -> InlineKeyboardMarkup:
kb = InlineKeyboardMarkup()
kb.add(InlineKeyboardButton(text=f'Оплатить — {course["price"]/100:.2f} {course["currency"]}', callback_data=f'course_pay:{course["payload"]}'))
return kb


# Admin category management inline
def admin_categories_inline(categories: List[dict]) -> InlineKeyboardMarkup:
kb = InlineKeyboardMarkup()
for c in categories:
title = c['title'] + ('' if c['is_active'] else ' (off)')
kb.add(InlineKeyboardButton(text=title, callback_data=f'admin_cat:{c["id"]}'))
kb.add(InlineKeyboardButton(text='➕ Добавить категорию', callback_data='admin_cat_add'))
kb.add(InlineKeyboardButton(text='❌ Отмена', callback_data='admin_cancel'))
return kb


# Admin course management inline
def admin_courses_inline(courses: List[dict]) -> InlineKeyboardMarkup:
kb = InlineKeyboardMarkup()
for course in courses:
kb.add(InlineKeyboardButton(text=course['title'], callback_data=f'admin_course:{course["id"]}'))
kb.add(InlineKeyboardButton(text='➕ Добавить курс', callback_data='admin_course_add'))
kb.add(InlineKeyboardButton(text='❌ Отмена', callback_data='admin_cancel'))
return kb


# Generic cancel keyboard (reply)
def cancel_kb() -> ReplyKeyboardMarkup:
return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text='❌ Отмена')]], resize_keyboard=True)
