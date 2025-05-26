#!/usr/bin/env python3
"""
Magyar nyelvű diktáló program Whisper használatával
Használat: python dictate.py [--model MODEL_SIZE] [--output-dir DIR]
"""

import argparse
import datetime
import os
import sys
import tempfile
import threading
import logging
from pathlib import Path

try:
    import whisper
    import pyaudio
    import wave
    import select
    import tty
    import termios
except ImportError as e:
    print(f"Hiányzó függőség: {e}")
    print("Telepítsd a szükséges csomagokat:")
    print("pip install openai-whisper pyaudio")
    sys.exit(1)

class HungarianDictation:
    def __init__(self, model_size="base", output_dir="diktatum"):
        """
        Inicializálja a diktáló rendszert
        
        Args:
            model_size: Whisper model mérete (tiny, base, small, medium, large)
            output_dir: Kimeneti könyvtár neve
        """
        self.model_size = model_size
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        # Logging beállítása
        self.setup_logging()
        
        # Audio beállítások
        self.chunk = 1024
        self.format = pyaudio.paInt16
        self.channels = 1
        self.rate = 16000
        
        # ALSA hibák elnyomása
        import os

        os.environ['ALSA_CARD'] = 'default'
        
        self.audio = pyaudio.PyAudio()
        self.recording = False
        self.frames = []
        
        # Terminal beállítások billentyűzet olvasáshoz
        self.old_settings = None

        print(f"Whisper model betöltése ({model_size})...")
        self.logger.info(f"Whisper model betöltése: {model_size}")
        try:
            self.model = whisper.load_model(model_size)
            print("Model sikeresen betöltve!")
            self.logger.info("Whisper model sikeresen betöltve")
        except Exception as e:
            print(f"Hiba a model betöltésekor: {e}")
            self.logger.error(f"Hiba a model betöltésekor: {e}")
            sys.exit(1)
    
    def setup_logging(self):
        """Logging beállítása"""
        log_file = self.output_dir / "dictate.log"

        # Logger létrehozása
        self.logger = logging.getLogger('dictate')
        self.logger.setLevel(logging.INFO)
 
        # File handler
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.INFO)
        
        # Formátum beállítása
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(formatter)
        
        # Handler hozzáadása
        if not self.logger.handlers:  # Elkerüli a duplikálást
            self.logger.addHandler(file_handler)
        
        self.logger.info("="*50)
        self.logger.info("Dictate program elindítva")
    
    def start_recording(self):
        """Elindítja a hangfelvételt"""
        if self.recording:
            return
            
        self.recording = True
        self.frames = []
        
        try:
            self.stream = self.audio.open(
                format=self.format,
                channels=self.channels,
                rate=self.rate,
                input=True,
                frames_per_buffer=self.chunk
            )
            
            print("🎤 Felvétel elkezdve...")
            self.logger.info("Hangfelvétel elindítva")
            
            # Háttérben fut a felvétel
            self.record_thread = threading.Thread(target=self._record_audio)
            self.record_thread.start()
            
        except Exception as e:
            print(f"Hiba a felvétel indításakor: {e}")
            self.logger.error(f"Hiba a felvétel indításakor: {e}")
            self.recording = False
    
    def _record_audio(self):
        """Háttérben rögzíti a hangot"""
        frame_count = 0
        while self.recording:
            try:
                data = self.stream.read(self.chunk, exception_on_overflow=False)
                self.frames.append(data)
                frame_count += 1
                
                # Logolás minden 100 frame-nél (kb. másodpercenként)
                if frame_count % 100 == 0:
                    duration = frame_count * self.chunk / self.rate
                    self.logger.debug(f"Felvétel folyik: {duration:.1f} másodperc")
                    
            except Exception as e:
                self.logger.error(f"Hiba a felvétel során: {e}")
                break
    
    def stop_recording(self):
        """Leállítja a hangfelvételt és feldolgozza"""
        if not self.recording:
            return
            
        self.recording = False
        print("⏹️  Felvétel leállítva, feldolgozás...")
        
        duration = len(self.frames) * self.chunk / self.rate
        self.logger.info(f"Felvétel leállítva, időtartam: {duration:.2f} másodperc")
        
        # Várjuk meg a record thread befejeződését
        if hasattr(self, 'record_thread'):
            self.record_thread.join()
        
        try:
            self.stream.stop_stream()
            self.stream.close()
        except Exception as e:
            self.logger.warning(f"Stream zárási hiba: {e}")
        
        if not self.frames:
            print("Nincs rögzített hang.")
            self.logger.warning("Nincs rögzített hang")
            return
        
        # Ideiglenes fájl létrehozása
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
            temp_filename = temp_file.name
            
            # WAV fájl írása
            wf = wave.open(temp_filename, 'wb')
            wf.setnchannels(self.channels)
            wf.setsampwidth(self.audio.get_sample_size(self.format))
            wf.setframerate(self.rate)
            wf.writeframes(b''.join(self.frames))
            wf.close()
        
        self.logger.info(f"Ideiglenes WAV fájl létrehozva: {temp_filename}")
        
        # Whisper feldolgozás
        try:
            print("🤖 Beszédfelismerés folyamatban...")
            self.logger.info("Whisper feldolgozás elkezdve")
            
            result = self.model.transcribe(
                temp_filename, 
                language="hu",  # Magyar nyelv
                task="transcribe"
            )
            
            transcribed_text = result["text"].strip()
            self.logger.info(f"Whisper eredmény: '{transcribed_text}' (konfidencia adatok: {result.get('segments', [])})")
            
            if transcribed_text:
                self.save_transcription(transcribed_text)
                print(f"✅ Szöveg mentve!")
                print(f"📝 Felismert szöveg: {transcribed_text}")
            else:
                print("❌ Nem sikerült szöveget felismerni.")
                self.logger.warning("Üres szöveg eredmény a Whisper-től")
                
        except Exception as e:
            print(f"Hiba a beszédfelismerés során: {e}")
            self.logger.error(f"Whisper feldolgozási hiba: {e}")
        finally:
            # Ideiglenes fájl törlése
            try:
                os.unlink(temp_filename)
                self.logger.info("Ideiglenes fájl törölve")
            except Exception as e:
                self.logger.warning(f"Ideiglenes fájl törlési hiba: {e}")
    
    def save_transcription(self, text):
        """Elmenti a felismert szöveget időbélyeggel ellátott fájlba"""
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H:%M:%S")
        filename = f"diktatum_{timestamp}.txt"
        filepath = self.output_dir / filename
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(f"Diktálás időpontja: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("-" * 50 + "\n\n")
                f.write(text)
                f.write("\n")
            
            print(f"📁 Fájl mentve: {filepath}")
            self.logger.info(f"Szöveg fájl mentve: {filepath}")
            self.logger.info(f"Mentett szöveg: '{text}'")
            
        except Exception as e:
            print(f"Hiba a fájl mentésekor: {e}")
            self.logger.error(f"Fájl mentési hiba: {e}")
    
    def cleanup(self):
        """Tisztítás"""
        self.logger.info("Program leállítás")
        if self.old_settings:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self.old_settings)
        self.audio.terminate()
        self.logger.info("Cleanup befejezve")
    
    def get_key(self):
        """Billentyű olvasása root jogosultság nélkül"""
        if select.select([sys.stdin], [], [], 0) == ([sys.stdin], [], []):
            key = sys.stdin.read(1)
            return key
        return None
    
    def run(self):
        """Főprogram futtatása"""
        os.system('clear') 
        print("=" * 60)
        print("🎙️  WHISPER DIKTÁLÓ - FLUX")
        print("=" * 60)
        print()
        print("Irányítás:")
        print("  SPACE vagy s + ENTER - Felvétel indítása/leállítása")
        print("  q + ENTER       - Kilépés")
        print(f"  Fájlok mentési helye: {self.output_dir.absolute()}")
        print(f"  Logfájl: {self.output_dir.absolute()}/dictate.log")
        print()
        print("Várakozás parancsra...")
        
        self.logger.info("Felhasználói interfész elindítva")
        
        try:
            # Terminal raw módba állítása
            self.old_settings = termios.tcgetattr(sys.stdin)
            tty.setraw(sys.stdin.fileno())
            
            while True:
                # Visszaállítjuk a normál módot input olvasáshoz
                termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self.old_settings)
                
                try:
                    command = input("\n> ").strip().lower()
                    self.logger.info(f"Felhasználói parancs: '{command}'")
                except EOFError:
                    break
                
                if command in ['s', 'space', '']:
                    if not self.recording:
                        self.start_recording()
                    else:
                        self.stop_recording()
                
                elif command in ['q', 'quit', 'exit']:
                    if self.recording:
                        self.stop_recording()
                    print("\n👋 Viszlát!")
                    self.logger.info("Felhasználó kilépett")
                    break
                    
                elif command == 'help':
                    print("\nElérhető parancsok:")
                    print("  s, space, ENTER - Felvétel indítása/leállítása")
                    print("  q, quit, exit   - Kilépés")
                    print("  help           - Súgó megjelenítése")
                    self.logger.info("Súgó megjelenítve")
                
                else:
                    self.logger.info(f"Ismeretlen parancs: '{command}'")
                
                # Raw módba visszaállítás
                tty.setraw(sys.stdin.fileno())
                        
        except KeyboardInterrupt:
            if self.recording:
                self.stop_recording()
            print("\n👋 Program megszakítva.")
            self.logger.info("Program megszakítva (Ctrl+C)")
        
        finally:
            self.cleanup()

def main():
    parser = argparse.ArgumentParser(
        description="Magyar nyelvű diktáló program Whisper használatával"
    )
    parser.add_argument(
        "--model", 
        choices=["tiny", "base", "small", "medium", "large"],
        default="base",
        help="Whisper model mérete (alapértelmezett: base)"
    )
    parser.add_argument(
        "--output-dir",
        default="diktatum",
        help="Kimeneti könyvtár (alapértelmezett: diktatum)"
    )
    
    args = parser.parse_args()
    
    print("Függőségek ellenőrzése...")
    
    # Rendszerkövetelmények ellenőrzése
    try:
        # ALSA hibák elnyomása
        import contextlib
        import os
        
        # PyAudio ALSA hibák elnyomása
        with contextlib.redirect_stderr(open(os.devnull, 'w')):
            audio = pyaudio.PyAudio()
            info = audio.get_host_api_info_by_index(0)
            audio.terminate()
    except Exception as e:
        print(f"❌ Mikrofon hiba: {e}")
        print("Ellenőrizd, hogy a mikrofon csatlakoztatva van és használható.")
        return
    
    dictation = HungarianDictation(
        model_size=args.model,
        output_dir=args.output_dir
    )
    
    dictation.run()

if __name__ == "__main__":
    main()
