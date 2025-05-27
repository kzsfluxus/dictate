# Dictate

Whisper alapú diktáló és emailküldő CLI alkalmazás

## Telepítés

```bash
git clone https://github.com/kzsfluxus/dictate
cd dictate
python3 -m venv .venv
source .venv/bin/activate
pip3 install -r requirements.txt
```
> Megjegyzés: szükséges lehet a portaudio19-dev és python3-dev csomagok telepítése.

Majd másoljuk a `dictate.sh` és a `dictate_browser.sh` fájlokat a PATH-ba. Pl.: $HOME/bin. Ezután a két szkriptben adjuk meg a `dictate` könyvtár abszolút útvonalát.

## Használat

### Dictate

Az app az openai_whisper modeljére épül: tiny, base, small, medium és large. Minél nagyobb egy modell annál pontosabb, de lassabb a feldolgozás. Alapértelmezésként a base modell van beállítva, ezt a `dictate.sh` fájlban meg lehet változtatni.

A `dictate.sh` szkript indítja az appot.

- `space` vagy `s` (start) + `Enter` indítja a felvételt
- `space` vagy `s` (stop) + ``Enter`` leállítja a felvételt
- `q` (quit) + `Enter` kilépés

A felvételekből készült leiratokat a program a `diktatum` alkönyvtárban - időbélyeggel ellátva - tárolja.

### Leirat böngésző

A böngészőt a `dictate_browser.sh` indítja. Nyilakkal lehet navigálni a leiratok között.

- `Enter`- a leiratot szerkesztésre megnyitja a `vim` szövegszerkesztőben
- `m` (mail) - megnyit egy dialógusablakot, címzett és tárgy mezőkkel, az email törzse automatikusan a választott leirat lesz.
- `s` (send) - elküldi az emailt
- `q` (quit) - kilépés

A levelezéshez szükséges adatokat (smtp-szerver, emailcím, application password) az `email_config.json` fájlban kell megadni.
