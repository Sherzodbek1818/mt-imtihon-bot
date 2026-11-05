import telebot
from telebot import types
import sqlite3
import random
import time

TOKEN = "8978375321:AAH7sqteOMmgO1Z5yQjTRVlgl5COmZGUeeA"
bot = telebot.TeleBot(TOKEN)

ADMIN_ID = 6063880298

def init_db():
    conn = sqlite3.connect('bot.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, full_name TEXT, status TEXT DEFAULT "pending")')
    cursor.execute('CREATE TABLE IF NOT EXISTS subjects (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE)')
    cursor.execute('CREATE TABLE IF NOT EXISTS questions (id INTEGER PRIMARY KEY AUTOINCREMENT, subject_id INTEGER, question TEXT, options TEXT, correct TEXT)')
    conn.commit()
    conn.close()

init_db()

user_state = {}
user_test_data = {}

def is_admin(user_id):
    return user_id == ADMIN_ID

@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    
    if is_admin(user_id):
        show_admin_panel(message.chat.id)
        return

    conn = sqlite3.connect('bot.db')
    cursor = conn.cursor()
    cursor.execute('SELECT status, full_name FROM users WHERE user_id = ?', (user_id,))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        user_state[user_id] = 'waiting_info'
        bot.send_message(message.chat.id, "💳 To'lov qilgan bo'lsangiz, ism, familiya va guruhingizni yuboring:")
    elif row[0] == 'pending':
        bot.send_message(message.chat.id, f"Hurmatli {row[1]}, ma'lumotlaringiz adaminga yuborilgan. Ruxsat kutilmoqda ⏳")
    elif row[0] == 'approved':
        show_subjects(message.chat.id)

def show_admin_panel(chat_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("📚 Fan qo'shish", "🗑 Fanni o'chirish")
    markup.add("➕ Test qo'shish")
    bot.send_message(chat_id, "Salom Admin! Panelga xush kelibsiz.", reply_markup=markup)

@bot.message_handler(func=lambda msg: msg.from_user.id in user_state and user_state[msg.from_user.id] == 'waiting_info')
def get_student_info(message):
    user_id = message.from_user.id
    info = message.text
    
    conn = sqlite3.connect('bot.db')
    cursor = conn.cursor()
    cursor.execute('INSERT OR REPLACE INTO users (user_id, full_name, status) VALUES (?, ?, ?)', (user_id, info, 'pending'))
    conn.commit()
    conn.close()
    
    del user_state[user_id]
    bot.send_message(message.chat.id, "Ma'lumotlaringiz adaminga yuborildi. Ruxsat kutilmoqda ⏳")
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("✅ Ruxsat berish", callback_data=f"approve_{user_id}"))
    bot.send_message(ADMIN_ID, f"👤 <b>Yangi talaba so'rovi:</b>\n\nIsm/Guruh: <b>{info}</b>\nTelegram ID: <code>{user_id}</code>", parse_mode='HTML', reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('approve_'))
