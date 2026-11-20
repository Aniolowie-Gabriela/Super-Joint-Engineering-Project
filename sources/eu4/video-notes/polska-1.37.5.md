# Polska — otwarcie, Litwa, Prusy i Rzeczpospolita

Opracowanie na podstawie wydarzeń, misji i decyzji w plikach gry EU4 1.37.5.0. Wskazówki strategiczne wynikają z warunków zapisanych w skryptach. Warianty zależne od zestawu DLC są opisane przy odpowiednich notatkach.

<a id="1444-11-11"></a>
## Polska 1444: kiedy wybór Jagiellona ustanawia unię z Litwą

Polska zaczyna 11 listopada 1444 w bezkrólewiu i jest już seniorem wobec wasalnego Mazowsza, a poprzednia unia z Litwą jest zakończona. Wydarzenie wyboru Kazimierza może zajść przed 1450, gdy Polska jest niezależna, ma regencję i nie ma reformy Cesarstwa Chińskiego, a niezależną Litwą rządzi Jagiellon. Wybór Jagiellona przekazuje decyzję Litwie, a jej zgoda ustanawia Polskę seniorem unii i uruchamia zmianę polskiej reformy na monarchię elekcyjną. Skrypt Litwy sterowanej przez AI waży zgodę jako 1, odmowę jako 0. Jeśli celem jest najprostsza droga do Rzeczypospolitej, wybór Jagiellona zapewnia zwykle najłatwiejsze spełnienie warunku unii, a do wykonania pozostawia m.in. integrację Mazowsza i przejęcie Gdańska i Malborka.

**Zakres i warunki.** Unia działa bez Lions of the North. Wydarzenie ma losowy moment i przyspiesza od 1447. Zmiana dynastyczna lub utrata niezależności Litwy mogą zablokować wydarzenie, a człowiek grający Litwą może wybrać odmowę.

**Punkty odniesienia w plikach EU4 1.37.5.0.**

- `history/countries/POL - Poland.txt`, `1444.11.11` — Polska ma regenta o zerowych statystykach w dacie startowej.
- `history/diplomacy/Baltic_alliances.txt`, `first = POL / second = MAZ oraz end_date = 1444.11.10` — Mazowsze jest wasalem, a poprzednia unia z Litwą kończy się dzień przed początkiem gry.
- `events/flavorPOL.txt`, `flavor_pol.18` — Warunki, losowy czas i opcja wysłania decyzji Litwie.
- `events/flavorLIT.txt`, `flavor_lit.16` — Wagi obu odpowiedzi AI i utworzenie unii przez Polskę po przyjęciu.
- `events/flavorPOL.txt`, `flavor_pol.20` — Przyjęcie reformy polskiej monarchii elekcyjnej po zgodzie Litwy.
- `decisions/TheCommonwealth.txt`, `pol_commonwealth / allow` — Unia z Litwą, zniknięcie Mazowsza i własne rdzenie w zachodnich Prusach są wymagane.

<a id="flavor-pol-18-b"></a>
## Miejscowy szlachcic zamiast Jagiellona: polska strategia zachodnia

Jeśli wybierzesz miejscowego szlachcica, Polska otrzyma osobnego władcę i pogorszy stosunki z Litwą. W Lions of the North Następstwa Warny mogą wtedy dać pretekst do wymuszenia unii personalnej z Czechami, podczas gdy wybór Jagiellona kieruje analogiczną nagrodę na Węgry. Misja wymaga dwóch sojuszników, armii co najmniej na 90% limitu i spełnienia warunku osobno wobec Czech i Węgier. W gałęzi rywalizacji sprawdza, czy to Czechy lub Węgry uznają Polskę za rywala. Innymi możliwościami są m.in. obrażenie celu albo sojusz. Sojusz z celem unii przełącza nagrodę na korzyści dyplomatyczne, więc przed odebraniem nagrody sprawdź status celu. Przy miejscowym szlachcicu droga do Rzeczypospolitej wymaga uzyskania unii z Litwą inną drogą lub ziem pod decyzję wymuszoną.

