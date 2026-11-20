# Próba lokalnego asystenta w kampanii Polską

Uruchomiono Gemmę 4 E4B z włączonym rozumowaniem przez lokalny backend llama.cpp.
Asystent korzystał z pełnego indeksu instalacji EU4 1.37.5.0, opracowań i wektorów.
Każde pytanie opisuje osobną przykładową sytuację. Poniżej są wszystkie odpowiedzi
i odsyłacze wyświetlone przez asystenta. Zachowano brzmienie, numerację i błędy.

## 1. Jest listopad 1444, gram Polską. Co zrobić na samym początku, zanim zacznę pierwszą wojnę?

~~~~text
Na początku gry, z powodu bezkrólewiu, nie możesz wypowiedzieć wojny, ponieważ rada regencyjna blokuje tę akcję [3]. Musisz poczekać na wybór władcy, a następnie sprawdzić w ekranie dyplomacji, czy ostrzeżenie o radzie regencyjnej zniknęło, aby móc podjąć działania [3].

Źródła
[3] Polska w 1444 i blokada wypowiadania wojny — history/countries/POL - Poland.txt:21
    localisation/text_l_english.yml:1227 · NO_WAR_WHEN_REGENCY
    events/flavorPOL.txt:1783 · flavor_pol.18
~~~~

## 2. Mam wybór między Jagiellonem a miejscowym szlachcicem. Co realnie zyskam, biorąc Jagiellona?

~~~~text
Jagiellon otwiera unię z Litwą, a miejscowy szlachcic daje Polsce własnego władcę bez tej unii. W pierwszej kampanii wybierz Jagiellona, a po szlachcica sięgnij, jeśli z Lions of the North wolisz walczyć o unię z Czechami. [1]

Źródła
[1] Jagiellon czy miejscowy szlachcic — events/flavorPOL.txt:1783
    events/flavorLIT.txt:850 · flavor_lit.16
    missions/SCA_Polish_Missions.txt:1498 · pol_varna_aftermath
~~~~

## 3. Mam już unię z Litwą i sojusz z Brandenburgią. Kiedy uderzyć na Krzyżaków i co wziąć w pierwszym pokoju?

~~~~text
Jeżeli w wydarzeniu wybierzesz Jagiellona, Litwa sterowana przez komputer zgodzi się zostać młodszym partnerem Polski w unii personalnej. Zostań w regencji i wypatruj wyboru Kazimierza przed 1450, gdy niezależną Litwą nadal rządzi Jagiellon. [1]

Źródła
[1] Jak dostać unię personalną z Litwą — events/flavorPOL.txt:1783
    events/flavorLIT.txt:850 · flavor_lit.16
    events/flavorPOL.txt:1884 · flavor_pol.20
~~~~

## 4. Brakuje mi pieniędzy na armię. Czy jako Polska mam wziąć tanie pożyczki od mieszczan, czy odpuścić doradców?

~~~~text
Jeśli masz dostęp do mieszczaństwa, przywilej Zadłużenie u mieszczan daje standardowo pięć pięcioletnich pożyczek na 1%. Otwórz stany i sprawdź dostępność przywileju przed zaciągnięciem droższej pożyczki bankowej. [1]

Źródła
[1] Tanie pożyczki od mieszczaństwa — common/estate_privileges/03_burgher_privileges.txt:479
    common/defines.lua:1170 · BASE_INTERESTS
    common/defines.lua:1228 · BANK_LOAN_DURATION
~~~~

## 5. Zdobyłem Gdańsk, ale główny handel nadal mam w Krakowie. Gdzie wysłać kupca i kiedy warto zmienić główny port?

~~~~text
Polska automatycznie zbiera handel w Krakowie, a Gdańsk daje siłę handlową w węźle Morza Bałtyckiego. Zbieraj w Krakowie i rozważ przeniesienie głównego portu po zdobyciu silnej pozycji na Bałtyku. [1]

Źródła
[1] Handel Polski: Kraków i Bałtyk — history/countries/POL - Poland.txt:8
    common/tradenodes/00_tradenodes.txt:1652 · krakow
    common/tradenodes/00_tradenodes.txt:1751 · baltic_sea
    history/provinces/43 - Danzig.txt:26 · center_of_trade = 2
    localisation/loadingtips_l_english.yml:24 · LOADING_TIP_22
~~~~

## 6. Mazowsze już wcielone, Litwa dalej w unii. Co sprawdzić, zanim kliknę utworzenie Rzeczypospolitej?

~~~~text
Polska jako senior Litwy może ją odziedziczyć przy tworzeniu Rzeczypospolitej, zwykle od technologii administracyjnej 10 i z rdzeniami na Krakowie, Warszawie, Gdańsku i Malborku. Sprawdź podpowiedź decyzji, w tym pokój, stabilność, nieistnienie Mazowsza oraz rozmiar i chęć wolności Litwy. [1]

Źródła
[1] Jak utworzyć Rzeczpospolitą przez unię z Litwą — decisions/TheCommonwealth.txt:3
    events/flavorPOL.txt:2774 · flavor_pol.32
~~~~

## Obserwacje

- Przy pytaniu o przygotowania Polska dostała informację o blokadzie wojny.
  Odpowiedź nie zaproponowała, jak wykorzystać czas w bezkrólewiu.
- Przy pytaniu o Krzyżaków asystent wrócił do wyboru Jagiellona, mimo że unia była już w pytaniu.
- Przy pytaniu o budżet opisał pożyczki mieszczan. Pominął porównanie z kosztami doradców.
- Przy pytaniu o handel wskazał warunek rozważenia zmiany głównego portu, ale pominął miejsce wysłania kupca.

[Jak uruchomić asystenta i zbudować bazę](eu4-workflow.md)
