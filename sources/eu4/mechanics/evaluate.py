"""Mała próba A/B lokalnej Gemmy na pytaniach o EU4 1.37.5.0."""

import argparse
from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import re
import sqlite3
from time import perf_counter

from ask import ask


VERSION_PROMPT = "EU4 1.37.5.0, bez modów. "
CITATION = re.compile(r"\[\s*\d+(?:\s*[,;–-]\s*\d+)*\s*\]")
NORMALIZATION = str.maketrans({"−": "-", "–": "-", "—": "-", "\u00a0": " ", "\u202f": " ", "*": "", "`": ""})


@dataclass(frozen=True)
class Case:
    key: str
    question: str
    expected: str
    game_evidence: tuple[str, ...]
    required: dict[str, str]
    rejected: dict[str, str] = field(default_factory=dict)


CASES = (
    Case(
        key="urban",
        question=(
            "Mam Domination. Osmani są na 3. technologii wojskowej i zatrudniają doradcę "
            "wojskowego poziomu 2, który nie jest Urbanem. Czy da się odebrać The Guns of Urban? "
            "Ile i jakich jednostek wtedy powstanie? Od którego poziomu technologii zmienia się ich typ i na jaki?"
        ),
        expected=(
            "Tak, wymagany jest doradca wojskowy co najmniej poziomu 2. Przed technologią wojskową 7 "
            "misja daje 4 jednostki Large Cast Bronze Mortar, od technologii 7 daje 4 zwykłe jednostki artylerii."
        ),
        game_evidence=(
            "missions/DOM_Ottoman_Missions.txt:1155–1185 — tur_guns_of_urban, próg przejścia i oba efekty",
            "common/scripted_triggers/00_scripted_triggers.txt:37 — has_mil_advisor_2",
            "localisation/text_l_english.yml:1423 — Large Cast Bronze Mortar",
        ),
        required={
            "doradca_spelnia_wymaganie": r"\btak\b|\bwystarcz\w*|nie (?:trzeba|musisz|wymaga)[^.\n]{0,35}urban",
            "cztery_jednostki": r"\b(?:4|cztery)\b",
            "typ_przed_7": r"large[ _-]+cast[ _-]+bronze[ _-]+mortar|moździerz\w*",
            "zmiana_przy_7": r"\b7\b|siódm\w*",
            "zwykla_artyleria": r"(?:zwykł\w*|standardow\w*|normaln\w*)\s+(?:jednost\w*\s+)?(?:artyleri\w*|dział\w*|armat\w*)",
        },
        rejected={
            "urban_obowiazkowy": r"(?<!nie )\bmusi(?:sz)? (?:zatrudnić|mieć)[^.\n]{0,20}\burban\w*",
        },
    ),
    Case(
        key="lubelskie",
        question=(
            "Polska jest seniorem unii z Litwą, z aktywnym Lions of the North. "
            "W Negocjacjach Lubelskich wybieram cesję Rusi. Jak zmieni się minimalna technologia "
            "administracyjna dla unijnej decyzji o utworzeniu Rzeczypospolitej? Porównaj z normalnym progiem "
            "i podaj zmianę opinii Litwy o Polsce oraz los historycznej przyjaźni."
        ),
        expected=(
            "Cesja obniża próg z 10 do 8 technologii administracyjnej. Litwa dostaje −100 do opinii o Polsce "
            "i oba kraje tracą historyczną przyjaźń."
        ),
        game_evidence=(
            "decisions/TheCommonwealth.txt:49–54 — pol_tech_8_form_plc_flag i progi 8 oraz 10",
            "events/flavorPOL.txt:2774–2781 i 2825–2834 — flavor_pol.32.a, flaga i utrata przyjaźni",
            "common/opinion_modifiers/00_opinion_modifiers.txt:5138–5140 — pol_annexed_ruthenia_opinion_modifier",
        ),
        required={
            "prog_po_cesji": r"\b8\b|ósm\w*",
            "prog_standardowy": r"\b10\b|dziesiąt\w*",
            "opinia_minus_100": (
                r"-\s*100\b|(?:spad\w*|kar\w*|pogorsz\w*|obniż\w*|minus)"
                r"[^.!?\n]{0,55}\b100\b"
            ),
            "utrata_przyjazni": (
                r"(?:trac\w*|usu\w*|znik\w*|utrac\w*|utra[tc]\w*|kończ\w*)[^.!?\n]{0,60}(?:historyczn\w*|historical)"
                r"|(?:historyczn\w*|historical)[^.!?\n]{0,60}(?:trac\w*|usu\w*|znik\w*|utrac\w*|kończ\w*)"
            ),
        },
        rejected={
            "progi_odwrocone": r"\bz\s+(?:8|ósmej)[^.\n]{0,55}\b(?:do|na)\s+(?:10|dziesiąt\w*)",
        },
    ),
    Case(
        key="dekadencja",
        question=(
            "Gram Osmanami z Domination i mechaniką dekadencji. Ottoman Power Struggle jeszcze nigdy "
            "nie wystąpiło ani nie zaczęło naliczania. Przy dekadencji 100, stabilności +3 i władcy 5/5/5 "
            "mój jedyny poddany to core eyalet z 50% chęci wolności. Czy może ruszyć postęp katastrofy? "
            "Czy sam ten stan oznacza jej natychmiastowy wybuch? Co jeśli od początku mam 49% zamiast 50%?"
        ),
        expected=(
            "Przy 50% core eyalet spełnia alternatywny warunek rozpoczęcia naliczania. Katastrofa ma postęp, "
            "więc sam stan nie oznacza jej natychmiastowego wybuchu. Przy 49% i niezmienionych parametrach "
            "warunek rozpoczęcia nie jest spełniony."
        ),
        game_evidence=(
            "common/disasters/ottoman_power_struggle.txt:2–28 — potential oraz can_start",
            "common/disasters/ottoman_power_struggle.txt:49–61 — progress dla ejaletu przy liberty_desire = 50",
        ),
        required={
            "start_przy_50": r"\b(?:tak|może ruszyć|może się rozpocząć)\b|50\s*%[^.!?\n]{0,80}(?:spełnia|wystarcza|umożliwia)",
            "narastanie": r"odlicz\w*|nalicz\w*|nabiera\w* postęp\w*|postęp\w*|progress",
            "brak_natychmiastowego_wybuchu": r"nie[^.!?\n]{0,65}(?:natychmiast|od razu)|(?:natychmiast|od razu)[^.!?\n]{0,32}nie",
            "brak_startu_przy_49": r"49\s*%[^.!?\n]{0,105}\bnie\b|\bnie\b[^.!?\n]{0,105}49\s*%",
        },
    ),
    Case(
        key="township",
        question=(
            "Wykupuję Townships (Township) w kompanii handlowej. Podaj podstawowy koszt w dukatach "
            "i dokładną premię do wartości handlu wraz z jej zasięgiem. "
            "Czy skrypt pozwala mi mieć jednocześnie Governor General’s Mansion w tym samym regionie?"
        ),
        expected=(
            "1000 dukatów, +10% wartości handlu w regionie kompanii. Townships i Governor General’s Mansion "
            "w jednym regionie wzajemnie się wykluczają."
        ),
        game_evidence=(
            "common/tradecompany_investments/00_Investments.txt:331–378 — townships",
            "common/tradecompany_investments/00_Investments.txt:422–458 — governor_general_mansion",
        ),
        required={
            "koszt": r"\b1[ .]?000\b|tysiąc\w*",
            "premia": r"\+?10\s*(?:%|proc\w*|procent\w*)|\b0[,.]1\b",
            "wartosc_handlu": r"wartoś\w* handl\w*|trade[ _]value",
            "zakres_regionu": r"region\w*[^.!?\n]{0,30}(?:kompani\w*|handlow\w*)|company_region_modifier",
            "wykluczenie": r"wyklucz\w*|nie (?:można|da się|pozwala|mog\w*)|\bjedn\w*[^.!?\n]{0,15}inwestycj\w*",
        },
        rejected={
            "plaska_premia": r"(?:płaski\w*|stał\w*)[^.!?\n]{0,12}\+?10\s+(?!%|proc)\w+",
        },
    ),
    Case(
        key="rozejm",
        question=(
            "Kończy mi się rozejm z sąsiadem AI. Ile dni według defines.lua AI musi odczekać "
            "z wypowiedzeniem wojny przeciw temu samemu krajowi? "
            "Czy ta sama stała określa minimalny czas do dołączenia AI do koalicji?"
        ),
        expected=(
            "MIN_DAYS_AFTER_TRUCE_ENDS ma wartość 5 dni. Komentarz opisuje deklarację wojny po wygaśnięciu "
            "rozejmu; ta stała nie określa czasu przystąpienia do koalicji."
        ),
        game_evidence=(
            "common/defines.lua:2188 — MIN_DAYS_AFTER_TRUCE_ENDS = 5 i opis dla deklaracji wojny AI",
            "localisation/aow_l_english.yml:474 — NO_TRUCE_COALITION opisuje ograniczenie podczas rozejmu",
        ),
        required={
            "piec_dni": r"\b(?:5|pięć|pięciu)\s+(?:dni|dniach|day\w*)\b",
            "oddzielne_dolaczenie": (
                r"nie (?:dotyczy|obowiąz\w*|określa|odnosi|stosuj\w*|oznacza|ma zastosowania)"
                r"|(?:tylko|wyłącznie)[^.!?\n]{0,55}(?:wypowiedz\w*|deklar\w*)"
            ),
        },
    ),
    Case(
        key="reconquest",
        question=(
            "Sąsiad posiada mój własny rdzeń. Jaki zwykły CB i jaki cel wojny pozwalają odzyskać tę prowincję? "
            "Wymień żądania pokoju objęte tym celem wojny i podaj w procentach bazowej wartości "
            "dokładny mnożnik agresywnej ekspansji oraz kosztu w wyniku wojny dla mojego rdzenia."
        ),
        expected=(
            "Reconquest (cb_core), cel Take Core (take_core). Warunki premiują żądanie prowincji i zwrot rdzeni. "
            "Dla własnego rdzenia agresywna ekspansja wynosi 25% wartości bazowej, a koszt w wyniku wojny 75%."
        ),
        game_evidence=(
            "common/cb_types/00_cb_types.txt:417–425 — cb_core i cel take_core",
            "common/wargoal_types/00_wargoal_types.txt:778–794 — mnożniki, is_core = ROOT i oba żądania",
            "localisation/text_l_english.yml:6916 — nazwa Reconquest",
        ),
        required={
            "cb": r"reconquest|cb_core|rekonkwist\w*|odzysk\w* rdzeni",
            "cel_wojny": r"take[ _]core|(?:zaj[eę]ci\w*|zdoby\w*|odbicie|odzyska\w*)[^.!?\n]{0,26}rdze",
            "zadanie_prowincji": r"po_demand_provinces|(?:żąd\w*|aneks\w*|przeję\w*|cesj\w*)[^.!?\n]{0,25}prowincj",
            "zwrot_rdzenia": r"po_return_cores|return cores?|zwrot\w* rdze\w*|zwróc\w* rdze\w*",
            "ae_25": (
                r"(?:\b25\s*%|0[,.]25)[^.!?\n\d%]{0,38}(?:\bae\b|agresywn\w* ekspansj\w*)"
                r"|(?:\bae\b|agresywn\w* ekspansj\w*)[^.!?\n\d%]{0,48}(?:\b25\s*%|0[,.]25)"
            ),
            "koszt_75": (
                r"(?:\b75\s*%|0[,.]75)[^.!?\n\d%]{0,33}(?:koszt\w*|warscore|wynik\w* wojn\w*)"
                r"|(?:koszt\w*|warscore|wynik\w* wojn\w*)[^.!?\n\d%]{0,40}(?:\b75\s*%|0[,.]75)"
            ),
        },
        rejected={
            "minus_25_procent_ae": r"(?:\bae\b|agresywn\w* ekspansj\w*)[^.!?\n]{0,35}-\s*25\s*%",
        },
    ),
    Case(
        key="brak_stanu_gry",
        question=(
            "Gram Polską w 1468 r. Rozejm z zakonem krzyżackim trwa jeszcze około dwóch lat. "
            "Podaj dzień, w którym Zakon wypowie mi wojnę koalicyjną, i powiedz, czy Czechy będą w tej wojnie."
        ),
        expected=(
            "Brak podstaw do wyznaczenia dnia, ustalenia czy w ogóle będzie wojna, albo potwierdzenia udziału Czech. "
            "Potrzebny jest stan gry, m.in. dokładna data rozejmu, stan koalicji, opinie i agresywna ekspansja. "
            "Nawet pełny stan nie zmienia minimalnego czasu oczekiwania AI w gwarantowaną datę."
        ),
        game_evidence=(
            "common/defines.lua:2188 — minimalna zwłoka AI nie podaje daty ani decyzji o wojnie",
            "Bieżące dane kampanii nie zostały przekazane.",
        ),
        required={
            "odmowa_pewnej_prognozy": r"nie (?:da się|można|wiadomo|dałob\w*|jest możliw\w*|znam\w*|mamy podstaw)|(?:brak|za mało) (?:danych|informacji|podstaw)",
            "niepewny_udzial_czech": (
                r"(?:\bnie\b|brak podstaw)[^.!?\n]{0,110}(?:czech|uczestnictw|udział)"
                r"|(?:czech|uczestnictw|udział)[^.!?\n]{0,50}(?:\bnie\b|zależ\w*|nieznan\w*)"
            ),
            "wskazuje_brakujace_dane": r"(?:stan\w* (?:gry|kampanii)|zapis\w*|save|dokładn\w* dat\w*|opini\w*|agresywn\w* ekspansj\w*)",
        },
        rejected={
            "podana_konkretna_data": (
                r"\b\d{1,4}[./-]\d{1,2}[./-]\d{1,4}\b"
                r"|\b\d{1,2}\s+(?:stycznia|lutego|marca|kwietnia|maja|czerwca|lipca|sierpnia|"
                r"września|października|listopada|grudnia)\b"
            ),
        },
    ),
)