def approve_student(call):
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "Siz admin emassiz!")
        return
        
    user_id = int(call.data.split('_')[1])
    conn = sqlite3.connect('bot.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET status = "approved" WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()
    
    bot.answer_callback_query(call.id, "Ruxsat berildi!")
    bot.edit_message_text("✅ Talaba muvaffaqiyatli tasdiqlandi.", call.message.chat.id, call.message.message_id)
    bot.send_message(user_id, "🎉 Tabriklaymiz! Sizga ruxsat berildi. /start ni bosing.")

def show_subjects(chat_id):
    conn = sqlite3.connect('bot.db')
    cursor = conn.cursor()
    cursor.execute('SELECT id, name FROM subjects')
    subjects = cursor.fetchall()
    conn.close()
    if not subjects:
        bot.send_message(chat_id, "Hozircha fanlar yo'q.")
        return
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    for sub in subjects:
        markup.add(types.KeyboardButton(sub[1]))
    bot.send_message(chat_id, "Test topshirish uchun fanni tanlang:", reply_markup=markup)

@bot.message_handler(func=lambda msg: msg.text == "📚 Fan qo'shish" and is_admin(msg.from_user.id))
def admin_add_subject(message):
    user_state[message.from_user.id] = 'waiting_subject_name'
    bot.send_message(message.chat.id, "Yangi fan nomini kiriting:")

@bot.message_handler(func=lambda msg: msg.from_user.id in user_state and user_state[msg.from_user.id] == 'waiting_subject_name')
def save_subject(message):
    sub_name = message.text
    conn = sqlite3.connect('bot.db')
    cursor = conn.cursor()
    try:
        cursor.execute('INSERT INTO subjects (name) VALUES (?)', (sub_name,))
        conn.commit()
        bot.send_message(message.chat.id, f"'{sub_name}' fani qo'shildi!")
    except:
        bot.send_message(message.chat.id, "Bu fan allaqachon mavjud!")
    conn.close()
    del user_state[message.from_user.id]
    start(message)

@bot.message_handler(func=lambda msg: msg.text == "🗑 Fanni o'chirish" and is_admin(msg.from_user.id))
def admin_delete_subject_start(message):
    conn = sqlite3.connect('bot.db')
    cursor = conn.cursor()
    cursor.execute('SELECT id, name FROM subjects')
    subs = cursor.fetchall()
    conn.close()
    if not subs:
        bot.send_message(message.chat.id, "O'chirish uchun fanlar mavjud emas.")
        return
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    for sub in subs:
        markup.add(types.KeyboardButton(f"DelSub: {sub[1]}"))
    markup.add("🔙 Orqaga")
    bot.send_message(message.chat.id, "Qaysi fanni o'chirmoqchisiz? (Fanning barcha testlari ham o'chib ketadi):", reply_markup=markup)

@bot.message_handler(func=lambda msg: msg.text.startswith("DelSub: ") and is_admin(msg.from_user.id))
def delete_subject_confirm(message):
    sub_name = message.text.replace("DelSub: ", "")
    conn = sqlite3.connect('bot.db')
    cursor = conn.cursor()
    cursor.execute('SELECT id FROM subjects WHERE name = ?', (sub_name,))
    sub = cursor.fetchone()
    if sub:
        sub_id = sub[0]
        cursor.execute('DELETE FROM questions WHERE subject_id = ?', (sub_id,))
        cursor.execute('DELETE FROM subjects WHERE id = ?', (sub_id,))
        conn.commit()
        bot.send_message(message.chat.id, f"🗑 '{sub_name}' fani va uning barcha testlari o'chirib yuborildi!")
    conn.close()
    start(message)

@bot.message_handler(func=lambda msg: msg.text == "🔙 Orqaga" and is_admin(msg.from_user.id))
def go_back_admin(message):
    start(message)

@bot.message_handler(func=lambda msg: msg.text == "➕ Test qo'shish" and is_admin(msg.from_user.id))
def admin_add_test_start(message):
    conn = sqlite3.connect('bot.db')
    cursor = conn.cursor()
    cursor.execute('SELECT id, name FROM subjects')
    subs = cursor.fetchall()
    conn.close()
    if not subs:
        bot.send_message(message.chat.id, "Avval fan qo'shing!")
        return
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    for sub in subs:
        markup.add(types.KeyboardButton(f"Fan: {sub[1]}"))
    markup.add("🔙 Orqaga")
    bot.send_message(message.chat.id, "Qaysi fanga test qo'shasiz?", reply_markup=markup)

@bot.message_handler(func=lambda msg: msg.text.startswith("Fan: ") and is_admin(msg.from_user.id))
def select_subject_for_test(message):
    sub_name = message.text.replace("Fan: ", "")
    conn = sqlite3.connect('bot.db')
    cursor = conn.cursor()
    cursor.execute('SELECT id FROM subjects WHERE name = ?', (sub_name,))
    sub = cursor.fetchone()
    conn.close()
    if sub:
        user_state[message.from_user.id] = f'adding_tests_{sub[0]}'
        bot.send_message(message.chat.id, "Testlarni quyidagi shablonda yuboring:\nSavol matni\n- Xato javob 1\n- Xato javob 2\n+ To'g'ri javob\n\nTugatgach /stop bosing.", reply_markup=types.ReplyKeyboardRemove())

@bot.message_handler(func=lambda msg: msg.from_user.id in user_state and user_state[msg.from_user.id].startswith('adding_tests_'))
def receive_tests(message):
    if message.text == '/stop':
        del user_state[message.from_user.id]
        bot.send_message(message.chat.id, "Test qo'shish yakunlandi.")
        start(message)
        return
    sub_id = int(user_state[message.from_user.id].split('_')[2])
    lines = message.text.strip().split('\n')
    if len(lines) < 3:
        bot.send_message(message.chat.id, "Xato format! Qaytadan yuboring.")
        return
    question = lines[0]
    options, correct = [], ""
    for line in lines[1:]:
        if line.startswith('+'):
            correct = line[1:].strip()
            options.append(correct)
        elif line.startswith('-'):
            options.append(line[1:].strip())
    if not correct:
        bot.send_message(message.chat.id, "To'g'ri javob (+ bilan) ko'rsatilmagan!")
        return
    conn = sqlite3.connect('bot.db')
    cursor = conn.cursor()
    cursor.execute('INSERT INTO questions (subject_id, question, options, correct) VALUES (?, ?, ?, ?)', (sub_id, question, "|||".join(options), correct))
    conn.commit()
    conn.close()
    bot.send_message(message.chat.id, "✅ Saqlandi! Keyingisini yuboring yoki /stop bosing.")

@bot.message_handler(func=lambda msg: True)
def handle_student(message):
    user_id = message.from_user.id
    if is_admin(user_id) and message.text in ["📚 Fan qo'shish", "🗑 Fanni o'chirish", "➕ Test qo'shish"]:
        return
        
    conn = sqlite3.connect('bot.db')
    cursor = conn.cursor()
    cursor.execute('SELECT status FROM users WHERE user_id = ?', (user_id,))
    row = cursor.fetchone()
    conn.close()
    
    if not row or row[0] != 'approved':
        return
        
    conn = sqlite3.connect('bot.db')
    cursor = conn.cursor()
    sub_name = message.text
    cursor.execute('SELECT id FROM subjects WHERE name = ?', (sub_name,))
    sub = cursor.fetchone()
    conn.close()
    
    if sub:
        conn = sqlite3.connect('bot.db')
        cursor = conn.cursor()
        cursor.execute('SELECT id, question, options, correct FROM questions WHERE subject_id = ?', (sub[0],))
        all_qs = cursor.fetchall()
        conn.close()
        if not all_qs:
            bot.send_message(message.chat.id, "Bu fanda hali testlar mavjud emas.")
            return
        random.shuffle(all_qs)
        user_test_data[user_id] = {'questions': all_qs[:50], 'current_index': 0, 'score': 0}
        send_question(message.chat.id, user_id)

def send_question(chat_id, user_id):
    data = user_test_data.get(user_id)
    if not data or data['current_index'] >= len(data['questions']):
        total_q = len(data['questions'])
        correct_count = data['score']
        score_100 = round((correct_count / total_q) * 100, 1)
        
        if score_100 >= 86:
            grade = "5 (A'lo) 🌟"
        elif score_100 >= 71:
            grade = "4 (Yaxshi) 👍"
        elif score_100 >= 56:
            grade = "3 (Qoniqarli) ✍️"
        else:
            grade = "2 (Qoniqarsiz) ❌"
            
        result_text = (
            f"🎉 <b>Test yakunlandi!</b>\n\n"
            f"📊 Natijangiz: <b>{correct_count} / {total_q}</b>\n"
            f"💯 100 ballik tizimda: <b>{score_100} ball</b>\n"
            f"🎓 Bahoyingiz: <b>{grade}</b>"
        )
        
        bot.send_message(chat_id, result_text, parse_mode='HTML')
        del user_test_data[user_id]
        show_subjects(chat_id)
        return
        
    q = data['questions'][data['current_index']]
    options = q[2].split("|||")
    random.shuffle(options)
    markup = types.InlineKeyboardMarkup()
    for opt in options:
        markup.add(types.InlineKeyboardButton(opt, callback_data=f"ans_{q[0]}_{opt}"))
    bot.send_message(chat_id, f"<b>{data['current_index']+1}-savol:</b>\n{q[1]}", parse_mode='HTML', reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('ans_'))
def check_ans(call):
    user_id = call.from_user.id
    if user_id not in user_test_data:
        bot.answer_callback_query(call.id, "Vaqt tugagan yoki test qaytadan boshlangan.")
        return
    parts = call.data.split('_', 2)
    selected = parts[2]
    data = user_test_data[user_id]
    q = data['questions'][data['current_index']]
    correct_ans = q[3]
    
    bot.answer_callback_query(call.id)
    
    markup = types.InlineKeyboardMarkup()
    options = q[2].split("|||")
    
    for opt in options:
        if opt == correct_ans:
            btn_text = f"✅ {opt} (To'g'ri javob)"
        elif opt == selected and selected != correct_ans:
            btn_text = f"❌ {opt} (Sizning xato tanlovingiz)"
        else:
            btn_text = f"▫️ {opt}"
        markup.add(types.InlineKeyboardButton(btn_text, callback_data="none"))
        
    if selected == correct_ans:
        data['score'] += 1
        status_line = "\n\n✅ <b>To'g'ri topdingiz!</b>"
    else:
        status_line = f"\n\n❌ <b>Xato!</b>\n🟢 To'g'ri javob: <b>{correct_ans}</b> edi."
        
    bot.edit_message_text(f"<b>{data['current_index']+1}-savol:</b>\n{q[1]}{status_line}", 
                          call.message.chat.id, call.message.message_id, parse_mode='HTML', reply_markup=markup)
    
    data['current_index'] += 1
    time.sleep(1.2)
    send_question(call.message.chat.id, user_id)

print("Bot ishga tushdi...")
bot.infinity_polling()
