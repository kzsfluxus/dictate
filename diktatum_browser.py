#!/usr/bin/env python3
"""
Diktátum fájl böngésző terminál alkalmazás.
Lehetővé teszi a diktátum txt fájlok böngészését és szerkesztését vim-ben.
"""

import re
import subprocess
import sys
from pathlib import Path

try:
    import curses
except ImportError:
    print("A curses modul szükséges a futtatáshoz.")
    sys.exit(1)

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
        footer = "↑↓←→: navigáció | Enter: megnyitás | q: kilépés"
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
        if key in (curses.KEY_ENTER, 10, 13):
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