**Zakres i warunki.** Opis Następstw Warny dotyczy Lions of the North. Skrypt wyznacza warunki przyznania pretekstu, a bieżące sojusze, podległość lub zniknięcie kraju mogą zmienić nagrodę i wykonalność wojny.

**Punkty odniesienia w plikach EU4 1.37.5.0.**

- `events/flavorPOL.txt`, `flavor_pol.18.b` — Miejscowy władca, pogorszenie relacji z Litwą i flaga ścieżki z dodatkiem.
- `missions/SCA_Polish_Missions.txt`, `pol_varna_aftermath / trigger i hidden_effect` — Warunki misji oraz odrębne nagrody wobec Czech i Węgier po każdym z wyborów, w tym pierwszeństwo sojuszu.
- `common/scripted_triggers/00_scripted_triggers.txt`, `valid_for_personal_unions_trigger` — Skrypt wymaga istniejącego, niezależnego kraju chrześcijańskiego będącego monarchią albo republiką niderlandzką.
- `decisions/TheCommonwealth.txt`, `pol_commonwealth oraz commonwealth_enforced` — Decyzje unijna i wymuszona mają odmienne warunki.

<a id="pol-throne-bohemia"></a>
## Sojusz z Czechami lub Węgrami daje dyplomatyczną szansę na unię

Po Następstwach Warny polskie misje o tronie czeskim i o ochronie Węgier można wykonać także przez sojusz z odpowiednim krajem. Dyplomatyczna ścieżka wymaga opinii sojusznika o Polsce co najmniej +190, pokoju u sojusznika oraz przewagi Polski w rozwoju i liczebności armii, a warunek zapisany dla aktywnego Leviathan to zaufanie 100. Odebranie misji, gdy z krajem trwa sojusz, wywołuje wybór po jego stronie. Może on zgodzić się na unię albo zaproponować wzmocnione więzi, a podstawowe wagi AI to odpowiednio 1 i 8, z dodatnimi modyfikatorami wagi unii za określone idee lub zaufanie. Wniosek strategiczny: drogę sojuszniczą warto wybierać, kiedy długotrwały sojusz też służy celom kampanii.

**Zakres i warunki.** Dotyczy drzewa Lions of the North. Podane wagi są wagami bazowymi, a dostępność misji przez wcześniejszy podbój lub podporządkowanie kraju podlega oddzielnym warunkom.

**Punkty odniesienia w plikach EU4 1.37.5.0.**

- `missions/SCA_Polish_Missions.txt`, `pol_throne_bohemia` — Warunki dyplomatyczne dla Czech i wywołanie ich wydarzenia przy czynnym sojuszu.
- `missions/SCA_Polish_Missions.txt`, `pol_protect_hungary` — Analogiczne warunki dla Węgier i osobne wydarzenie przy czynnym sojuszu.
- `events/flavorPOL.txt`, `flavor_pol.25 oraz flavor_pol.26` — Opcje adresatów, wagi AI, modyfikatory wagi zgody i skutki wyborów.

<a id="prussian-confederation-disaster"></a>
## Prusy: czekać na bunt Konfederacji czy ruszyć po Gdańsk

Pruska Konfederacja może wybuchnąć u Krzyżaków od 1460 do końca 1499, jeżeli aktywna jest odpowiednia katastrofa, a zakon jest niezależny, nie został jeszcze rozbity przez Konfederację, jest w pokoju, graniczy z niezależną Polską i nie jest jej sojusznikiem. Gdańsk musi pozostać pod kontrolą i własnością zakonu albo jego poddanego Gdańska, a zakon może wcześniej powstrzymać katastrofę. Jeśli zakon zaatakuje Konfederację, Polska dostaje wydarzenie o wsparciu, którego przyjęcie zawiera sojusz z Gdańskiem i zapisuje poparcie potrzebne do jego podporządkowania przez misję. Czekanie ma sens, jeśli można wykorzystać wcześniejsze lata gdzie indziej i pozostawić zakon w stanie spełniającym warunki. Samodzielny podbój Gdańska i Malborka jest bardziej sterowalnym otwarciem pod Rzeczpospolitą, gdy czekanie grozi utratą tych ziem na rzecz innego państwa lub zakon może zamknąć ścieżkę Konfederacji.