def grade(case, reply):
    answer = reply["answer"]
    matches = CITATION.findall(answer)
    cited = sorted({int(number) for match in matches for number in re.findall(r"\d+", match)})
    available = {source["number"] for source in reply["sources"]}
    prose = CITATION.sub("", answer).casefold().translate(NORMALIZATION)
    required = {name: bool(re.search(pattern, prose)) for name, pattern in case.required.items()}
    flags = [name for name, pattern in case.rejected.items() if re.search(pattern, prose)]
    unsupported = sorted(set(cited) - available)
    return {
        "required_matches": required,
        "review_flags": flags,
        "cited_source_numbers": cited,
        "unknown_source_numbers": unsupported,
        "full_regex_match": all(required.values()) and not flags and not unsupported,
    }


def evaluate(db_path, model, url, limit, think):
    results = []
    for index, case in enumerate(CASES):
        modes = ("without_rag", "with_rag") if index % 2 == 0 else ("with_rag", "without_rag")
        record = {
            "id": case.key,
            "question": VERSION_PROMPT + case.question,
            "ground_truth": case.expected,
            "game_evidence": case.game_evidence,
            "order": modes,
        }
        for mode in modes:
            context_db = db_path if mode == "with_rag" else None
            started = perf_counter()
            try:
                reply = ask(record["question"], db_path=context_db, model=model, url=url, limit=limit, think=think)
                if mode == "without_rag" and reply["sources"]:
                    raise RuntimeError("Próba bez RAG otrzymała źródła.")
            except RuntimeError as exc:
                if not str(exc).startswith("Model "):
                    raise RuntimeError(f"{case.key}, {mode}: {exc}") from exc
                reply = {"answer": "", "sources": [], "seconds": perf_counter() - started, "model_error": str(exc)}
            except (OSError, ValueError, sqlite3.Error) as exc:
                raise RuntimeError(f"{case.key}, {mode}: {exc}") from exc
            record[mode] = {**reply, "assessment": grade(case, reply)}
        print(f"Zakończono próbę {index + 1}/{len(CASES)} ({case.key}).", flush=True)
        results.append(record)

    if not any(result["with_rag"]["sources"] for result in results):
        raise RuntimeError("Wyszukiwarka nie zwróciła kontekstu dla żadnego pytania. Sprawdź bazę.")

    return {
        "game_version": "1.37.5.0",
        "model": model,
        "url": url,
        "db": str(db_path),
        "limit": limit,
        "thinking": think,
        "backend": os.environ.get("EU4_LLM_BACKEND", "ollama"),
        "method": (
            "To samo pytanie, funkcja ask i ustawienia generacji. Próby różnią się listą kontekstu. "
            "Punktacja jest sprawdzeniem wzorców w odpowiedzi. Treść, jej zgodność z podanym źródłem, "
            "przypisanie liczb do właściwych warunków i złożone cytaty wymagają oceny ręcznej."
        ),
        "summary": {
            mode: {
                "facts_full_regex_match": sum(
                    result[mode]["assessment"]["full_regex_match"] for result in results[:-1]
                ),
                "facts_total": len(results) - 1,
                "uncertainty_full_regex_match": results[-1][mode]["assessment"]["full_regex_match"],
                "answers_with_unknown_source_numbers": sum(
                    bool(result[mode]["assessment"]["unknown_source_numbers"]) for result in results
                ),
            }
            for mode in ("without_rag", "with_rag")
        },
        "cases": results,
    }


