# Varnez – opis projektu i kierunek dalszego rozwoju

## 1. Cel projektu

Varnez to inteligentny asystent gracza Europa Universalis IV, który zna aktualny stan państwa, pamięta przebieg kampanii i rozumie mechaniki gry. Korzysta z rzeczywistych danych rozgrywki, a nie wyłącznie z ogólnej wiedzy o grze.

Główną przewagą projektu jest znajomość konkretnej kampanii oraz jej historii. Asystent powinien odpowiadać zarówno na pytania dotyczące aktualnej sytuacji państwa, jak i wyjaśniać zmiany zachodzące na przestrzeni rozgrywki.

Varnez doradza, analizuje i wyjaśnia. Ostateczne decyzje zawsze podejmuje gracz.

Monitorowanie rozgrywki i gromadzenie danych odbywa się niezależnie od aktywności asystenta.

## 2. Aktualny stan projektu

| Obszar | Obecne możliwości |
|---|---|
| Rozpoznawanie stanu rozgrywki | Państwo gracza, data, dyplomacja, armie i floty, prowincje, poddani, sojusznicy, wydarzenia i wybrane parametry gospodarcze. |
| Analiza strategiczna | Raporty dotyczące sytuacji państwa oraz wskazywanie obszarów wymagających uwagi. |
| Analiza mapy | Rozmieszczenie armii, przynależność prowincji, sąsiedztwo i okupacje. |
| Analiza zapisów | Odczytywanie wcześniejszych zapisów oraz porównywanie ich ze sobą. |
| Wiedza o mechanikach | Zasady rozgrywki, wydarzenia, misje, decyzje i warunki ich wystąpienia. |
| Obserwacja ekranu | Dostęp do aktualnego obrazu gry i możliwość interpretowania widocznych elementów. |
| Interakcja z grą | Otwieranie zakładek oraz wskazywanie elementów interfejsu. |

Obecnie informacje o rozgrywce pobierane są przede wszystkim na żądanie asystenta. Projekt nie posiada jeszcze trwałej, automatycznie aktualizowanej historii kampanii.

## 3. Źródła danych

Podstawowym źródłem informacji jest pamięć działającej gry, do której dostęp zapewnia Tongs.

Projekt zakłada wykorzystanie jednej, ustalonej wersji EU4, co ogranicza problemy wynikające ze zmian wewnętrznych struktur gry.

| Źródło | Przeznaczenie |
|---|---|
| Pamięć gry | Podstawowe źródło aktualnych danych rozgrywki. |
| Zapisy gry | Uzupełniające źródło informacji i możliwość analizy wcześniejszych stanów kampanii. |
| Interfejs gry | Odczyt informacji niedostępnych bezpośrednio przez pozostałe mechanizmy. |
| Obraz gry | Interpretowanie sytuacji widocznej na ekranie gracza. |
| Pliki gry | Wiedza o mechanikach, zasadach, wydarzeniach i decyzjach. |

Asystent powinien rozróżniać źródła informacji, uwzględniać ich aktualność oraz ograniczenia dokładności.

### 3.1. Ograniczenia dostępu do danych

Projekt wykorzystuje przede wszystkim istniejące możliwości Tongsa. Jego rozszerzanie nie jest domyślnym założeniem.

Brakujące dane traktujemy jako ograniczenie systemu, a nie automatycznie jako zadanie programistyczne.

Wszystkie zidentyfikowane ograniczenia powinny być przechowywane w osobnym, aktualizowanym dokumencie w repozytorium.

Dokument powinien zawierać:

- Nazwę i kategorię niedostępnego parametru.
- Przyczynę jego niedostępności.
- Informację o możliwych alternatywnych źródłach.
- Ograniczenia dokładności dostępnych informacji.
- Wpływ braku danych na funkcjonalność asystenta.
- Status dostępności parametru.

Rozszerzenie Tongsa będzie rozważane wyłącznie wtedy, gdy brak określonych danych uniemożliwia realizację istotnej funkcjonalności projektu.

Rejestr ograniczeń stanowi dokumentację stanu wiedzy o dostępności danych, a nie listę obowiązkowych zadań programistycznych.

## 4. Zakres danych rozgrywki

Zakres informacji obejmuje przede wszystkim państwo gracza oraz wybrane informacje dotyczące innych państw istotnych dla jego sytuacji strategicznej.

### Państwo gracza

- Gospodarka i finanse: skarbiec, dochody, wydatki, pożyczki i inflacja.
- Handel: węzły handlowe, kupcy i udział w handlu.
- Technologie i idee.
- Potencjał militarny: armie, floty, rezerwy ludzkie, morale i profesjonalizm.
- Prowincje, ich rozwój, własność i budynki.
- Dyplomacja, sojusze, rywale i poddani.
- Stabilność, legitymizacja i agresywna ekspansja.
- Wojny, wydarzenia i inne istotne zmiany.

