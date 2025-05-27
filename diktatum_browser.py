#!/usr/bin/env python3
"""
Diktátum fájl böngésző terminál alkalmazás.
Lehetővé teszi a diktátum txt fájlok böngészését és szerkesztését vim-ben.
Email küldés funkció Gmail SMTP-vel.
"""

import json
import re
import smtplib
import subprocess
import sys
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

try:
    import curses
except ImportError:
    print("A curses modul szükséges a futtatáshoz.")
    sys.exit(1)

CONFIG_FILE = "email_config.json"

def load_config():
    """Email konfiguráció betöltése"""
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as file:
            return json.load(file)
    except FileNotFoundError:
        # Alapértelmezett konfig létrehozása
        default_config = {
            "smtp_server": "smtp.gmail.com",
            "smtp_port": 587,
            "email": "your_email@gmail.com",
            "password": "your_app_password",
            "sender_name": "Diktátum rendszer"
        }
        with open(CONFIG_FILE, 'w', encoding='utf-8') as file:
            json.dump(default_config, file, indent=2, ensure_ascii=False)
        print(f"Alapértelmezett konfiguráció létrehozva: {CONFIG_FILE}")
        print("Kérlek töltsd ki az email adatokkal!")
        return default_config

def get_txt_files():
    """Diktátum txt fájlok listázása az időbélyeg kinyerésével"""
    diktatum_dir = Path("diktatum")
    if not diktatum_dir.exists():
        return []

    files = []
    pattern = r'diktatum_(\d{4}-\d{2}-\d{2}_\d{2}:\d{2}:\d{2})\.txt'

    for file_path in diktatum_dir.glob("*.txt"):
        match = re.match(pattern, file_path.name)
        if match:
            timestamp = match.group(1)
            files.append({
                'display': timestamp,
                'filename': file_path.name,
                'full_path': str(file_path)
            })

    # Időrend szerinti rendezés (legújabb elől)
    files.sort(key=lambda x: x['display'], reverse=True)
    return files

def read_file_content(file_path):
    """Fájl tartalmának beolvasása a 4. sortól kezdve"""
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            lines = file.readlines()

        # A 4. sortól kezdve (index 3-tól)
        if len(lines) > 3:
            content = ''.join(lines[3:]).strip()
            return content
        return ""
    except Exception as err:
        return f"Hiba a fájl olvasásakor: {err}"

def send_email(config, recipient, subject, body):
    """Email küldése Gmail SMTP-vel"""
    try:
        # Email üzenet összeállítása
        msg = MIMEMultipart()
        msg['From'] = f"{config['sender_name']} <{config['email']}>"
        msg['To'] = recipient
        msg['Subject'] = subject

        msg.attach(MIMEText(body, 'plain', 'utf-8'))

        # SMTP kapcsolat
        server = smtplib.SMTP(config['smtp_server'], config['smtp_port'])
        server.starttls()
        server.login(config['email'], config['password'])

        # Email küldése
        text = msg.as_string()
        server.sendmail(config['email'], recipient, text)
        server.quit()

        return True, "Email sikeresen elküldve!"

    except Exception as err:
        return False, f"Hiba az email küldésekor: {err}"