**Zakres i warunki.** Okno wydarzenia wynika ze skryptu, a jego wystąpienie pozostaje warunkowe i losowe. Premia z misji zwykłego podboju różni się między drzewami z Lions of the North i bez dodatku.

**Punkty odniesienia w plikach EU4 1.37.5.0.**

- `common/disasters/prussian_confederation.txt`, `prussian_confederation_disaster` — Od 1450 katastrofa może zacząć narastać w epoce odkryć.
- `events/flavorTEU.txt`, `flavor_teu.1 / trigger i flavor_teu.2.a` — Okno, warunki wystąpienia, możliwość wojny oraz polska odpowiedź zapisująca wsparcie.
- `decisions/PrussianConfederation.txt`, `curtail_prussian_confederation` — Zakon bez odpowiedniej misji może powstrzymać Konfederację decyzją.
- `missions/SCA_Teutonic_Missions.txt`, `teu_handle_the_prussian_confederation` — Rozszerzone drzewo Krzyżaków pozwala powstrzymać Konfederację misją.
- `decisions/TheCommonwealth.txt`, `pol_commonwealth / owns_core_province = 43` — Gdańsk i Malbork są obowiązkowymi polskimi rdzeniami przy formowaniu przez unię.

<a id="prussian-confederation-mission-pol"></a>
## Gdańsk jako wasal lub Prusy Książęce: wybierz pod wymagane rdzenie

Po poparciu Konfederacji misja może być zaliczona, gdy Gdańsk jest niezależny i w pokoju, lecz nagroda z wydarzeniem o wasalizacji ma dodatkowy próg poniżej 100 rozwoju Gdańska. Zwykły wybór wasalizacji pozostawia Gdańsk jako osobne państwo i przyznaje roszczenia do wybranych ziem Prus Zachodnich. Jeśli Prusy jeszcze nie istnieją, drugi wybór także wasalizuje Gdańsk, zmienia jego tag na Prusy z nazwą Prusy Książęce i przekazuje Polsce należące do niej lub jej poddanych prowincje Prus Zachodnich wraz z rdzeniami. Przy formowaniu Rzeczypospolitej sprawdź, czy wariant od razu zapewni Gdańsk i Malbork jako polskie rdzenie.

**Zakres i warunki.** Wariant Prus Książęcych nie przekazuje ziem trzymanych przez obce niezależne państwo. Warunek pokojowego i niezależnego Gdańska można obejść, zaliczając misję przez kontrolę wymaganych prowincji, ale to samo w sobie nie uruchamia nagrody wasalizacji.

**Punkty odniesienia w plikach EU4 1.37.5.0.**

- `missions/Polish_Missions.txt`, `prussian_confederation_mission_pol` — Podstawowe drzewo rozdziela warunek zaliczenia misji od progu rozwoju przy nagrodzie wasalizacji.
- `missions/SCA_Polish_Missions.txt`, `pol_prussia_confederation` — Rozszerzone drzewo używa tego samego warunku nagrody, ale wymaga również Prus Wschodnich przy zaliczeniu przez kontrolę terytorium.
- `events/flavorTEU.txt`, `flavor_teu.3.a oraz flavor_teu.3.b` — Dwie opcje podległości, w tym warunek braku istniejących Prus i przekazanie ziem Prus Zachodnich z rdzeniami.
- `map/area.txt`, `west_prussia_area` — Prowincje 43 i 1841 leżą w obszarze objętym transferem.
- `decisions/TheCommonwealth.txt`, `pol_commonwealth / allow` — Polska musi sama posiadać rdzenie na Gdańsku i Malborku.
- `localisation/scandinavia_l_english.yml`, `RPR:1` — Nazwa ustawiana przez wydarzenie to Ducal Prussia, czyli Prusy Książęce.

