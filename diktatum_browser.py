#!/usr/bin/env python3
"""
Leirat fájl böngésző terminál alkalmazás.
Lehetővé teszi a diktátum txt fájlok böngészését és szerkesztését vim-ben.
Email küldés funkció Gmail SMTP-vel és címlista kezeléssel.
"""

import json
import os
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
ADDRESSES_DIR = "addresses"
EMAILS_FILE = os.path.join(ADDRESSES_DIR, "emails.txt")

def ensure_addresses_directory():
    """Addresses mappa és emails.txt fájl létrehozása ha szükséges"""
    if not os.path.exists(ADDRESSES_DIR):
        os.makedirs(ADDRESSES_DIR)

    if not os.path.exists(EMAILS_FILE):
        with open(EMAILS_FILE, 'w', encoding='utf-8') as file:
            file.write("")

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

def load_email_addresses():
    """Emailcímek betöltése a fájlból"""
    try:
        with open(EMAILS_FILE, 'r', encoding='utf-8') as file:
            addresses = [line.strip() for line in file.readlines() if line.strip()]
        return sorted(addresses)
    except FileNotFoundError:
        return []

def save_email_address(email):
    """Emailcím hozzáadása a listához ha még nincs benne"""
    addresses = load_email_addresses()

    if email and email not in addresses:
        addresses.append(email)
        addresses.sort()

        with open(EMAILS_FILE, 'w', encoding='utf-8') as file:
            for addr in addresses:
                file.write(addr + '\n')

def email_address_selector(stdscr):
    """Emailcím választó ablak"""
    addresses = load_email_addresses()

    if not addresses:
        # Üres lista esetén
        height, width = stdscr.getmaxyx()
        dialog_height = 7
        dialog_width = 50
        start_y = (height - dialog_height) // 2
        start_x = (width - dialog_width) // 2

        dialog_win = curses.newwin(dialog_height, dialog_width, start_y, start_x)
        dialog_win.box()
        dialog_win.addstr(1, 2, "Címlista üres", curses.A_BOLD)
        dialog_win.addstr(3, 2, "Még nincsenek mentett emailcímek.")
        dialog_win.addstr(5, 2, "Nyomj egy billentyűt...")
        dialog_win.refresh()
        dialog_win.getch()
        return None

    # Címválasztó ablak
    height, width = stdscr.getmaxyx()
    dialog_height = min(20, height - 4)
    dialog_width = min(60, width - 4)
    start_y = (height - dialog_height) // 2
    start_x = (width - dialog_width) // 2

    dialog_win = curses.newwin(dialog_height, dialog_width, start_y, start_x)
    dialog_win.keypad(True)  # ← Ez a fontos sor!

    selected_idx = 0
    scroll_offset = 0
    visible_items = dialog_height - 4  # Hely a lista elemeinek

    while True:
        dialog_win.clear()
        dialog_win.box()
        dialog_win.addstr(1, 2, "Emailcím választása", curses.A_BOLD)

        # Navigációs útmutató
        nav_text = "↑↓: navigálás | Enter: választás | Esc: kilépés"
        dialog_win.addstr(dialog_height - 2, 2, nav_text)

        # Lista megjelenítése
        start_display = scroll_offset
        end_display = min(start_display + visible_items, len(addresses))

        for i, addr in enumerate(addresses[start_display:end_display]):
            y_pos = 2 + i
            display_idx = start_display + i

            # Kiválasztott elem kiemelése
            if display_idx == selected_idx:
                attr = curses.A_REVERSE
            else:
                attr = curses.A_NORMAL

            # Cím megjelenítése (csonkolva ha túl hosszú)
            display_addr = addr[:dialog_width - 6] + "..." if len(addr) > dialog_width - 6 else addr
            dialog_win.addstr(y_pos, 2, display_addr, attr)

        dialog_win.refresh()

        key = dialog_win.getch()

        if key == 27:  # Esc
            return None
        if key in (curses.KEY_ENTER, 10, 13):  # Enter
            return addresses[selected_idx]
        elif key in (curses.KEY_UP, ord('k')):  # Fel nyíl vagy k
            if selected_idx > 0:
                selected_idx -= 1
                if selected_idx < scroll_offset:
                    scroll_offset = selected_idx
        elif key in (curses.KEY_DOWN, ord('j')):  # Le nyíl vagy j
            if selected_idx < len(addresses) - 1:
                selected_idx += 1
                if selected_idx >= scroll_offset + visible_items:
                    scroll_offset = selected_idx - visible_items + 1


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
    except (FileNotFoundError, PermissionError, UnicodeDecodeError) as err:
        return f"Hiba a fájl olvasásakor: {err}"