def email_dialog(stdscr, file_path):
    """Email küldési dialógus ablak"""
    height, width = stdscr.getmaxyx()

    # Dialógus ablak méretei
    dialog_height = 14
    dialog_width = min(64, width - 4)
    start_y = (height - dialog_height) // 2
    start_x = (width - dialog_width) // 2

    # Fájl tartalmának beolvasása
    email_body = read_file_content(file_path)

    # Dialógus ablak
    dialog_win = curses.newwin(dialog_height, dialog_width, start_y, start_x)
    dialog_win.box()
    dialog_win.addstr(1, 2, "Email küldése", curses.A_BOLD)

    # Címzett beviteli mező
    dialog_win.addstr(3, 2, "Címzett:")
    recipient_win = curses.newwin(1, dialog_width - 12, start_y + 3, start_x + 10)

    # Tárgy beviteli mező
    dialog_win.addstr(5, 2, "Tárgy:")
    subject_win = curses.newwin(1, dialog_width - 10, start_y + 5, start_x + 8)

    # Törzs előnézet
    dialog_win.addstr(7, 2, "Törzs előnézet:")
    preview_text = email_body[:100] + "..." if len(email_body) > 100 else email_body
    dialog_win.addstr(8, 2, preview_text[:dialog_width-4])

    # Utasítások
    dialog_win.addstr(12, 2, "Enter: tovább")

    dialog_win.refresh()

    # Beviteli mezők kezelése
    curses.echo()

    # Címzett bekérése
    recipient_win.refresh()
    recipient = recipient_win.getstr(0, 0, dialog_width - 13).decode('utf-8')

    # Tárgy bekérése
    subject_win.refresh()
    subject = subject_win.getstr(0, 0, dialog_width - 11).decode('utf-8')

    curses.noecho()

    # Megerősítés
    dialog_win.addstr(10, 2, f"Küldés: {recipient}")
    dialog_win.addstr(12, 2, "s: küldés | Esc: mégse   ")
    dialog_win.refresh()

    while True:
        key = dialog_win.getch()
        if key == ord('s'):
            # Email küldése
            config = load_config()
            success, message = send_email(config, recipient, subject, email_body)

            # Eredmény megjelenítése
            dialog_win.clear()
            dialog_win.box()
            dialog_win.addstr(1, 2, "Email küldés eredménye", curses.A_BOLD)

            # Üzenet megjelenítése (több sorban ha szükséges)
            lines = [message[i:i+dialog_width-4] for i in range(0, len(message), dialog_width-4)]
            for i, line in enumerate(lines[:6]):  # Max 6 sor
                dialog_win.addstr(3 + i, 2, line)

            dialog_win.addstr(dialog_height - 2, 2, "Nyomj egy billentyűt...")
            dialog_win.refresh()
            dialog_win.getch()
            return success

        if key == 27:  # Esc
            return False

