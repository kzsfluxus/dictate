#!/usr/bin/env python3
"""
Magyar nyelvű diktáló program Whisper használatával
Használat: python dictate.py [--model MODEL_SIZE] [--output-dir DIR]
"""

import argparse
import contextlib
import datetime
import logging
import os
import sys
import tempfile
import threading
from pathlib import Path

try:
    import whisper
    import pyaudio
    import wave
    import select
    import tty
    import termios
except ImportError as import_error:
    print(f"Hiányzó függőség: {import_error}")
    print("Telepítsd a szükséges csomagokat:")
    print("pip install openai-whisper pyaudio")
    sys.exit(1)


class HungarianDictation:
    """Magyar nyelvű diktáló osztály Whisper használatával"""

    # pylint: disable=too-many-instance-attributes
    # Sok attribútum szükséges az audio kezeléshez és állapot követéshez

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
        self.logger = None
        self.setup_logging()

        # Audio beállítások
        self.chunk = 1024
        self.format = pyaudio.paInt16
        self.channels = 1
        self.rate = 16000

        os.environ['ALSA_CARD'] = 'default'

        self.audio = pyaudio.PyAudio()
        self.recording = False
        self.frames = []
        self.stream = None
        self.record_thread = None

        # Terminal beállítások billentyűzet olvasáshoz
        self.old_settings = None
        self.model = None

        print(f"Whisper model betöltése ({model_size})...")
        self.logger.info("Whisper model betöltése: %s", model_size)
        try:
            self.model = whisper.load_model(model_size)
            print("Model sikeresen betöltve!")
            self.logger.info("Whisper model sikeresen betöltve")
        except (OSError, RuntimeError, ValueError) as error:
            print(f"Hiba a model betöltésekor: {error}")
            self.logger.error("Hiba a model betöltésekor: %s", error)
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

        self.logger.info("=" * 50)
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

        except (OSError, ValueError, pyaudio.PyAudioError) as error:
            print(f"Hiba a felvétel indításakor: {error}")
            self.logger.error("Hiba a felvétel indításakor: %s", error)
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
                    self.logger.debug("Felvétel folyik: %.1f másodperc", duration)

            except (OSError, IOError, pyaudio.PyAudioError) as error:
                self.logger.error("Hiba a felvétel során: %s", error)
                break

    def stop_recording(self):
        """Leállítja a hangfelvételt és feldolgozza"""
        if not self.recording:
            return

        self.recording = False
        print("⏹️  Felvétel leállítva, feldolgozás...")

        duration = len(self.frames) * self.chunk / self.rate
        self.logger.info("Felvétel leállítva, időtartam: %.2f másodperc", duration)

        # Várjuk meg a record thread befejeződését
        if self.record_thread:
            self.record_thread.join()

        try:
            if self.stream:
                self.stream.stop_stream()
                self.stream.close()
        except (OSError, pyaudio.PyAudioError) as error:
            self.logger.warning("Stream zárási hiba: %s", error)

        if not self.frames:
            print("Nincs rögzített hang.")
            self.logger.warning("Nincs rögzített hang")
            return

        self._process_audio()

    def _check_audio_quality(self, audio_data):
        """Ellenőrzi az audio minőségét és csendet"""
        import numpy as np
        
        # Bytes to numpy array
        audio_array = np.frombuffer(b''.join(audio_data), dtype=np.int16)
        
        # Átlagos amplitúdó számítása
        avg_amplitude = np.mean(np.abs(audio_array))
        max_amplitude = np.max(np.abs(audio_array))
        
        # Csend küszöb (ezeket lehet finomhangolni)
        silence_threshold = 500  # Nagyon alacsony hang küszöb
        min_max_amplitude = 1000  # Minimális maximális amplitúdó
        
        self.logger.info("Audio statisztikák - Átlag: %.1f, Max: %.1f", 
                        avg_amplitude, max_amplitude)
        
        is_mostly_silent = (avg_amplitude < silence_threshold or 
                           max_amplitude < min_max_amplitude)
        
        return not is_mostly_silent, avg_amplitude, max_amplitude

    def _is_likely_hallucination(self, text, avg_amplitude):
        """Ellenőrzi, hogy a szöveg valószínűleg hallucináció-e"""
        # Gyakori Whisper hallucináció minták
        hallucination_patterns = [
            "köszönöm",
            "thank you",
            "thanks for watching",
            "köszönöm hogy meghallgatta",
            "köszönöm a figyelmet",
            "videóhoz",
            "video",
            "subscribe",
            "feliratkozás",
            "like",
            "tetszik",
            "comment",
            "komment"
        ]
        
        text_lower = text.lower().strip()
        
        # Ha túl rövid és alacsony az amplitúdó
        if len(text_lower) < 50 and avg_amplitude < 800:
            # Ellenőrizzük a hallucináció mintákat
            for pattern in hallucination_patterns:
                if pattern in text_lower:
                    return True
        
        # Ha nagyon rövid szöveg és nagyon alacsony hang
        if len(text_lower) < 20 and avg_amplitude < 300:
            return True
            
        return False

    def _process_audio(self):
        """Feldolgozza a rögzített hangot"""
        # Audio minőség ellenőrzése
        try:
            has_sound, avg_amp, max_amp = self._check_audio_quality(self.frames)
            
            if not has_sound:
                print("❌ Túl halk vagy csendes felvétel. Próbálj hangosabban beszélni!")
                self.logger.warning("Audio túl halk - átlag: %.1f, max: %.1f", avg_amp, max_amp)
                return
                
        except ImportError:
            # Ha nincs numpy, folytatjuk numpy nélkül
            self.logger.warning("NumPy nem elérhető, audio minőség ellenőrzés kihagyva")
            avg_amp = 1000  # Alapértelmezett érték
        except Exception as error:
            self.logger.warning("Audio minőség ellenőrzési hiba: %s", error)
            avg_amp = 1000
        
        # Ideiglenes fájl létrehozása
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
            temp_filename = temp_file.name

            # WAV fájl írása
            with wave.open(temp_filename, 'wb') as wave_file:
                wave_file.setnchannels(self.channels)
                wave_file.setsampwidth(self.audio.get_sample_size(self.format))
                wave_file.setframerate(self.rate)
                wave_file.writeframes(b''.join(self.frames))

        self.logger.info("Ideiglenes WAV fájl létrehozva: %s", temp_filename)

        # Whisper feldolgozás
        try:
            print("🤖 Beszédfelismerés folyamatban...")
            self.logger.info("Whisper feldolgozás elkezdve")

            result = self.model.transcribe(
                temp_filename,
                language="hu",  # Magyar nyelv
                task="transcribe",
                # További paraméterek a hallucináció csökkentésére
                temperature=0.0,  # Determinisztikus eredmény
                no_speech_threshold=0.6,  # Magasabb küszöb a csendes részekhez
                logprob_threshold=-1.0,  # Alacsonyabb valószínűségű szövegek kiszűrése
            )

            transcribed_text = result["text"].strip()
            segments = result.get('segments', [])
            no_speech_prob = result.get('no_speech_prob', 0.0)
            
            self.logger.info("Whisper eredmény: '%s' (szegmensek: %d, no_speech_prob: %.3f)",
                           transcribed_text, len(segments), no_speech_prob)

            # Ellenőrizzük a hallucináció valószínűségét
            if transcribed_text:
                if no_speech_prob > 0.8:
                    print("❌ Nagy valószínűséggel nincs beszéd a felvételben.")
                    self.logger.info("Magas no_speech_prob (%.3f), eredmény elvetve", no_speech_prob)
                elif self._is_likely_hallucination(transcribed_text, avg_amp):
                    print("❌ A felismert szöveg valószínűleg hallucináció (háttérzaj).")
                    self.logger.info("Hallucináció gyanú: '%s'", transcribed_text)
                else:
                    self.save_transcription(transcribed_text)
                    print("✅ Szöveg mentve!")
            else:
                print("❌ Nem sikerült szöveget felismerni.")
                self.logger.warning("Üres szöveg eredmény a Whisper-től")

        except (OSError, RuntimeError, ValueError, whisper.DecodingError) as error:
            print(f"Hiba a beszédfelismerés során: {error}")
            self.logger.error("Whisper feldolgozási hiba: %s", error)
        finally:
            # Ideiglenes fájl törlése
            try:
                os.unlink(temp_filename)
                self.logger.info("Ideiglenes fájl törölve")
            except OSError as error:
                self.logger.warning("Ideiglenes fájl törlési hiba: %s", error)

    def save_transcription(self, text):
        """Elmenti a felismert szöveget időbélyeggel ellátott fájlba"""
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H:%M:%S")
        filename = f"diktatum_{timestamp}.txt"
        filepath = self.output_dir / filename

        try:
            with open(filepath, 'w', encoding='utf-8') as text_file:
                current_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                text_file.write(f"Diktálás időpontja: {current_time}\n")
                text_file.write("-" * 50 + "\n\n")
                text_file.write(text)
                text_file.write("\n")

            print(f"📁 Fájl mentve: {filepath}")
            self.logger.info("Szöveg fájl mentve: %s", filepath)
            self.logger.info("Mentett szöveg: '%s'", text)

        except (OSError, IOError, UnicodeError) as error:
            print(f"Hiba a fájl mentésekor: {error}")
            self.logger.error("Fájl mentési hiba: %s", error)

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

    def _handle_command(self, command):
        """Parancs feldolgozása"""
        if command in ['s', 'space', '']:
            if not self.recording:
                self.start_recording()
            else:
                self.stop_recording()
            return True

        if command in ['q', 'quit', 'exit']:
            if self.recording:
                self.stop_recording()
            print("\n👋 Viszlát!")
            self.logger.info("Felhasználó kilépett")
            return False

        if command == 'help':
            print("\nElérhető parancsok:")
            print("  s, space, ENTER - Felvétel indítása/leállítása")
            print("  q, quit, exit   - Kilépés")
            print("  help           - Súgó megjelenítése")
            self.logger.info("Súgó megjelenítve")
            return True

        self.logger.info("Ismeretlen parancs: '%s'", command)
        return True

    def run(self):
        """Főprogram futtatása"""
        # pylint: disable=too-many-branches,too-many-statements
        # A run metódus természetesen összetett a felhasználói interfész miatt

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
                    self.logger.info("Felhasználói parancs: '%s'", command)
                except EOFError:
                    break

                if not self._handle_command(command):
                    break

                # Raw módba visszaállítás
                tty.setraw(sys.stdin.fileno())

        except KeyboardInterrupt:
            if self.recording:
                self.stop_recording()
            print("\n👋 Program megszakítva.")
            self.logger.info("Program megszakítva (Ctrl+C)")

        finally:
            self.cleanup()


def check_microphone():
    """Ellenőrzi a mikrofon elérhetőségét"""
    try:
        # ALSA hibák elnyomása
        with contextlib.redirect_stderr(open(os.devnull, 'w', encoding='utf-8')):
            audio = pyaudio.PyAudio()
            # Csak ellenőrizzük, hogy el tudjuk érni az audio rendszert
            audio.get_host_api_count()
            audio.terminate()
        return True
    except (OSError, pyaudio.PyAudioError) as error:
        print(f"❌ Mikrofon hiba: {error}")
        print("Ellenőrizd, hogy a mikrofon csatlakoztatva van és használható.")
        return False


def main():
    """Főprogram"""
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
    if not check_microphone():
        return

    dictation = HungarianDictation(
        model_size=args.model,
        output_dir=args.output_dir
    )

    dictation.run()


if __name__ == "__main__":
    main()