def get_file_preview(file_path):
    """Fájl 4. sorának első 50 karakterének lekérése"""
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            lines = file.readlines()
        
        # A 4. sor (index 3) első 50 karaktere
        if len(lines) > 3:
            fourth_line = lines[3].strip()
            if fourth_line:
                return fourth_line if len(fourth_line) <= 60 else fourth_line[:60] + ' ...'
        return ""
    except (FileNotFoundError, PermissionError, UnicodeDecodeError):
        return "Hiba a fájl olvasásakor"

def send_email_smtp(server_config, message_data):
    """SMTP email küldés - külön funkció a kivételkezelés javításához"""
    server = smtplib.SMTP(server_config['smtp_server'], server_config['smtp_port'])
    server.starttls()
    server.login(server_config['email'], server_config['password'])

    text = message_data['msg'].as_string()
    server.sendmail(server_config['email'], message_data['recipient'], text)
    server.quit()

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
        message_data = {'msg': msg, 'recipient': recipient}
        send_email_smtp(config, message_data)

        return True, "Email sikeresen elküldve!"

    except (smtplib.SMTPException, ConnectionError, OSError) as err:
        return False, f"Hiba az email küldésekor: {err}"

def create_email_dialog_window(stdscr):
    """Email dialógus ablak létrehozása"""
    height, width = stdscr.getmaxyx()

    # Dialógus ablak méretei
    dialog_height = 16
    dialog_width = min(64, width - 4)
    start_y = (height - dialog_height) // 2
    start_x = (width - dialog_width) // 2

    return {
        'dialog_height': dialog_height,
        'dialog_width': dialog_width,
        'start_y': start_y,
        'start_x': start_x
    }

def setup_dialog_ui(dialog_win, dialog_config, email_body):
    """Email dialógus UI elemeinek beállítása"""
    dialog_win.box()
    dialog_win.addstr(1, 2, "Email küldése", curses.A_BOLD)

    # Címzett és tárgy beviteli mezők
    dialog_win.addstr(3, 2, "Címzett:")
    dialog_win.addstr(5, 2, "Tárgy:")

    # Törzs előnézet
    dialog_win.addstr(7, 2, "Törzs előnézet:")
    preview_text = email_body[:56] + "..." if len(email_body) > 56 else email_body
    dialog_win.addstr(8, 2, preview_text[:dialog_config['dialog_width']-4])

    # Új menüpont
    dialog_win.addstr(10, 2, "a: címzett választása listából")
    dialog_win.addstr(14, 2, "Enter: tovább")
    dialog_win.refresh()