def calculate_layout(stdscr, files):
    """Terminál méretből számítjuk ki az elrendezést"""
    height, width = stdscr.getmaxyx()

    # Tájékozódáshoz nézzük meg egy elem szélességét
    if not files:
        return 1, 1, []

    # Egy elem szélessége: timestamp + padding
    item_width = max(len(f['display']) for f in files) + 4

    # Hány oszlop fér el
    cols = max(1, width // item_width)

    # Hány sor szükséges
    rows_needed = (len(files) + cols - 1) // cols

    # Elérhető sorok (header és footer miatt -3)
    available_rows = height - 3

    if rows_needed <= available_rows:
        # Minden fér egy képernyőre
        return cols, rows_needed, files
    # Lapozni kell
    return cols, available_rows, files

def draw_screen(stdscr, files, selected_idx, scroll_offset, cols, visible_rows):
    """Képernyő kirajzolása - egyszerűsített verzió a túl sok ág elkerülésére"""
    stdscr.clear()
    height, width = stdscr.getmaxyx()

    # Header
    title = "Diktátum fájlok"
    stdscr.addstr(0, (width - len(title)) // 2, title, curses.A_BOLD)

    if not files:
        stdscr.addstr(height // 2, (width - len("Nincsenek txt fájlok")) // 2,
                     "Nincsenek txt fájlok")
        stdscr.refresh()
        return

    # Fájlok megjelenítése
    _draw_files(stdscr, files, selected_idx, scroll_offset, cols, visible_rows, height, width)
    _draw_footer_and_scroll(stdscr, files, cols, visible_rows, scroll_offset, height, width)

    stdscr.refresh()

def _draw_files(stdscr, files, selected_idx, scroll_offset, cols, visible_rows, height, width):
    """Fájlok kirajzolása"""
    start_row = 2
    item_width = max(len(f['display']) for f in files) + 4

    visible_files = files[scroll_offset:scroll_offset + (cols * visible_rows)]

    for i, file_info in enumerate(visible_files):
        row = start_row + (i // cols)
        col = (i % cols) * item_width

        # Kiválasztott elem kiemelése
        attr = curses.A_REVERSE if scroll_offset + i == selected_idx else curses.A_NORMAL

        # Ellenőrizzük, hogy nem lógunk-e ki a képernyőből
        if row < height - 1 and col + len(file_info['display']) < width:
            stdscr.addstr(row, col, file_info['display'], attr)

def _draw_footer_and_scroll(stdscr, files, cols, visible_rows, scroll_offset, height, width):
    """Footer és scroll indikátor kirajzolása"""
    # Footer
    if height > 2:
        footer = "↑↓←→: navigáció | Enter: megnyitás | m: email | q: kilépés"
        footer_row = height - 1
        if len(footer) <= width:
            stdscr.addstr(footer_row, 0, footer)

    # Scroll indikátor
    if len(files) > cols * visible_rows:
        progress = f"{scroll_offset // cols + 1}/{(len(files) + cols - 1) // cols}"
        if len(progress) <= width:
            stdscr.addstr(1, width - len(progress), progress)

def open_file_in_vim(file_path):
    """Fájl megnyitása vim-ben"""
    curses.endwin()  # Curses mód kikapcsolása
    try:
        subprocess.run(['vim', file_path], check=True)
    except FileNotFoundError:
        print("A vim szerkesztő nem található!")
        input("Nyomj Enter-t a folytatáshoz...")
    except subprocess.CalledProcessError as subprocess_error:
        print(f"Hiba a vim futtatásakor: {subprocess_error}")
        input("Nyomj Enter-t a folytatáshoz...")

    # Curses újraindítása
    new_stdscr = curses.initscr()
    curses.noecho()
    curses.cbreak()
    new_stdscr.keypad(True)
    return new_stdscr

def _handle_navigation(key, selected_idx, files, cols):
    """Navigáció kezelése"""
    if key == curses.KEY_UP and selected_idx >= cols:
        return selected_idx - cols
    if key == curses.KEY_DOWN and selected_idx + cols < len(files):
        return selected_idx + cols
    if key == curses.KEY_LEFT and selected_idx > 0:
        return selected_idx - 1
    if key == curses.KEY_RIGHT and selected_idx < len(files) - 1:
        return selected_idx + 1
    return selected_idx

def _update_scroll_offset(selected_idx, scroll_offset, cols, visible_rows):
    """Scroll offset frissítése a kiválasztott elem alapján"""
    visible_start = scroll_offset
    visible_end = scroll_offset + (cols * visible_rows) - 1

    if selected_idx < visible_start:
        return (selected_idx // cols) * cols
    if selected_idx > visible_end:
        new_offset = ((selected_idx - cols * visible_rows + 1) // cols) * cols
        return max(0, new_offset)
    return scroll_offset

def main(stdscr):
    """Főprogram"""
    # Curses beállítások
    curses.noecho()
    curses.cbreak()
    stdscr.keypad(True)

    files = get_txt_files()
    selected_idx = 0
    scroll_offset = 0

    while True:
        cols, visible_rows = calculate_layout(stdscr, files)[:2]

        # Scroll offset korrekciója
        max_scroll = max(0, len(files) - (cols * visible_rows))
        scroll_offset = min(scroll_offset, max_scroll)

        # Kiválasztott elem láthatóságának ellenőrzése
        scroll_offset = _update_scroll_offset(selected_idx, scroll_offset, cols, visible_rows)

        draw_screen(stdscr, files, selected_idx, scroll_offset, cols, visible_rows)

        if not files:
            key = stdscr.getch()
            if key == ord('q'):
                break
            continue

        key = stdscr.getch()

        if key == ord('q'):
            break
        if key == ord('m'):
            # Email küldés
            if 0 <= selected_idx < len(files):
                file_path = files[selected_idx]['full_path']
                email_dialog(stdscr, file_path)
        elif key in (curses.KEY_ENTER, 10, 13):
            if 0 <= selected_idx < len(files):
                file_path = files[selected_idx]['full_path']
                stdscr = open_file_in_vim(file_path)
                # Fájlok újratöltése (esetleg változtak)
                files = get_txt_files()
                if selected_idx >= len(files):
                    selected_idx = max(0, len(files) - 1)
        else:
            selected_idx = _handle_navigation(key, selected_idx, files, cols)

if __name__ == "__main__":
    try:
        curses.wrapper(main)
    except KeyboardInterrupt:
        print("\nKilépés...")
    except Exception as error:
        print(f"Hiba: {error}")
