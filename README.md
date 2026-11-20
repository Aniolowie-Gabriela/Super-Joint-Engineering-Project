# Lokalny asystent Europa Universalis IV

Zadawaj po polsku pytania o rozgrywkę. Asystent korzysta z naszej wiedzy o EU4 1.37.5.0 i podaje źródła. Gemma działa na twoim komputerze.

## Uruchom na Windows

1. Zainstaluj Python 3.12 lub nowszy oraz Ollamę. Otwórz Ollamę. [Python](https://www.python.org/downloads/) · [Ollama dla Windows](https://docs.ollama.com/windows)
2. Pobierz repozytorium przez **Code → Download ZIP** i rozpakuj je lub użyj polecenia poniżej.
3. Otwórz [Przygotuj-EU4.cmd](Przygotuj-EU4.cmd). Naciśnij Enter, aby użyć wspólnej wiedzy. Jeśli chcesz dołączyć reguły i historię z własnej instalacji gry, wpisz jej folder. Przy pierwszym uruchomieniu pobierane są zależności i modele.
4. Otwórz [Zapytaj-EU4.cmd](Zapytaj-EU4.cmd) i wpisz pytanie, np. „Po co mi kupcy?”.

~~~powershell
git clone https://github.com/Aniolowie-Gabriela/Super-Joint-Engineering-Project.git
cd Super-Joint-Engineering-Project
~~~

[Schemat działania i odtwarzanie testu](docs/eu4-workflow.md) · [Przykładowa rozmowa o kampanii Polską](docs/eu4-polska-demo.md) · [Materiały do bazy](sources/eu4/README.md)

## Agent skills

[taf4you2/agent-skills](https://github.com/taf4you2/agent-skills) is included as a Git submodule in `agent-skills/`.

To use the agent skills, clone the project with the submodule:

```bash
git clone --recurse-submodules https://github.com/Aniolowie-Gabriela/Super-Joint-Engineering-Project.git
```

For an existing checkout, fetch the pinned version:

```bash
git submodule update --init --recursive
```

To update to the latest upstream `main`, then record the new version:

```bash
git submodule update --remote agent-skills
git add agent-skills
git commit -m "chore: update agent-skills submodule"
```

See [the agent-skills README](agent-skills/README.md) for skill descriptions and setup instructions.