### Pozostałe państwa

Skrócony zakres informacji dotyczących sąsiadów, rywali oraz wielkich mocarstw:

- Potencjał militarny.
- Rozwój państwa.
- Poziom technologiczny.
- Sojusze.
- Relacje z państwem gracza.
- Potencjalne zagrożenia.

Zakres ten określa docelowe potrzeby informacyjne projektu. Nie oznacza, że wszystkie wymienione parametry są obecnie dostępne.

## 5. Automatyczne monitorowanie rozgrywki

Monitoring działa niezależnie od asystenta i jest oparty na zdarzeniach oraz określonych momentach upływu czasu w grze.

Nie wszystkie informacje wymagają jednakowej częstotliwości sprawdzania. Powinna ona wynikać z mechanik EU4, charakterystyki danego parametru oraz jego znaczenia dla analizy rozgrywki.

| Rodzaj monitorowania | Przeznaczenie |
|---|---|
| Zdarzeniowe | Rejestrowanie istotnych zdarzeń w momencie ich wykrycia. |
| Dzienne | Parametry wymagające częstego sprawdzania lub agregowania. |
| Tygodniowe | Parametry, których codzienne sprawdzanie nie przynosi istotnej wartości. |
| Miesięczne | Parametry związane z miesięcznym cyklem mechanik gry. |
| Na żądanie | Informacje niewymagające ciągłego monitorowania. |
| Jednorazowe | Informacje niezmienne podczas kampanii. |

Każdy monitorowany parametr powinien posiadać z góry określoną częstotliwość odczytu oraz zdarzenie inicjujące jego synchronizację.

Przypisanie konkretnych parametrów do poszczególnych kategorii powinno uwzględniać rzeczywiste mechaniki gry i dostępne możliwości pozyskiwania danych.

## 6. Pamięć kampanii

Historia kampanii przechowywana jest w zewnętrznej bazie danych, niezależnej od asystenta.

System zapisuje wyłącznie zmienione wartości. Jeżeli podczas kolejnego odczytu parametr nie uległ zmianie, nie powstaje nowy rekord.

Każda zarejestrowana zmiana zawiera pełną nową wartość parametru oraz datę jej zaobserwowania w świecie gry.

Przykładowa historia skarbca:

| Data w grze | Wartość skarbca |
|---|---:|
| 1500.01.01 | 250 |
| 1500.01.07 | 275 |
| 1500.01.15 | 225 |
| 1500.02.01 | 240 |

Takie podejście umożliwia analizowanie historycznych wartości bez konieczności przechowywania kolejnych pełnych kopii stanu państwa.

System powinien rozróżniać dokładną datę zdarzenia, jeżeli jest dostępna, od daty wykrycia zmiany.

## 7. Ciągłość historii kampanii

Historia powinna poprawnie uwzględniać sytuacje występujące podczas rozgrywki, które mogą wpływać na jej ciągłość.

| Sytuacja | Zasada |
|---|---|
| Wczytanie wcześniejszego zapisu | Utworzenie alternatywnej gałęzi historii. |
| Zmiana państwa lub jego identyfikatora | Zachowanie ciągłości historii tej samej kampanii. |
| Rozpoczęcie nowej kampanii | Utworzenie niezależnej historii. |
| Zmiana wersji gry lub zestawu dodatków | Zachowanie informacji o środowisku rozgrywki. |
| Przerwa w monitorowaniu | Oznaczenie okresu, dla którego brakuje danych. |

Każda kampania powinna posiadać własny identyfikator, niezależny od nazwy kontrolowanego państwa.

Asystent powinien domyślnie analizować aktywną gałąź historii, bez mieszania jej z alternatywnymi przebiegami rozgrywki.

## 8. Przechowywanie historii

Każda kategoria monitorowanych danych powinna mieć z góry ustalone, stałe zasady przechowywania historii.

Nie stosujemy jednej ogólnej polityki retencji dla wszystkich danych ani mechanizmu dynamicznie zmieniającego zasady przechowywania.

Dla każdego parametru określamy:

- Częstotliwość zapisywania zmian.
- Wymaganą szczegółowość historii.
- Okres przechowywania.
- Ewentualny sposób agregowania wartości.

Kluczowe parametry, takie jak skarbiec, mogą być przechowywane przez całą kampanię z pełną dostępną szczegółowością.

Dane o dużej częstotliwości zmian, takie jak pozycje jednostek, mogą mieć z góry ustalony krótszy okres przechowywania.

Istotne wydarzenia zachowujemy przez całą kampanię.

