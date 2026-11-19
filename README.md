# SharkPet 🦈

A tiny desktop pet: a hammerhead shark that swims around your screen, does tricks,
and cheers you on. Pure Python (tkinter), no extra packages needed.

**Windows only** (the see-through desktop layer uses a Windows feature).

## Run it

Install Python from [python.org](https://www.python.org/downloads/) (tick
"Add python.exe to PATH"), then:

```
py sharkpet.py
```

A moment after launch he says hi. If you don't see him, check
`sharkpet_log.txt` in your user folder.

## Controls

| Do this | To get this |
|---|---|
| Right-click the shark | Menu: rename, cheer me on, tricks, edit messages, quit |
| Double-click the shark | Rename him |
| Click and drag him | Pick him up and carry him (drop him in the tank window!) |
| Click him (no drag) | A puff of bubbles |

Closing the tank window quits the app.

## Tricks

Barrel roll, spin, leap, backflip, bunny hop, zoom, dance, moonwalk, chase tail,
shimmy, and play dead. He does one at random every so often, or pick one from
the right-click menu.

## Your own messages

Right-click, then **Edit messages...** A text file opens with one message per
line. Save it and he'll use yours instead of the built-in ones.

## Build a standalone .exe

```
py -m pip install pyinstaller
py -m PyInstaller --onefile --noconsole --name SharkPet sharkpet.py
```

The app ends up in `dist\SharkPet.exe`. Windows may warn about an unrecognized
app, since it isn't code-signed: choose **More info**, then **Run anyway**.

## Where things are saved

Everything lives in your user folder: his name (`.shark_tank_name.txt`),
your messages (`sharkpet_messages.txt`), and any errors (`sharkpet_log.txt`).
