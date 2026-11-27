# Armia — skład, bitwy i odsiecz

Autor filmu: Skol The Game. Wersja źródła: niepodana, publikacja 2024-09-08. Napisy automatyczne: `ru`. Docelowa baza: EU4 1.37, singleplayer, bez modów. [Army Guide](https://www.youtube.com/watch?v=-u_hnOjIAF4)

<a id="t158"></a>
## Proporcja kawalerii i straty piechoty

Przed zbudowaniem armii z dużą liczbą konnych odczytaj dopuszczalny udział kawalerii dla swojego państwa. Niedobór piechoty względem kawalerii grozi karą do taktyki wojskowej. Skol zwraca uwagę, że straty piechoty mogą pogorszyć proporcję podczas bitwy, dlatego warto zostawić zapas zamiast zaczynać na granicy limitu.

**Zakres i warunki.** Wersja gry w filmie niepodana. Dokładna kara, sposób przeliczania oraz teza o dodatkowej karze na stepie dla każdego państwa wymagają weryfikacji. Plik defines.lua z 1.37.5 podaje jednakową bazową prędkość 0,7 dla wszystkich trzech rodzajów pułków, wbrew tezie filmu o dwukrotnie szybszej kawalerii.

[2:38–3:59 · Skol The Game](https://www.youtube.com/watch?v=-u_hnOjIAF4&t=158s)

<a id="t245"></a>
## Artyleria w drugim szeregu

Utrzymaj piechotę lub kawalerię przed działami. Artyleria strzela z drugiego szeregu, a jej punkty obronne mogą pomóc pułkowi przed nią. Jeśli zabraknie osłony, kosztowne działa stają się łatwiejszym celem na froncie. Nawet skromna liczba dział może pomóc armii w oblężeniach.

**Zakres i warunki.** Defines.lua dla 1.37.5 zawiera mnożnik 0,5 dla drugiego szeregu. Dokładnych zasad przekazywania punktów obronnych i podwójnych strat dział na froncie nie sprawdzono. Tabelę liczby dział dla poszczególnych poziomów fortów widać na ekranie, ale brakuje jej w napisach.

[4:05–4:56 · Skol The Game](https://www.youtube.com/watch?v=-u_hnOjIAF4&t=245s)

<a id="t305"></a>
## Punkty jednostki zależą od fazy walki i grupy technologicznej

Przy wyborze modelu pułku porównaj osobno jego punkty ognia, starcia i morale. Ogień i starcie odpowiadają swoim fazom, a punkty morale mają znaczenie w obu. Punkty ofensywne i defensywne działają po obu stronach bitwy. Kraje z różnych grup technologicznych mogą dysponować innymi modelami przy tym samym poziomie technologii.

**Zakres i warunki.** Rosyjskie napisy często zapisują pips jako „псы”. W przykładzie porównującym grupy zachodnią i muzułmańską brakuje jednego z poziomów, a nazwy państw są uszkodzone. Dokładne modele i momenty awansu trzeba zestawić z common/units i common/technologies/mil.txt dla 1.37.5.

[5:05–6:56 · Skol The Game](https://www.youtube.com/watch?v=-u_hnOjIAF4&t=305s)

<a id="t416"></a>
## Dobór pułków do faz i ról w bitwie

Skol zaczyna wybór piechoty od defensywnego morale. W początkowej grze wysoko ocenia punkty starcia, a wraz ze wzrostem siły artylerii zwiększa wagę ognia. Dla konnicy używanej w fazie starcia ocenia przede wszystkim ofensywne punkty tej fazy. Wczesne modele dział porównuje pod kątem osłony przedniego szeregu, późniejsze przede wszystkim pod kątem własnych obrażeń od ognia.

**Zakres i warunki.** Wersja nagrania niepodana. W 50 starciach Francji z Aragonią dobór autora uzyskał 28 zwycięstw wobec 22 dla rekomendacji moda. Jeden układ i taki wynik nie dowodzą uniwersalnego rankingu. W napisach brakuje tabel oraz pełnych warunków próby.

[6:56–9:41 · Skol The Game](https://www.youtube.com/watch?v=-u_hnOjIAF4&t=416s)

<a id="t622"></a>
## Fazy walki i kondycja pojedynczych pułków

Starcie zaczyna się fazą ognia, po której następuje faza starcia. Każda trwa trzy dni i rozpoczyna się kolejnym rzutem. Obserwuj morale i stan liczebny poszczególnych pułków, zwłaszcza na skrzydłach. Autor wskazuje, że uszczuplone pułki gorzej sięgają celów na flankach, dlatego przed kluczowym starciem warto rozważyć konsolidację osłabionych jednostek.

**Zakres i warunki.** Defines.lua w 1.37.5 potwierdza trzy dni na fazę. Z nagrania nie wyprowadzono progów zasięgu, reguł obsadzania wolnych miejsc ani skutków różnych wariantów konsolidacji dla pustych pułków.

**Punkty odniesienia w plikach EU4 1.37.5.0.**

- `common/defines.lua`, `DAYS_PER_PHASE = 3` — Fazy ognia i starcia trwają po trzy dni.

[10:22–11:58 · Skol The Game](https://www.youtube.com/watch?v=-u_hnOjIAF4&t=622s)

<a id="t746"></a>
## Dowódca, teren i taktyka ograniczają wpływ rzutu

Przed wejściem do bitwy porównaj dowódców w obu fazach, sprawdź pozycję obrońcy oraz teren. O stratach współdecydują rzut, przewaga dowódcy, punkty pułków i warunki terenu. Przy ocenie wymiany strat uwzględnij także technologię i dyscyplinę. Dyscyplina wspiera zadawanie obrażeń i zwiększa taktykę wojskową, która ogranicza otrzymywane straty.

**Zakres i warunki.** Formuły są na ekranie, a napisy miejscami mieszają straty liczebności z morale. W 1.37.5 +1 do rzutu obrońcy ma budynek ramparts, zwykła definicja fortu 4. poziomu nie przyznaje tej premii. Przeliczenie rzutu w filmie ilustruje konkretną konfigurację.

[12:26–15:40 · Skol The Game](https://www.youtube.com/watch?v=-u_hnOjIAF4&t=746s)

<a id="t1010"></a>
## Morale ubywa także w rezerwie

Pułk może tracić morale w trakcie bitwy nawet wtedy, gdy czeka na swoją kolej w rezerwie. Zostawienie części wojsk w sąsiedniej prowincji pozwala wprowadzić świeższe posiłki, o ile dotrą przed załamaniem pierwszego szeregu. Artyleria na tyłach inaczej znosi bierny ubytek morale niż jednostki na froncie, więc potrzeba wymiany dział może przyjść później niż wymiana piechoty.

**Zakres i warunki.** Defines.lua w 1.37.5 zawiera wartości 0,01 dla rozstawionych pułków i 0,02 dla rezerwy oraz mnożnik 0,4 dla tyłu. To parametry biernych strat morale. Wniosek o przetrwaniu dokładnie 2,5 pierwszej linii upraszcza przebieg bitwy.

**Punkty odniesienia w plikach EU4 1.37.5.0.**

- `common/defines.lua`, `BATTLE_DAILY_MORALE_DAMAGE / RESERVE_DAILY_MORALE_DAMAGE / BACK_LINE_MORALE_DAMAGE_TAKEN_MODIFIER` — Plik określa bierne straty morale na froncie i w rezerwie oraz osobny mnożnik tylnego szeregu.

[16:50–18:01 · Skol The Game](https://www.youtube.com/watch?v=-u_hnOjIAF4&t=1010s)

<a id="t1146"></a>
## Szerokość walki jako punkt wyjścia do składu armii

Odczytaj aktualną szerokość walki i dobierz do niej pierwszą linię piechoty z ewentualną kawalerią. Jeśli nie inwestujesz w kawalerię, piechota może obsadzić cały pierwszy szereg. W przykładowej armii typowego kraju Skol używa małej liczby konnych na skrzydłach, żeby piechota również miała cele w zasięgu. Liczniejszą jazdę rozważa w państwach z mocnymi premiami lub modelami pułków.

**Zakres i warunki.** Rozmieszczenie w pokazie Francji z Aragonią zależy od szerokości przeciwnika i zasięgu jednostek. Proponowana liczba konnych zależnie od technologii to szablon autora bez testu jego optymalności w 1.37.

[19:06–22:19 · Skol The Game](https://www.youtube.com/watch?v=-u_hnOjIAF4&t=1146s)

<a id="t1339"></a>
## Od dział oblężniczych do pełnego drugiego szeregu

Po odblokowaniu dział na 7. technologii wojskowej można zacząć od grupy wspierającej oblężenia, jeśli budżet nie pomieści całego tylnego szeregu. Na 16. technologii działa zyskują duży bonus do ognia i pełny drugi szereg ma więcej sensu w ważnych bitwach. Zaplanuj również wydatki na linię osłaniającą działa i ewentualne posiłki.

**Zakres i warunki.** Plik common/technologies/mil.txt dla 1.37.5 potwierdza pierwszy model dział na 7. poziomie i wzrost artillery_fire o 1 na 16. poziomie. Podana w filmie liczba dziesięciu dział nie jest uniwersalnym minimum dla oblężenia.

[22:19–23:10 · Skol The Game](https://www.youtube.com/watch?v=-u_hnOjIAF4&t=1339s)

<a id="t1396"></a>
## Kiedy posiłki muszą dotrzeć do bitwy

Obserwuj morale pułków pierwszego szeregu i czas dojścia następnej armii. Posiłki muszą dołączyć zanim front załamie się lub przestanie osłaniać działa. Przy dłuższym marszu ruch może rozpocząć się jeszcze przed pierwszą bitwą. Zapasową artylerię możesz wprowadzić później niż świeżą piechotę, jeśli działa nadal mają morale i osłonę. Skoryguj plan według rzeczywistych strat i ogólnego morale armii.

**Zakres i warunki.** Wczesne trzy do czterech faz po trzy dni i jednoczesne 12–15 dni w napisach są niespójne. Nie zweryfikowano uniwersalnego terminu pojawienia się posiłków ani przewidywalnego zajmowania przez kawalerię konkretnych miejsc po wejściu później.

[23:16–25:43 · Skol The Game](https://www.youtube.com/watch?v=-u_hnOjIAF4&t=1396s)

<a id="t1582"></a>
## Morale z prestiżu, projekcji siły i tradycji armii

Przy ocenie morale przed wojną uwzględnij prestiż, projekcję siły, tradycję armii i doradcę wojskowego. Skol wspomina też o przywileju duchowieństwa premiującym określone wojny. Profesjonalizm wspiera obrażenia i oblężenia, a wystarczająco wysoki ogranicza bierne straty morale rezerwy. Zmiana doradcy może pomóc od razu, podczas gdy tradycję budujesz dłużej.

**Zakres i warunki.** Archiwum 1.37.5 potwierdza skalę premii morale przy 100 prestiżu, projekcji i tradycji jako odpowiednio 10%, 10% i 25% oraz premię organizacji rezerw od 80% profesjonalizmu. Profesjonalizm wymaga Cradle of Civilization, a przywilej odpowiedniego stanu i spełnienia warunków wojny.

[26:22–28:58 · Skol The Game](https://www.youtube.com/watch?v=-u_hnOjIAF4&t=1582s)
