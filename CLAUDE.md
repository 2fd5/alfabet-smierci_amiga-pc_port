# CLAUDE.md: stałe zasady projektu

Czytaj to na starcie każdej sesji. Potem `CLAUDE.local.md` (lokalne zasady, jeśli jest) i `PROGRESS.md` (gdzie jesteśmy, następny krok, komendy).

## Cel i kontekst

- Port **Alfabet Śmierci** (1996, Arte / Seven Stars Multimedia, Amiga AGA, polska przygodówka point-and-click) na PC, w stylu ScummVM: własny silnik, który ładuje **oryginalne dane** z dyskietek ADF. Nie dosłowna transpilacja 68k.
- Prywatny projekt Pete'a (Piotr 'Pete' Romańczyk). Pierwszym czytelnikiem repo będzie Maciej 'Maniak' Frontkiewicz (autor gry), więc kod ma być czysty, czytelny, udokumentowany, a dane oryginału oddzielone od kodu silnika. IP nie jest problemem.
- Cele: zero strat jakości (grafika, palety, muzyka), przenośny folder z jednym exe, bez instalatora i bez admina. **Muzyka ma najwyższy priorytet**: wierna emulacja Pauli (libopenmpt, tryb A1200), nigdy wcześniej wyrenderowany stratny dźwięk.
- Komunikacja z Pete'em **po polsku**, raporty krótkie, w głosie założyciela. **Nigdy nie używaj długich myślników (em-dash)**, także w kodzie, docs i commitach. Zamiast tego przecinek, dwukropek, kropka albo zwykły myślnik.

## Decyzje Pete'a: nie zmieniać bez pytania

