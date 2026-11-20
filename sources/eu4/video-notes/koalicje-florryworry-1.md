# Koalicje — ocena ryzyka, rozejmy i agresywna ekspansja

Autor filmu: Florryworry. Wersja źródła: sprzed 1.37, dokładna wersja niepotwierdzona. Napisy automatyczne: `en`. Docelowa baza: EU4 1.37, singleplayer, bez modów. [How to deal with coalitions, część 1](https://www.youtube.com/watch?v=awPNaMmM8Sw)

<a id="t108"></a>
## Policz kandydatów do utworzenia koalicji

Florryworry proponuje sprawdzić, ilu niezależnych przeciwników ma jednocześnie co najmniej 50 punktów agresywnej ekspansji, ujemną opinię i brak rozejmu. Czterech takich kandydatów to dla niego sygnał, że układ pokojowy może doprowadzić do koalicji. Poprawa opinii wybranego państwa albo trwający rozejm może zmniejszyć ich liczbę. To praktyczna metoda przesiewowa przed podpisaniem pokoju.

**Zakres i warunki.** Poradnik sprzed 1.37 upraszcza mechanikę. Defines.lua w 1.37.5 potwierdza parametr AE_COALITION_THRESHOLD = −50, ale sam nie rozstrzyga warunków AI, nastawienia i siły. Ryzyko dołączenia do koalicji jest czym innym niż ryzyko, że koalicja wypowie wojnę.

**Punkty odniesienia w plikach EU4 1.37.5.0.**

- `common/defines.lua`, `AE_COALITION_THRESHOLD = -50` — Plik potwierdza parametr AE. Pozostałe warunki decyzji AI nie wynikają z tej stałej.

[1:48–2:45 · Florryworry](https://www.youtube.com/watch?v=awPNaMmM8Sw&t=108s)

<a id="t165"></a>
## Mniejsza nowa agresywna ekspansja i szybszy zanik starej

Przy układaniu pokoju przydają się modyfikatory obniżające agresywną ekspansję nakładaną przez nowe żądania. Gdy wcześniejsze podboje już obciążyły opinię sąsiadów, modyfikator poprawy stosunków przyspiesza zanik kary. Autor wymienia prestiż po obu stronach, a wśród sposobów na szybszy zanik wskazuje doradcę i odpowiednie idee. Porównaj skutek przewidywanego traktatu po zastosowaniu wybranego modyfikatora.

**Zakres i warunki.** Poradnik pochodzi sprzed 1.37. W 1.37.5 common/static_modifiers/00_static_modifiers.txt potwierdza ae_impact i improve_relation_modifier dla prestiżu, a common/opinion_modifiers/00_opinion_modifiers.txt bazowy roczny zanik AE o 2. Wysłanie dyplomaty podnosi opinię wybranego kraju. Modyfikator Improve Relations wspiera także tempo zaniku AE.

[2:45–3:24 · Florryworry](https://www.youtube.com/watch?v=awPNaMmM8Sw&t=165s)

<a id="t204"></a>
## Religia, kultura i Święte Cesarstwo wpływają na rozkład AE

Ten sam pokój może wywołać różne reakcje w państwach wokół podbitych ziem. Na przykładzie podboju katolickiego terytorium Florryworry tłumaczy, dlaczego zaniepokojone są zwłaszcza państwa katolickie, i wskazuje pokrewieństwo kulturowe jako dodatkowy czynnik. W Świętym Cesarstwie kilka takich czynników może działać równocześnie. Porównaj w oknie pokoju konkretne kraje, szczególnie po zmianach wyznaniowych związanych z reformacją.

**Zakres i warunki.** Poradnik jest sprzed 1.37. Defines.lua w 1.37.5 zawiera odrębne wartości dla religii, kultury i HRE. To część formuły, więc sam podział państw na grupy wyznaniowe nie przesądza o wysokości AE.

[3:24–5:27 · Florryworry](https://www.youtube.com/watch?v=awPNaMmM8Sw&t=204s)

<a id="t327"></a>
## Rotacja rozejmów przy podbojach jednego regionu

Przy szybkiej ekspansji Florryworry skupia wojny w jednym obszarze religijnym i planuje różne końce rozejmów. W przykładzie bliskowschodnim może zostawić kilka silnych krajów bez rozejmu, jeśli pozostali są czasowo wyłączeni z tworzenia nowej koalicji. Przed kolejnym pokojem sprawdź, czy wygasający wkrótce rozejm nie przywróci istotnego kandydata w trakcie kolejnej wojny.

**Zakres i warunki.** Przykład sprzed 1.37 zakłada zasoby i czas na regularne wojny. Liczba trojga przeciwników bez rozejmu jest częścią heurystyki dla powstawania nowej koalicji. Ten sposób liczenia nie wyjaśnia deklaracji wojny ani obronnego wezwania członków istniejącej koalicji.

[5:27–7:19 · Florryworry](https://www.youtube.com/watch?v=awPNaMmM8Sw&t=327s)

<a id="t445"></a>
## Jak zmniejszyć ryzyko koalicji przed pokojem z Bengalem

W przykładzie pokoju z Bengalem autor sprawdza ostrzeżenie w oknie pokoju, a Bengal wykreśla ze swojego rachunku, bo traktat ustanowi z nim rozejm. Dla państw blisko progu AE rozważa przesunięcie pokoju do stycznia, żeby roczny zanik obniżył przewidywane wartości. W przypadku państwa, które pozostałoby wyraźnie ponad progiem, proponuje podnieść jego opinię przed zawarciem traktatu. Potem aktualizuje rachunek kandydatów.

**Zakres i warunki.** Pokaz sprzed 1.37. Autor używa trybu debug i integruje jedno z państw, aby szybciej uzyskać sytuację z mniejszą liczbą kandydatów. Integracja nie stanowi testu skutków dyplomatycznej poprawy opinii. Nazwy mniejszych państw i niektóre wartości są uszkodzone przez ASR.

[7:25–10:24 · Florryworry](https://www.youtube.com/watch?v=awPNaMmM8Sw&t=445s)

<a id="t466"></a>
## Długość i wygasanie rozejmu w planie następnej wojny

Koszt warunków pokojowych pomaga zaplanować odstępy między końcami rozejmów. Autor podaje 5 lat przy pokoju za 0% warscore, 10 lat przy 50% i 15 lat przy 100%. Po podpisaniu pokoju sprawdza termin w interfejsie, by wiedzieć, kiedy Bengal znów może zostać kandydatem do koalicji. Przy kilku zbliżających się terminach aktualizuj rachunek i porównuj go z własną gotowością do wojny.

**Zakres i warunki.** Bazowe 5 lat i skalowane do 10 dodatkowych lat potwierdza defines.lua dla 1.37.5. Opis rozbieżności miesiąca rozejmu dotyczy starego pokazu i nie został potwierdzony dla 1.37. Zmiana w patchnotes 1.37 i osobny parametr oczekiwania AI dotyczą deklaracji wojny po rozejmie, a czas dołączenia do koalicji wymaga osobnego sprawdzenia.

**Punkty odniesienia w plikach EU4 1.37.5.0.**

- `common/defines.lua`, `TRUCE_YEARS = 5 / SCALED_TRUCE_YEARS = 10 / MIN_DAYS_AFTER_TRUCE_ENDS` — Podstawowy rozejm trwa pięć lat, a skala dodaje do dziesięciu lat. Minimalny czas oczekiwania AI dotyczy deklaracji wojny po końcu rozejmu.

[7:46–11:37 · Florryworry](https://www.youtube.com/watch?v=awPNaMmM8Sw&t=466s)

<a id="t761"></a>
## Dyplomacja wobec trudno dostępnych kandydatów

Jeśli uzyskanie rozejmu z trudno dostępnym państwem byłoby kosztowne, Florryworry proponuje skupić się na jego opinii. Wymienia wysłanie dyplomaty, prezent i wpływanie na kraj po uzyskaniu statusu wielkiego mocarstwa. Po takich działaniach sprawdź przewidywaną opinię oraz AE przy aktualnych żądaniach pokojowych. To przydatne, gdy wystarczy zmienić pozycję kilku państw granicznych dla wyniku.

**Zakres i warunki.** Porady pochodzą sprzed 1.37. Wpływanie na kraj wymaga dostępu do akcji wielkich mocarstw i spełnienia jej warunków. Common/opinion_modifiers/00_opinion_modifiers.txt ma +25 dla great_power_influence w 1.37.5. Film dotyczy zapobiegania koalicji i odsyła temat istniejącej koalicji do osobnej części.

[12:41–14:26 · Florryworry](https://www.youtube.com/watch?v=awPNaMmM8Sw&t=761s)