<a id="pol-commonwealth-potential-allow-i-inherit-lit"></a>
## Utworzenie Rzeczypospolitej: dwa tryby i granice dla Litwy

Polska jako senior unii z Litwą może utworzyć Rzeczpospolitą standardowo przy 10. technologii administracyjnej, stabilności co najmniej +1 i w pokoju, jeśli sama posiada własne rdzenie na Krakowie, Warszawie, Gdańsku i Malborku, a Mazowsze nie istnieje. Litwa musi mieć mniej niż 60 miast i mniej niż 25% chęci wolności oraz nie może być krajem, którym grał człowiek. Decyzja bezpośrednio dziedziczy Litwę, więc przy planowaniu pod tę decyzję zostaw jej najwyżej 59 miast i monitoruj chęć wolności, zanim oddasz jej kolejne zdobycze. Bez wzajemnej unii decyzja wymuszona wymaga dodatkowo własnych rdzeni na Wilnie, Mińsku, Kijowie i Turowie oraz stabilności +3 przy 10. technologii administracyjnej i pokoju. Decyzja wymuszona sama nie przejmuje reszty terytorium Litwy.

**Zakres i warunki.** Wyjątkiem od technologii 10 w unijnej decyzji jest wybór cesji Rusi w Negocjacjach Lubelskich. Decyzje mają także ograniczenia widoczności, m.in. dla wcześniej utworzonej lub istniejącej Rzeczypospolitej.

**Punkty odniesienia w plikach EU4 1.37.5.0.**

- `decisions/TheCommonwealth.txt`, `pol_commonwealth / potential, allow i inherit = LIT` — Ustala wszystkie podane progi i dziedziczenie Litwy, w odróżnieniu od zwykłej integracji.
- `decisions/TheCommonwealth.txt`, `commonwealth_enforced / potential, allow i effect` — Ustala warunek braku unii, rozszerzoną listę rdzeni i brak dziedziczenia.
- `events/flavorPOL.txt`, `flavor_pol.32.a` — Ustawia wyjątek dla technologii administracyjnej 8.

<a id="poland-sca-slot-5-branching-lit-east-pol-develop-ukraine"></a>
## Negocjacje Lubelskie: wcześniejsza Rzeczpospolita ma koszt

Przy Lions of the North na ścieżce unijnej misja rozwoju Rusi może wywołać Negocjacje Lubelskie, jeśli Litwa nadal jest poddanym Polski i posiada oba obszary nad Dnieprem, a Podole z Wołyniem pozostają pod kontrolą Polski lub jej poddanych. Misja wymaga inwestycji w te obszary, dodatkowego rozwoju kilku prowincji oraz osobnego warunku dotyczącego Kijowa. Opcja cesji ziem obniża próg technologii unijnej decyzji o utworzeniu Rzeczypospolitej z 10 do 8, ale zabiera historyczną przyjaźń w obie strony i daje Litwie modyfikator opinii o Polsce −100. Druga opcja przyznaje obu krajom czasowe obniżki kosztów rozwoju i stabilności. Strategicznie cesja ma największy sens, kiedy możesz domknąć pozostałe warunki decyzji i utrzymać chęć wolności Litwy poniżej 25% po zmianie relacji.

**Zakres i warunki.** Przy aktywnym Leviathan Ławra Peczerska na poziomie 2 lub 3 może zastąpić kijowski wymóg pięciu ulepszeń i budynku podatkowego. Ścieżka cesji nadal wymaga unii i polskich rdzeni z decyzji.

