# Dictate

Whisper alapú diktáló és emailküldő CLI alkalmazás

## Telepítés

```bash
git clone https://github.com/kzsfluxus/dictate.git
cd dictate
python3 -m venv .venv
source .venv/bin/activate
pip3 install -r requirements.txt
```
> Megjegyzés: szükséges lehet a portaudio19-dev és python3-dev csomagok telepítése.

Majd másoljuk a `dictate.sh` és a `dictate_browser.sh` fájlokat a PATH-ba. Pl.: $HOME/bin. Ezután a két szkriptben adjuk meg a `dictate` könyvtár abszolút útvonalát.

## Használat

### Dictate

Az app az openai_whisper modeljeire épül: tiny, base, small, medium és large. Minél nagyobb egy modell annál pontosabb, de lassabb a feldolgozás. Alapértelmezésként a base modell van beállítva, ezt a `dictate.sh` fájlban meg lehet változtatni.

Az egyes modellek mérete:

| Modell     | Paraméterek száma | Méret (GB) | Megjegyzés                                |
| ---------- | ----------------- | ---------- | ----------------------------------------- |
| **tiny**   | \~39 M            | \~0.075 GB | Nagyon gyors, de kevésbé pontos           |
| **base**   | \~74 M            | \~0.145 GB | Gyors, de alacsonyabb pontosság           |
| **small**  | \~244 M           | \~0.49 GB  | Jó egyensúly sebesség és pontosság között |
| **medium** | \~769 M           | \~1.55 GB  | Nagyobb pontosság, lassabb feldolgozás    |
| **large**  | \~1550 M          | \~2.9 GB   | Legpontosabb, de a leglassabb             |

A `dictate.sh` szkript indítja az appot.

- `space` vagy `s` (start) + `Enter` indítja a felvételt
- `space` vagy `s` (stop) + ``Enter`` leállítja a felvételt
- `q` (quit) + `Enter` kilépés

A felvételekből készült leiratokat a program a `diktatum` alkönyvtárban - időbélyeggel ellátva - tárolja.

### Leirat böngésző

A böngészőt a `dictate_browser.sh` indítja. Nyilakkal lehet navigálni a leiratok között.

- `Enter`- a leiratot szerkesztésre megnyitja a `vim` szövegszerkesztőben
- `m` (mail) - megnyit egy dialógusablakot, címzett és tárgy mezőkkel, az email törzse automatikusan a választott leirat lesz.
- `q` (quit) - kilépés

Email

- `a` (address_list) - emailcím választása listából
- `r` (recipient) - cím beírása, a levél elküldése után automatikusan bekerül a címlistába
- `t` (tárgy) - az email tárgyának megadása
- `s` (send) - elküldi az emailt
- `Esc` - kilépés

A levelezéshez szükséges adatokat (smtp-szerver, emailcím, application password) az `email_config.json` fájlban kell megadni.