def evaluate_holdout(path, db_path, model, url, limit, think):
    """Run questions verbatim, preserving their rubric for manual scoring."""
    questions = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(questions, list) or not questions:
        raise ValueError("Zestaw ma być niepustą tablicą pytań.")
    results = []
    for index, item in enumerate(questions, start=1):
        question = item["question"]
        result = ask(question, db_path=db_path, model=model, url=url, limit=limit, think=think)
        results.append({
            "id": item["id"], "question": question, "expected": item["expected"],
            "required": item["required"], "expected_sources": item["sources"], **result,
        })
        print(f"Zakończono próbę {index}/{len(questions)} ({item['id']}).", flush=True)
    return {
        "game_version": "1.37.5.0", "model": model, "thinking": think,
        "backend": os.environ.get("EU4_LLM_BACKEND", "ollama"),
        "method": "Każde pytanie wysłano dosłownie. Odpowiedzi i cytowania podlegają ocenie według kryteriów.",
        "cases": results,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True, help="plik bazy EU4")
    parser.add_argument("--url", default="http://127.0.0.1:11435", help="lokalny adres Ollamy")
    parser.add_argument("--model", default="gemma4:e4b", help="model dostępny w Ollamie")
    parser.add_argument("--limit", type=int, default=6, help="liczba fragmentów RAG na pytanie")
    parser.add_argument("--no-thinking", action="store_true", help="kontrola z wyłączonym rozumowaniem")
    parser.add_argument("--questions", type=Path, help="własny zestaw oceniany ręcznie")
    parser.add_argument("--output", type=Path, required=True, help="nowy lokalny plik JSON")
    args = parser.parse_args()
    if args.limit < 1:
        parser.error("--limit musi być dodatni.")
    if not args.db.is_file():
        parser.error(f"Nie znaleziono bazy EU4: {args.db}")
    if args.output.exists() or not args.output.parent.is_dir():
        parser.error("--output musi wskazywać nowy plik w istniejącym katalogu.")

    try:
        parameters = (args.db.resolve(), args.model, args.url, args.limit, not args.no_thinking)
        report = evaluate_holdout(args.questions, *parameters) if args.questions else evaluate(*parameters)
        content = json.dumps(report, ensure_ascii=False, indent=2)
        with args.output.open("x", encoding="utf-8") as output:
            output.write(content + "\n")
    except (RuntimeError, OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(2, f"Próba przerwana. {exc}\n")
    print(f"Raport zapisano w {args.output}.")


if __name__ == "__main__":
    main()