**Punkty odniesienia w plikach EU4 1.37.5.0.**

- `missions/SCA_Polish_Missions.txt`, `poland_sca_slot_5_branching_lit_east / pol_develop_ukraine` — DLC, wybór ścieżki, warunki inwestycji i uruchomienia wydarzenia.
- `events/flavorPOL.txt`, `flavor_pol.32.a oraz flavor_pol.32.b` — Cesja, usunięcie przyjaźni, flaga wcześniejszej formacji lub wspólny modyfikator.
- `common/opinion_modifiers/00_opinion_modifiers.txt`, `pol_annexed_ruthenia_opinion_modifier` — Kara do opinii Litwy o Polsce wynosi 100 i zanika o 2 rocznie.
- `common/event_modifiers/01_mission_modifiers.txt`, `pol_shared_prosperity_modifier` — Określa czasowe korzyści przy pozostawieniu ziem Litwie.
- `decisions/TheCommonwealth.txt`, `pol_commonwealth / pol_tech_8_form_plc_flag` — Przy fladze wymaga 8. technologii administracyjnej, a pozostałe warunki nadal obowiązują.

<a id="first-pol-second-maz"></a>
## Mazowsze i Warszawa: integracja oraz decyzja o stolicy

Mazowsze zaczyna jako wasal Polski i właściciel Warszawy, a obie polskie decyzje o utworzeniu Rzeczypospolitej wymagają zniknięcia Mazowsza i polskiego rdzenia na Warszawie. Dlatego warto planować jego integrację jako oddzielny krok obok wojny lub negocjacji o Prusy. Po uzyskaniu rdzenia na Warszawie i włączeniu jej do stanu można w pokoju przenieść tam stolicę decyzją, która dodaje Warszawie po jednym punkcie każdego rodzaju rozwoju. Przy Lions of the North misja mazowiecka wymaga dodatkowo posiadania całego obszaru Mazowsza i prowincji 1940, siedziby stolicy w Warszawie oraz sześciu odnotowanych ulepszeń rozwoju w mieście.

**Zakres i warunki.** Przeniesienie stolicy służy m.in. tej misji. Obie decyzje o utworzeniu Rzeczypospolitej sprawdzają posiadanie rdzeni i istnienie Mazowsza, niezależnie od położenia stolicy.

**Punkty odniesienia w plikach EU4 1.37.5.0.**

- `history/diplomacy/Baltic_alliances.txt`, `first = POL / second = MAZ` — Wasalstwo Mazowsza w dacie początkowej.
- `history/provinces/257 - Warszawa.txt`, `owner = MAZ` — Warszawa należy do Mazowsza w dacie początkowej.
- `decisions/TheCommonwealth.txt`, `pol_commonwealth oraz commonwealth_enforced / allow` — Właściwe decyzje wymagają rdzenia Warszawy i braku Mazowsza.
- `decisions/Poland.txt`, `move_capital_to_warsawa` — Warunki przeniesienia stolicy i trzy przyrosty bazowego rozwoju.
- `missions/SCA_Polish_Missions.txt`, `pol_deal_mazovia` — Wymogi misji mazowieckiej dostępnej w rozszerzonym drzewie.

<a id="add-government-reform-polish-great-sejm-oraz-1444-10-1"></a>
## Złota Wolność, sejm i elekcja: osobne mechaniki

Polska zaczyna z reformą Wielkiego Sejmu i przywilejem Złotej Wolności, a zgoda Litwy na unię przez wydarzenie nakłada osobną reformę polskiej monarchii elekcyjnej. Obie reformy mają parlament, gdy aktywne jest Common Sense albo Domination, a właściwa mechanika elekcji polskiej w reformie elekcyjnej ma osobny warunek Res Publica. Złota Wolność daje +33% krajowych zasobów ludzkich i odbiera bazowo 15 maksymalnego absolutyzmu. Odwołanie przywileju wymaga stabilności +3 i braku regencji, ma dodatkową bramkę ustrojową dla Polski i Rzeczypospolitej oraz kosztuje 3 stabilności, jeśli istnieje stan szlachecki. Wniosek strategiczny: przywilej daje realne wsparcie wojskowe na otwarciu, ale późniejszą centralizację warto planować z uwzględnieniem reformy ustroju i drogi do odwołania przywileju.