def get_email_inputs(stdscr, dialog_config):
    """Email beviteli mezők kezelése címválasztó opcióval"""
    # Email dialógus ablak újrarajzolása címválasztó opcióval
    dialog_win = curses.newwin(dialog_config['dialog_height'], dialog_config['dialog_width'],
                              dialog_config['start_y'], dialog_config['start_x'])

    recipient = ""
    subject = ""

    while True:
        dialog_win.clear()
        dialog_win.box()
        dialog_win.addstr(1, 2, "Email küldése", curses.A_BOLD)
        dialog_win.addstr(3, 2, f"Címzett: {recipient}")
        dialog_win.addstr(5, 2, f"Tárgy: {subject}")

        if not recipient:
            dialog_win.addstr(9, 2, "a: címzett választása listából")
            dialog_win.addstr(10, 2, "r: címzett manuális bevitele")
            dialog_win.addstr(11, 2, "Esc: mégse")
        elif not subject:
            dialog_win.addstr(9, 2, "t: tárgy bevitele")
            dialog_win.addstr(10, 2, "Esc: vissza")
        else:
            dialog_win.addstr(9, 2, "Enter: email megtekintése")
            dialog_win.addstr(10, 2, "r: címzett módosítása")
            dialog_win.addstr(11, 2, "t: tárgy módosítása")
            dialog_win.addstr(12, 2, "Esc: mégse")

        dialog_win.refresh()

        key = dialog_win.getch()

        if key == 27:  # Esc
            return None, None
        if key == ord('a') and not recipient:
            # Címválasztó megnyitása
            selected_email = email_address_selector(stdscr)
            if selected_email:
                recipient = selected_email
        elif key == ord('r'):
            # Manuális címbevitel
            dialog_win.addstr(7, 2, "Emailcím:")
            dialog_win.refresh()

            recipient_win = curses.newwin(1, dialog_config['dialog_width'] - 14,
                                        dialog_config['start_y'] + 7, dialog_config['start_x'] + 12)
            curses.echo()
            recipient_win.refresh()
            new_recipient = recipient_win.getstr(0, 0, dialog_config['dialog_width'] - 15).decode('utf-8')
            curses.noecho()

            if new_recipient.strip():
                recipient = new_recipient.strip()
        elif key == ord('t') and recipient:
            # Tárgy bevitele
            dialog_win.addstr(7, 2, "Tárgy:")
            dialog_win.refresh()

            subject_win = curses.newwin(1, dialog_config['dialog_width'] - 10,
                                      dialog_config['start_y'] + 7, dialog_config['start_x'] + 8)
            curses.echo()
            subject_win.refresh()
            new_subject = subject_win.getstr(0, 0, dialog_config['dialog_width'] - 11).decode('utf-8')
            curses.noecho()

            if new_subject.strip():
                subject = new_subject.strip()
        elif key in (curses.KEY_ENTER, 10, 13) and recipient and subject:
            return recipient, subject

def show_email_result(dialog_win, dialog_config, message):
    """Email küldés eredményének megjelenítése"""
    dialog_win.clear()
    dialog_win.box()
    dialog_win.addstr(1, 2, "Email küldés eredménye", curses.A_BOLD)

    # Üzenet megjelenítése (több sorban ha szükséges)
    lines = [message[i:i+dialog_config['dialog_width']-4]
             for i in range(0, len(message), dialog_config['dialog_width']-4)]
    for i, line in enumerate(lines[:6]):  # Max 6 sor
        dialog_win.addstr(3 + i, 2, line)

    dialog_win.addstr(dialog_config['dialog_height'] - 2, 2, "Nyomj egy billentyűt...")
    dialog_win.refresh()
    dialog_win.getch()

def email_dialog(stdscr, file_path):
    """Email küldési dialógus ablak"""
    # Addresses mappa létrehozása
    ensure_addresses_directory()

    dialog_config = create_email_dialog_window(stdscr)

    # Fájl tartalmának beolvasása
    email_body = read_file_content(file_path)

    # Beviteli mezők kezelése
    recipient, subject = get_email_inputs(stdscr, dialog_config)

    if not recipient or not subject:
        return False

    # Megerősítő dialógus
    dialog_win = curses.newwin(dialog_config['dialog_height'], dialog_config['dialog_width'],
                              dialog_config['start_y'], dialog_config['start_x'])

    dialog_win.clear()
    dialog_win.box()
    dialog_win.addstr(1, 2, "Email küldése - megerősítés", curses.A_BOLD)
    dialog_win.addstr(3, 2, f"Címzett: {recipient}")
    dialog_win.addstr(4, 2, f"Tárgy: {subject}")
    dialog_win.addstr(6, 2, "Törzs előnézet:")
    preview_text = email_body[:56] + "..." if len(email_body) > 56 else email_body
    dialog_win.addstr(7, 2, preview_text[:dialog_config['dialog_width']-4])

    dialog_win.addstr(10, 2, "s: küldés | Esc: mégse")
    dialog_win.refresh()

    while True:
        key = dialog_win.getch()
        if key == ord('s'):
            # Email küldése
            config = load_config()
            success, message = send_email(config, recipient, subject, email_body)

            # Emailcím mentése ha sikeres volt a küldés
            if success:
                save_email_address(recipient)

            # Eredmény megjelenítése
            show_email_result(dialog_win, dialog_config, message)
            return success

        if key == 27:  # Esc
            return False

