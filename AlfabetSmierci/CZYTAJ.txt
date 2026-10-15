ALFABET ŚMIERCI - port na PC
============================

Gra: Arte / Seven Stars Multimedia (C) 1995/1996.
Port by Pete Roman, for Seven Stars Multimedia and Maciej 'Maniak' Frontkiewicz, with love.
Wersja portu: 1.0 (2026-10-15).


URUCHOMIENIE

Uruchom AlfabetSmierci.exe (Windows 10/11, 64 bit). Nic nie trzeba instalować ani mieć
uprawnień administratora.

Z GitHuba: przycisk Code, potem Download ZIP. Rozpakuj, wejdź do folderu AlfabetSmierci
i uruchom AlfabetSmierci.exe. Gra jest kompletna, razem z oryginalnymi dyskietkami.

Cały folder można skopiować w dowolne miejsce, także na pendrive. Gra startuje
w pełnym ekranie. F11 albo Alt+Enter przełącza na okno.


CO JEST ORYGINAŁEM, A CO PORTEM

Oryginał, nietknięty:
  - wszystkie dane gry: zdjęcia, palety, muzyka, teksty, dialogi, intro, zakończenie,
  - logika gry: przełożona instrukcja po instrukcji z kodu 68000 na czytelne skrypty
    (data/scripts/*.alf), które działają tak samo jak program na Amidze.

Port:
  - AlfabetSmierci.exe: silnik, który czyta oryginalne dyskietki, wyświetla obraz tak jak
    układy AGA (bitplany, copper, sprite'y, blitter) i gra muzykę jak Amiga 1200
    (emulacja Pauli w libopenmpt, bez nagranego wcześniej dźwięku),
  - panele po bokach ekranu (opcje), ekrany autorów i narzędzi, szybki zapis.

Obraz jest pokazywany w oryginalnych proporcjach, bez rozciągania i bez wygładzania,
tylko z całkowitym powiększeniem pikseli.


SKĄD GRA BIERZE DANE

Z folderu data/ obok exe:
  data/disk1.adf .. disk4.adf   oryginalne dyskietki gry (obrazy ADF, bez zmian)
  data/scripts/                 logika gry przełożona z kodu oryginału

Exe rozpakowuje dane z dyskietek przy każdym uruchomieniu (CrunchMania, jak oryginał).
Zmiany dyskietek działają same: plansza "Włóż dysk" pokazuje się na chwilę,
potem gra jedzie dalej.

Zapisy trafiają do folderu saves/ obok gry:
  saves/stan_gry.adf   dyskietka zapisu z menu gry (3 miejsca, jak w oryginale)
  saves/stan.sav       szybki zapis z panelu po lewej (jedno miejsce)


STEROWANIE

Wszystko da się zrobić samą myszą, lewym przyciskiem:
  lewy przycisk myszy     wybór, przejście, opcja dialogu, dalej (kolejna kwestia)
  prawy przycisk myszy    dalej (tak jak w oryginale na Amidze)
  spacja                  dalej
  FIRE joysticka          w kilku miejscach gra go wymaga; działa lewy przycisk
                          (kliknięcie w puste miejsce obrazka), spacja, środkowy
                          przycisk myszy albo dowolny przycisk pada
  F11 / Alt+Enter         pełny ekran / okno
  Tab                     pokaż / ukryj panele boczne

Kursor gry (rączka) jest jedynym kursorem w oknie, także nad panelami.

Panel z lewej: głośność muzyki, skala (w oknie), pełny ekran, szybki zapis i wczytanie,
autorzy, narzędzia, wyjście.

Po zakończeniu gry, po ostatniej planszy autorów, pojawia się strona portu. Kliknięcie
albo dowolny klawisz wraca potem do ekranu tytułowego.


AUTORZY I LICENCJE

Autorzy gry i portu: przycisk "Autorzy" w panelu. Narzędzia i biblioteki: przycisk
"Narzędzia". Licencje bibliotek, które są w exe: THIRD_PARTY_LICENSES.txt.