**Zakres i warunki.** Odrzucenie Jagiellona może pozostawić Wielki Sejm, ale Polska nadal zaczyna ze Złotą Wolnością. Zakończenie odpowiednich misji lub rozwój absolutyzmu otwierają część dróg odwołania przywileju.

**Punkty odniesienia w plikach EU4 1.37.5.0.**

- `history/countries/POL - Poland.txt`, `add_government_reform = polish_great_sejm oraz 1444.10.1` — Reforma i przywilej są obecne na starcie.
- `events/flavorPOL.txt`, `flavor_pol.20.a` — Unia uruchamia przyjęcie reformy elekcyjnej i w razie wcześniejszego braku przywraca Złotą Wolność.
- `common/government_reforms/01_government_reforms_monarchies.txt`, `polish_great_sejm oraz polish_elective_monarchy / conditional` — Osobne warunki DLC na parlament i rzeczywistą elekcję.
- `common/estate_privileges/02_noble_privileges.txt`, `estate_nobles_golden_liberty / benefits, can_revoke i on_revoked` — Manpower, koszt absolutyzmu, warunki odwołania i utrata stabilności.

<a id="pol-ideas-oraz-plc-ideas"></a>
## Husaria i wybór idei po utworzeniu Rzeczypospolitej

Idee narodowe Polski i Rzeczypospolitej formowanej Polską mają Skrzydlatą Husarię z +30% zdolności bojowej kawalerii oraz odblokowaniem rekrutacji husarii dostępnej z Lions of the North. Polska ma od początku −10% kosztu kawalerii, a dalsze polskie idee wzmacniają m.in. zasoby ludzkie i morale armii. Rzeczpospolita ma zamiast tego m.in. +10% ilości towarów, −10% kosztu idei i +1 punkt administracyjny miesięcznie. Przy zmianie tagu gracz bez własnych idei może zostawić aktualny zestaw lub przejść na idee Rzeczypospolitej bez resetu postępu. Strategicznie zachowanie polskich idei jest sensowne, gdy priorytetem są wczesne koszty i liczebność armii, a przyjęcie idei Rzeczypospolitej wzmacnia gospodarkę i zwiększa dopływ punktów administracyjnych bez utraty premii do siły kawalerii.

**Zakres i warunki.** Skrzydlata Husaria to idea odblokowywana w toku kampanii, a nie nieograniczony typ oddziału dostępny w 1444. Efekt siły kawalerii jest zapisany w ideach niezależnie od DLC z jednostką specjalną.

**Punkty odniesienia w plikach EU4 1.37.5.0.**

- `common/ideas/00_country_ideas.txt`, `POL_ideas oraz PLC_ideas` — Porównanie tradycji, premii wojskowych, ekonomicznych i wspólnej idei Skrzydlatej Husarii.
- `decisions/TheCommonwealth.txt`, `pol_commonwealth / country_event = { id = ideagroups.1 }` — Przekazuje graczowi wybór idei po zmianie kraju.
- `events/IdeaGroups.txt`, `id = ideagroups.1` — Opcja wymiany zachowuje postęp, druga nie wykonuje wymiany.
- `patchnotes/1.34 Patchnotes.txt`, `2 new special units, 'Caroleans' and 'Winged Hussars'` — Informacja o jednostce wśród funkcji Lions of the North.
- `localisation/scandinavia_l_english.yml`, `custom_can_recruit_hussars_desc` — Liczebność regimentów specjalnych jest ograniczona rozwojem prowincji akceptowanych kultur.