Szczegółowość danych przekazywanych asystentowi jest niezależna od szczegółowości danych przechowywanych w bazie. Asystent może otrzymywać podsumowania lub szczegółowe wartości, zależnie od rodzaju wykonywanej analizy.

## 9. Rejestr istotnych wydarzeń

Oprócz historii wartości poszczególnych parametrów system przechowuje historię istotnych wydarzeń.

Wydarzenia powinny być wykrywane na podstawie dostępnych informacji i jawnych reguł, niezależnie od modelu językowego.

| Kategoria | Przykładowe wydarzenia |
|---|---|
| Wojna | Rozpoczęcie wojny, zawarcie pokoju. |
| Terytorium | Zdobycie lub utrata prowincji. |
| Dyplomacja | Zawarcie lub zerwanie sojuszu, zmiana rywala, powstanie koalicji. |
| Finanse | Zaciągnięcie pożyczki, bankructwo. |
| Państwo | Zmiana władcy, religii, rządu lub identyfikatora państwa. |
| Zagrożenia | Przekroczenie istotnych progów parametrów. |
| Rozgrywka | Wczytanie starszego zapisu, powstanie alternatywnej historii. |

System powinien rozróżniać zdarzenia bezpośrednio potwierdzone przez grę od zdarzeń wywnioskowanych na podstawie zmian parametrów.

## 10. Dostęp asystenta do informacji

Asystent posiada dwie niezależne ścieżki dostępu do danych.

### Dostęp do historii kampanii

Umożliwia pobieranie informacji zgromadzonych podczas monitorowania rozgrywki, w tym:

- Ostatniego zarejestrowanego stanu państwa.
- Historycznych wartości parametrów.
- Zmian zachodzących w określonym okresie.
- Rejestru istotnych wydarzeń.
- Porównań i podsumowań.

### Dostęp bezpośredni do rozgrywki

Umożliwia pobieranie aktualnych informacji bezpośrednio z gry, w szczególności danych, które nie są objęte ciągłym monitoringiem.

Asystent nie otrzymuje automatycznie całej zawartości bazy. Samodzielnie wybiera informacje potrzebne do przeprowadzenia konkretnej analizy.

## 11. Analiza długoterminowa

Obliczenia matematyczne, statystyki, porównania i wykrywanie zmian realizowane są niezależnie od modelu językowego.

Asystent interpretuje przygotowane wyniki, uwzględnia mechaniki gry oraz przedstawia rekomendacje.

| Obszar | Zakres analizy |
|---|---|
| Gospodarka | Zmiany dochodów, wydatków, skarbca i zadłużenia. |
| Rozwój państwa | Przyrost terytorium, rozwoju i poziomu technologicznego. |
| Wojsko | Zmiany potencjału militarnego i gotowości do prowadzenia wojen. |
| Wojny | Porównanie sytuacji państwa przed wojną i po jej zakończeniu. |
| Inwestycje | Ocena kosztów i możliwych korzyści. |
| Decyzje gracza | Analiza zmian następujących po podjęciu istotnych decyzji. |
| Zagrożenia | Rozwój sąsiadów, rywali, koalicji i innych potencjalnych przeciwników. |

Asystent powinien odróżniać fakty, zależności statystyczne oraz przypuszczalne związki przyczynowe.

Po powrocie gracza do rozmowy asystent może przedstawić podsumowanie zmian, które nastąpiły od ostatniej interakcji.

## 12. Ograniczenia i wiarygodność informacji

System powinien uwzględniać:

- Ograniczoną dostępność parametrów przez Tongs.
- Różną częstotliwość aktualizacji poszczególnych danych.
- Możliwe przerwy w monitorowaniu.
- Niedokładność wartości odczytywanych z interfejsu.
- Różnice pomiędzy aktualnym stanem gry a wcześniejszymi zapisami.
- Alternatywne przebiegi kampanii.
- Ograniczenia wynikające z wersji gry i aktywnych dodatków.

Asystent powinien informować gracza o braku danych, ich nieaktualności lub ograniczonej dokładności, zamiast uzupełniać brakujące informacje przypuszczeniami przedstawianymi jako fakty.

## 13. Docelowa wizja projektu

Varnez ma być osobistym doradcą strategicznym, który:

- Zna aktualną sytuację państwa.
- Pamięta przebieg kampanii.
- Rozumie mechaniki gry.
- Analizuje historię i trendy.
- Rozpoznaje narastające zagrożenia.
- Pomaga oceniać konsekwencje decyzji.
- Samodzielnie pozyskuje dodatkowe informacje potrzebne do analizy.

Jego największą przewagą jest połączenie wiedzy o grze, aktualnych danych rozgrywki oraz trwałej pamięci konkretnej kampanii.

Varnez nie zastępuje gracza. Dostarcza mu informacji i rekomendacji pozwalających podejmować bardziej świadome decyzje.