- **Stack**: C11 + SDL3 (statycznie) + libopenmpt (statycznie), w64devkit GCC + CMake, wszystko portable w `tools/toolchain` i `deps`. Uzasadnienie: STACK.md.
- **Skalowanie**: tylko całkowite, nearest neighbour, bez filtrów, bez rozciągania na szerokość.
- **Proporcje pikseli**: obraz oryginału nierozciągnięty. Hires 640x256 pokazywany jako 640x512 (podwajanie linii), czyli piksel hires 1:2. Lores podwajany w poziomie.
- **Panele boczne** (widescreen): lewy = opcje (głośność, skala, pełny ekran/okno, zapis/odczyt, credits, narzędzia, wyjście) w stylu z assetów gry; prawy = spokojny kamień. **Bez toporności, bez pionowych napisów ALFABET/ŚMIERCI** (wariant 1b).
- **Credits: dwa osobne ekrany**. Ekran 1 (oryginał): wszystkie oryginalne credits po polsku, jedna linijka portu po angielsku: "Port by Pete Roman, for Seven Stars Multimedia and Maciej 'Maniak' Frontkiewicz, with love", ostatnia karta "Piotr 'Pete' Romańczyk / Autor portu z systemów Amiga na PC" z osobistymi podziękowaniami dla twórców. Bez linii o Seven Stars i "mrocznym dzieciństwie" (usunięte na prośbę Pete'a). Ekran 2 (narzędzia): każde narzędzie i biblioteka z autorami i licencją, w tym **Claude Opus 5.5 i Claude Code (Anthropic)**, na końcu: "Dostęp do narzędzi możliwy dzięki współpracy z ReadyM (ReadyCode Limited)."
- **CREDITS.md** aktualizować przy każdym nowym narzędziu. **THIRD_PARTY_LICENSES.txt** jest w paczce (generuje `tools/make_licenses.py`).
- **Build one-click, przenośny**: `AlfabetSmierci/` w repo (commitowany, gotowy do gry z GitHuba: Download ZIP i uruchom) z jednym exe, `data/` (oryginalne dyskietki i skrypty), `CZYTAJ.txt`, licencjami; zip przez `tools/make_zip.py` (ścieżki z `/`).
- **Ekrany zmiany dyskietek zostają**: pokazują się ~2 s, potem dyskietka "wchodzi" sama.
- **Zakończenie**: oryginalny ekran końcowy zostaje, ale zamiast wiecznego `halt` po kliknięciu albo naciśnięciu klawisza gra wraca do ekranu tytułowego (decyzja 2026-10-14).
- **Rozmiar exe** (~8.9 MB, statyczne SDL3 + libopenmpt): zostaje, nie optymalizować rozmiaru.
- **Sterowanie (2026-10-15)**: lewy przycisk myszy przewija kwestie i potwierdza wszystko w całej grze; funkcje oryginału (prawy przycisk) zostają i są też pod spacją. FIRE: spacja, środkowy przycisk, pad, a lewy klik tam, gdzie nie koliduje (puste miejsce obrazka w loc_2D/34/35).
- **Kursor (2026-10-15)**: rączka gry jest jedynym kursorem w całym oknie i w pełnym ekranie, także nad panelami; kursor Windowsa ukryty; widoczna wszędzie, gdzie gracz może kliknąć; bez śladu na krawędzi.
- **Linia portu (2026-10-15)**: "Port by Pete Roman, for Seven Stars Multimedia and Maciej 'Maniak' Frontkiewicz, with love" jest na ekranie tytułowym, na ostatniej stronie "Autorzy" (z kartą autora portu) i na stronie po napisach końcowych gry.
- **Szybki zapis z panelu**: jeden slot (`saves/stan.sav`) wystarczy. Menu gry ma swoje 3 sloty na `stan_gry.adf`.
- **WinUAE** tylko do porównań z oryginałem: portable w `tools/winuae`, z wbudowanym **AROS**. **Nie pobierać ROM-ów Kickstart**. Jeśli Kickstart będzie potrzebny, Pete dostarczy 3.1 sam.
- **Oryginały nietknięte**: `orig/zips` (lokalnie, gitignore) tylko do odczytu. Dyskietki gry są w repo w `AlfabetSmierci/data/disk1..4.adf` (decyzja Pete'a 2026-10-15: gra jest abandonware, dyskietki w repo i w paczce), identyczne z kopiami z zipów; narzędzia czytają je stamtąd. Analizy na kopiach w `work/`.
- **Git: commit per kamień milowy.** Publiczne repo: github.com/pete-roman/alfabet-smierci_amiga-pc_port (od 2026-10-15, czysta historia od wersji 1.0). Push wyłącznie na wyraźne polecenie Pete'a.
- **Małe instalacje pip OK. Przed czymkolwiek ciężkim (Java, Ghidra, emulatory, SDK) wylistuj i zapytaj.**

## Mapa plików

| plik / katalog | co tam jest |
|---|---|
| `PROGRESS.md` | stan, tabela lokacji, bugi, pytania, **komendy build/run/test/package** |
| `RECON.md` | faza 1: format dysków, loader, CrunchMania, mapa pamięci, skąd co się bierze |
| `STACK.md` | wybór stacku i dlaczego |
| `ENGINE.md` | jak działa oryginał i jak działa port (VM, natywne procedury, timing, copper, intro, weryfikacja) |
| `scripts/README.md` | język `.alf` (logika gry zliftowana z asm) |
| `CREDITS.md` | credits oryginału, linia portu, narzędzia z licencjami |
| `src/` | silnik C: `amiga.c` (pamięć, hardware, blitter), `disk.c` (ADF, CrunchMania, ładowanie), `video.c` (copper, bitplany, sprite'y), `script.c` (lexer, parser, VM), `natives.c` (procedury przepisane natywnie), `audio.c` (P60A -> MOD, libopenmpt), `panels.c` (panele, credits, opcje), `main.c` (okno, wątki, autoplay) |
| `scripts/*.alf` | **generowane** przez `tools/lifter.py` (common, loc_XX, intro, symbols). Nie edytować ręcznie bez poprawki w lifterze, bo regeneracja nadpisze |
| `tools/symbols.py` | nazwy adresów: zmienne, procedury, listy NATIVE / INTRO_NATIVE |
| `tools/lifter.py` | asm 68k -> `.alf` (CFG, strukturyzacja if/else) |
| `tools/test_locations.py` | smoke test lokacji |
| `tools/playthrough.py`, `tests/walkthrough.json`, `docs/WALKTHROUGH.md` | pełne przejście gry automatem, solucja (wyprowadzona ze skryptów) i jej opis |
| `tools/*.py` reszta | crunchmania, dis68k, planar, plchars, p60a, extract, make_zip, make_licenses |
| `tools/winuae/alfabet.uae`, `run_original.bat`, `tools/uae*.ps1`, `tools/winshot.ps1` | oryginał w WinUAE i sterowanie nim |
| `AlfabetSmierci/` | gotowa do gry wersja: exe, `data/disk1..4.adf` (oryginalne dyskietki), `data/scripts/` (kopia `scripts/`), CZYTAJ, licencje; buduje `build.sh` |
| `README.md` | strona repo (GitHub): jak zagrać, co jest w środku, budowanie |
| `src/version.h` | numer wersji portu (zip: `work/AlfabetSmierci-<wersja>.zip`) |
| `orig/` | oryginalne zipy (lokalnie, gitignore, nietykalne) |
| `work/` | binarki rozpakowane, testy, zipy buildów (gitignore) |
| `extracted/`, `deps/`, `build/`, `tools/toolchain/` | generowane (gitignore); `AlfabetSmierci/saves/` też |

## Pułapki techniczne (nauczone na błędach)

- **CrunchMania** (`CrM!`) wszędzie: intro z dysku 1 sektor 22, gra główna sektor 450 (oba ładowane pod `$3000`), dyski 2-4 to bloby plików CrM od bajtu `$1600`. Dekruncher: `tools/crunchmania.py`, `crunchmania_decrunch` w `disk.c`.
- **Polskie znaki** w kodowaniu gry: ą=E6 ć=E7 ę=EA ł=EE ń=F1 ó=F3 ś=F5 ź=FB ż=FE, wielkie = mała - $20 (Ł=CE, Ś=D5, Ż=DE). To nie Latin-2. Konwersja: `tools/plchars.py`.
- **Tabele hotspotów** kończą się markerem **`$BACA`**. x w pikselach hires, y w półliniach (linia ekranu = y/2).
- **Palety**: 59 palet po 128 kolorów 0RGB pod `$59AFA`. Kolory 0-127 = scena, 128-255 = UI. Kolory AGA 24-bit: copper pisze hi i lo (LOCT) słowa. Kolor 255 = kolor tekstu, ustawiany WAIT-em coppera w linii `$F5`.
- **Ekran**: 8 bitplanów hires 640x256, 80 bajtów na wiersz (FMODE 3, modulo -8). Piksel hires ma proporcję 1:2 (dlatego 640x512).
- **Mysz**: x w pikselach hires, y w półliniach; HSTART sprite'a = x/2+$80, VSTART = y/2+$2C.
- **Timing**: PAL 50 Hz, 312 linii. VM ma budżet `INSNS_PER_FRAME` = 50000 instrukcji na klatkę i model plamki (beam): `wait_raster $n` czeka na najbliższą linię o młodszym bajcie n, nie na całą klatkę. Pętle busy-wait bez budżetu zawieszały grę. Fade w grze: in 9 kroków/klatkę, out 8 (zmierzone w WinUAE).
- **Muzyka**: The Player 6.0A (P60A), konwertowana symbolicznie do ProTracker M.K. (sample delta: out[j]=out[j-1]-raw[j]); bajt restartu = 0, inaczej OpenMPT wykrywa Scream Trackera i gra źle. libopenmpt z `render.resampler.emulate_amiga=1`, typ `a1200`.
- **Blitter**: gra pisze rejestry blittera bezpośrednio, emulacja w `amiga.c` startuje przy zapisie do `$DFF059` (BLTSIZE).
- **Lifter**: flagi CCR dziedziczone przez fallthrough, `lea d16(An)` (był bug: `a0 = 0`), `movem` = push/pop, osierocone etykiety = procedury `part_`. Po zmianie liftera zawsze regeneruj i przetestuj `loc_04`, `loc_05` i intro.
- **Mowa postaci w oryginale**: `$1C960`/`$16956`/`$1C90A` czekają tylko na PRAWY przycisk (POTGOR bit 10), `$1C960` chowa kursor (copper SPR0PT = `$1CC16`). Sprawdzone w WinUAE. Port (decyzja Pete'a 2026-10-15): przewija też lewy przycisk i spacja/FIRE, a w czasie czekania pokazuje rączkę jako własny kursor (stan gry bez zmian).
- **Kursor**: sprite'y gry nie są rysowane do obrazu, tylko do osobnej warstwy, z której `main.c` buduje sprzętowy kursor okna w aktualnej skali (jedyny kursor, także nad panelami). Gdy gra ma kursor wyłączony, a gracz może kliknąć, pokazuje się rączka z danych gry (`video_hand_image`).
- **Font gry**: `ż` (`$FE`) to "z" z poprzeczną kreską, nie z kropką. Wygląda jak "z", ale tak jest w oryginale (ekran z dialogiem w pociągu identyczny bajt w bajt z WinUAE).
- **WinUAE**: kliknięcia (`JOY1_FIRE_BUTTON` = lewy przycisk) w trakcie plansz z logo i tytułu zawieszają oryginał pod AROS; `tools/uae_ref.py boot` klika tylko na stronach fabuły. Hover przed kliknięciem (point, 1-1.5 s, click) jest pewniejszy niż sam klik.
- **FIRE joysticka**: oryginał w 3 miejscach (loc_2D, loc_34, loc_35) czyta przycisk fire joysticka w porcie 2 (`$BFE001` bit 7). W porcie: spacja, środkowy przycisk myszy, dowolny przycisk pada, a w loc_2D/34/35 także lewy klik w puste miejsce obrazka (`natives_lmb_is_fire`; nie w loc_13, gdzie FIRE szkodzi).
- **hover_mode**: niektóre pokoje uzbrajają hotspoty (`hover_mode` = 1) tylko gdy kursor jest poza hotspotami i nie wybrano czasownika. Automat musi odsunąć kursor przed wyborem czasownika (gracz robi to odruchowo).
- **Automat gry** (`tools/playthrough.py`): "gra czeka na gracza" = gra odpytuje wejście (`lmbpoll` <= 2, liczone w odczytach lmb i w `hit_test`/`hit_test_ui`), "czeka na prawy klik" = `rwait`. Same flagi tabeli dialogu nie wystarczą, bo zostają ustawione podczas fade.
- **Ekrany śmierci** (`loc_XX_2`/`_3`) są wołane przez `call` z `game_over`; w teście warp "game thread ended" jest oczekiwane.
- **Narzędzia w tym środowisku**: heredoc w Bash z backslashami psuje `\n`, do plików z kodem używaj Write/Edit. Repo ma `eol=lf`. Exe jest zablokowany, gdy testy go używają (link się wtedy nie uda). Nazwy z nawiasami w PowerShell: `-LiteralPath`. WinUAE IPC: `"CFG klucz wartość"` (spacja, nie `=`), ASCII. Zrzuty WinUAE przez `PrintWindow` (`tools/winshot.ps1`), nie przez foreground. `Compress-Archive` robi ścieżki z backslashami, nie używać (jest `tools/make_zip.py`). `sleep` w Bash jest zablokowany, długie rzeczy uruchamiaj w tle.

## Oszczędzanie kontekstu

- Długie outputy (logi, testy, disasm) zawsze do pliku w `work/`, potem `grep` albo czytanie fragmentami.
- **Nie wczytuj całych listingów asm ani całych `scripts/*.alf`** (common.alf ma ~7000 linii). Szukaj po adresie albo nazwie.
- Ciężkie czytanie (solucja ze skryptów, analiza lokacji, lifting nowych kawałków) zlecaj subagentom, odbieraj tylko wnioski.
- Po każdej skończonej lokacji lub kamieniu milowym: zaktualizuj `PROGRESS.md` i zrób commit.
- Raporty do Pete'a krótkie, po polsku, bez em-dashy.