<a id="trade-goods-gems-vistula-estuary-modifier-center-of-trade-2"></a>
## Kraków, Gdańsk i handel bałtycki

Gdańsk leży w węźle Morza Bałtyckiego i na starcie ma centrum handlu poziomu 2, ujście Wisły oraz klejnoty jako towar handlowy. Węzeł krakowski odpływa do Bałtyku, Wiednia i Saksonii, więc zdobyty Gdańsk pozwala korzystać z bałtyckiej trasy, jeśli masz dość siły handlowej także w węźle docelowym. Z Lions of the North po misjach Konfederacji Pruskiej i zwołania pospolitego ruszenia rozbudowa Gdańska wymaga budynku handlowego i produkcyjnego oraz odpowiedniego poziomu rozwoju lub centrum handlu. Strategicznie warto ocenić przepływ handlu przed przeniesieniem głównego portu i planować te budynki pod misję wtedy, gdy Gdańsk ma znaczenie w kampanii.

**Zakres i warunki.** Przy aktywnym Dharma misja akceptuje 35 rozwoju lub centrum handlu poziomu 3. Bez tego warunku DLC skrypt wymaga 40 rozwoju. Skrypt węzłów dowodzi kierunku, a przewidywany dochód zależy od aktualnej siły handlowej i sterowania handlem.

**Punkty odniesienia w plikach EU4 1.37.5.0.**

- `history/provinces/43 - Danzig.txt`, `trade_goods = gems / vistula_estuary_modifier / center_of_trade = 2` — Towar, ujście Wisły i poziom centrum handlu na starcie.
- `common/tradenodes/00_tradenodes.txt`, `krakow={ oraz baltic_sea={` — Kierunki wypływu krakowskiego i przynależność Gdańska do Bałtyku.
- `missions/SCA_Polish_Missions.txt`, `pol_embellish_gdansk` — Warunki misji budowlanej i modyfikacja progów za Dharma.
- `events/flavorPOL.txt`, `flavor_pol.31.a` — Rozbudowany Gdańsk otrzymuje dodatkowy rozwój i czasowy modyfikator.

<a id="owner-pol-oraz-fort-15th-yes"></a>
## Obrona Polski: budynki wojskowe jako inwestycja pod misję węgierską

Kraków należy do Polski i ma fort już w dacie startowej. Z Lions of the North misja ochrony Węgier dolicza jeden punkt bazowych zasobów ludzkich w każdej własnej prowincji, która ma budynek zwiększający zasoby ludzkie, limit armii albo fort. Sprawdzenie jest warunkiem alternatywnym, więc postawienie kilku z tych budynków w tym samym mieście nadal daje jeden punkt. Jeśli i tak inwestujesz w obronę lub rezerwy, ukończ potrzebne budynki przed odebraniem nagrody i wybieraj ich lokalizację według przydatności w kampanii.

**Zakres i warunki.** Warunek uzyskania bonusu dotyczy własności prowincji, więc budynki znajdujące się na ziemiach Litwy w unii go nie dostają. Przesunięcie odebrania misji ma też koszt, jeśli zależy ci na szybkiej odpowiedzi sojusznika na propozycję unii.

**Punkty odniesienia w plikach EU4 1.37.5.0.**

- `history/provinces/262 - Krakow.txt`, `owner = POL oraz fort_15th = yes` — Kraków zaczyna jako polska prowincja z fortem.
- `missions/SCA_Polish_Missions.txt`, `pol_protect_hungary / every_owned_province` — Nagroda sprawdza według alternatywy trzy typy budynków we własnych prowincjach i daje każdej spełniającej warunek jeden punkt bazowych zasobów ludzkich.
- `events/flavorPOL.txt`, `flavor_pol.26` — Wydarzenie węgierskie po misji przewiduje m.in. propozycję unii.