def calculate_layout(stdscr, files):
    """Terminál méretből számítjuk ki az elrendezést - módosítva a betekintéshez"""
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

    # Elérhető sorok (header + betekintés + elválasztó + footer miatt -6)
    available_rows = height - 6

    if rows_needed <= available_rows:
        # Minden fér egy képernyőre
        return cols, rows_needed, files
    # Lapozni kell
    return cols, available_rows, files

def draw_screen(stdscr, files, selected_idx, scroll_offset):
    """Képernyő kirajzolása betekintéssel"""
    stdscr.clear()
    height, width = stdscr.getmaxyx()

    # Header
    title = "Leirat fájlok"
    stdscr.addstr(0, (width - len(title)) // 2, title, curses.A_BOLD)

    # Betekintés megjelenítése
    preview_text = ""
    if files and 0 <= selected_idx < len(files):
        preview_text = get_file_preview(files[selected_idx]['full_path'])
    
    # Betekintés sor (csak ha van szöveg)
    if preview_text:
        # Szöveg levágása ha túl hosszú a képernyőhöz
        display_preview = preview_text[:width-2] if len(preview_text) > width-2 else preview_text
        stdscr.addstr(1, 0, display_preview)
    
    # Elválasztó vonal (szaggatott)
    separator = "-" * width
    stdscr.addstr(2, 0, separator)

    if not files:
        stdscr.addstr(height // 2, (width - len("Nincsenek txt fájlok")) // 2,
                     "Nincsenek txt fájlok")
        stdscr.refresh()
        return

    cols, visible_rows = calculate_layout(stdscr, files)[:2]

    # Fájlok megjelenítése (3. sortól kezdve a betekintés és elválasztó miatt)
    _draw_files(stdscr, files, selected_idx, scroll_offset, cols, visible_rows)
    _draw_footer_and_scroll(stdscr, files, cols, visible_rows, scroll_offset)

    stdscr.refresh()

def _draw_files(stdscr, files, selected_idx, scroll_offset, cols, visible_rows):
    """Fájlok kirajzolása - módosítva a betekintéshez"""
    height, width = stdscr.getmaxyx()
    start_row = 3  # Módosítva: 3. sortól kezdjük a betekintés és elválasztó miatt
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

def _draw_footer_and_scroll(stdscr, files, cols, visible_rows, scroll_offset):
    """Footer és scroll indikátor kirajzolása"""
    height, width = stdscr.getmaxyx()

    # Footer
    if height > 2:
        footer = "↑↓←→: navigáció | Enter: megnyitás | m: email | q: kilépés"
        footer_row = height - 1
        if len(footer) <= width:
            stdscr.addstr(footer_row, 0, footer)

    # Scroll indikátor (módosítva: a 2. sorba kerül az elválasztó vonal mellé)
    if len(files) > cols * visible_rows:
        progress = f" {scroll_offset // cols + 1}/{(len(files) + cols - 1) // cols}"
        if len(progress) <= width:
            stdscr.addstr(2, width - len(progress), progress)

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

        draw_screen(stdscr, files, selected_idx, scroll_offset)

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
    except (OSError, RuntimeError) as error:
        print(f"Hiba: {error}")