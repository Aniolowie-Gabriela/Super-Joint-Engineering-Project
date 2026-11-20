"""Small deterministic annotations for values and entity names in source fragments."""

from decimal import Decimal
import re


PERCENTAGES = {
    "administrative_efficiency": "efektywność administracyjna",
    "ae_impact": "nowo naliczana agresywna ekspansja",
    "advisor_cost": "koszt doradców",
    "artillery_power": "siła bojowa artylerii",
    "cavalry_power": "siła bojowa kawalerii",
    "core_creation": "koszt tworzenia rdzeni",
    "development_cost": "koszt rozwoju",
    "diplomatic_annexation_cost": "koszt aneksji dyplomatycznej",
    "discipline": "dyscyplina",
    "global_manpower_modifier": "maksymalna pula zasobów ludzkich",
    "global_institution_spread": "globalne rozprzestrzenianie instytucji",
    "global_regiment_cost": "koszt pułków",
    "global_tax_modifier": "krajowy modyfikator podatków",
    "global_trade_goods_size_modifier": "ilość wytwarzanych towarów",
    "global_trade_power": "globalna siła handlowa",
    "infantry_power": "siła bojowa piechoty",
    "improve_relation_modifier": "modyfikator poprawy stosunków i zaniku ujemnych opinii",
    "institution_spread_from_true_faith": "rozprzestrzenianie instytucji w prowincjach prawdziwej wiary",
    "land_maintenance_modifier": "koszt utrzymania wojsk lądowych",
    "land_morale": "morale armii",
    "land_forcelimit_modifier": "limit wojsk lądowych",
    "local_institution_spread": "lokalne rozprzestrzenianie instytucji",
    "local_manpower_modifier": "zasoby ludzkie w tym zakresie",
    "local_production_efficiency": "lokalna efektywność produkcji",
    "local_tax_modifier": "lokalny modyfikator podatków",
    "local_defensiveness": "lokalna obronność",
    "local_sailors_modifier": "marynarze w tym zakresie",
    "liberty_desire": "chęć wolności",
    "missionary_maintenance_cost": "koszt utrzymania misjonarzy",
    "movement_speed": "szybkość poruszania się",
    "merc_maintenance_modifier": "koszt utrzymania najemników",
    "naval_morale": "morale floty",
    "naval_maintenance_modifier": "koszt utrzymania floty",
    "naval_maintenance_flagship_modifier": "utrzymanie okrętu flagowego",
    "production_efficiency": "efektywność produkcji",
    "province_trade_power_modifier": "lokalna siła handlowa",
    "reform_progress_growth": "tempo postępu reform",
    "religious_unity": "jedność religijna",
    "siege_ability": "skuteczność oblężeń",
    "trade_efficiency": "efektywność handlu",
    "trade_steering": "kierowanie handlem",
    "trade_value_modifier": "wartość handlu",
    "vassal_income": "dochód od wasali",
}
POINTS = {
    "artillery_levels_available_vs_fort": "dostępne poziomy premii artylerii przeciw fortom (górna granica)",
    "diplomatic_reputation": "reputacja dyplomatyczna",
    "max_absolutism": "maksymalny absolutyzm, czyli limit",
    "merchants": "liczba kupców",
    "province_trade_power_value": "siła handlowa prowincji (wartość płaska)",
    "reduced_liberty_desire": "odejmowane punkty chęci wolności",
    "trade_goods_size": "ilość wytwarzanych towarów (wartość płaska)",
    "tolerance_heretic": "tolerancja heretyków",
    "flagship_naval_engagement_modifier": "szerokość starcia morskiego",
    "local_monthly_devastation": "miesięczny przyrost dewastacji prowincji",
    "tolerance_heathen": "tolerancja pogan",
    "yearly_corruption": "korupcja rocznie",
    "yearly_inflation_reduction": "redukcja inflacji rocznie",
}
FACTORS = {
    "badboy_factor": "bazowa agresywna ekspansja",
    "peace_cost_factor": "bazowy koszt w wyniku wojny",
    "transfer_trade_cost_factor": "koszt przekazania siły handlowej",
}
ASSIGNMENT = re.compile(r"(?m)^[ \t]*([a-zA-Z_][\w]*)[ \t]*=[ \t]*(-?\d+(?:\.\d+)?)(?=[ \t\r\n#;},]|$)")
LIMITS = re.compile(
    r"\bNOT\s*=\s*\{\s*(num_of_cities|num_of_subjects|num_of_rebel_controlled_provinces)\s*=\s*(\d+)\s*\}"
)
COUNTRY_TAG = re.compile(r"(?m)^[ \t]*(?:owner|controller)[ \t]*=[ \t]*([A-Z0-9]{3})(?=[ \t\r\n#}]|$)")


def number(value):
    return format(value.normalize(), "f").replace(".", ",")


def signed(value):
    return ("+" if value > 0 else "") + number(value)


def annotations(record):
    """Return readable values without deciding which branch applies to a save."""
    source_type = record["source_type"]
    if source_type not in {"game_script", "engine_parameter", "game_map"}:
        return []
    family = record["family"]
    matches = list(dict.fromkeys(ASSIGNMENT.findall(record["text"])))
    counts = {}
    for key, _ in matches:
        counts[key] = counts.get(key, 0) + 1
    notes = []
    if family == "tradegoods":
        notes.append("W definicji towaru modifier jest krajową premią za handel tym towarem, "
                     "a province oznacza premię prowincji, która go produkuje.")
        if "chance =" in record["text"]:
            notes.append("W sekcji chance liczby factor są wagami losowania. "
                         "Nie są procentową szansą. Wynik zależy też od wag innych dostępnych towarów.")
    if family == "centers_of_trade":
        notes.append("province_modifiers dotyczą tej prowincji, a state_modifiers całego stanu.")
    if family == "institutions" and "can_start" in record["text"]:
        notes.append("historical_start_date i historical_start_province są danymi historycznymi. "
                     "Dynamiczny start kampanii zależy od can_start oraz start_chance.")
    if family == "decisions" and "set_in_empire = no" in record["text"]:
        notes.append("Efekt set_in_empire = no oznacza opuszczenie Świętego Cesarstwa. "
                     "Zastosuj go tylko pod warunkami jego otaczającego bloku.")
    if family == "hegemons" and "navy_size" in record["text"]:
        notes.append("navy_size oznacza liczebność całej floty. num_of_heavy_ship to osobny warunek ciężkich okrętów.")
    if family == "peace_treaties":
        notes.append("ROOT oznacza państwo żądające warunku pokoju. FROM oznacza państwo, wobec którego żąda się pokoju.")
        if "define_ruler" in record["text"]:
            notes.append("define_ruler tworzy władcę w otaczającym zakresie. Wartości dynasty = ROOT i culture = ROOT "
                         "pobierają dynastię i kulturę państwa żądającego warunku pokoju.")
    if family == "wargoal_types":
        if "attacker =" in record["text"] or "defender =" in record["text"]:
            notes.append("Odczytaj warunki pokoju osobno dla attacker (atakujący) i defender (obrońca). "
                         "Mnożnik z bloku jednej strony nie dotyczy drugiej.")
    if "add_country_modifier" in record["text"] and re.search(r"\bduration\s*=\s*-1\b", record["text"]):
        notes.append("W add_country_modifier wartość duration = -1 nadaje modyfikator bez końca. "
                     "Sprawdź odrębną definicję modyfikatora, aby poznać wartość premii.")
    for key, raw in matches:
        if counts[key] != 1:
            continue
        value = Decimal(raw)
        if key in FACTORS:
            notes.append(f"{key}: {number(value * 100)}% wartości ({FACTORS[key]}).")
        elif key in PERCENTAGES and family != "technologies" and abs(value) <= 1:
            notes.append(f"{key}: {signed(value * 100)}% ({PERCENTAGES[key]}).")
        elif key in POINTS:
            notes.append(f"{key}: {signed(value)} ({POINTS[key]}).")
        elif key in {"GALLEY_BONUS_INLAND_SEA", "GALLEY_BONUS_COASTAL_SEA"}:
            notes.append(f"{key}: {signed(value * 100)}% bazowego bonusu.")
        elif key == "navy_size_percentage":
            notes.append(f"{key}: {number(value * 100)}% limitu floty.")
        elif key == "local_manpower" and family == "buildings":
            notes.append(f"{key}: {signed(value * 1000)} lokalnych zasobów ludzkich przed innymi mnożnikami.")
        elif key == "DAYS_PER_SIEGE_PHASE":
            notes.append(f"{key}: {number(value)} dni bazowej fazy, bez gwarancji upadku fortu po jednej fazie.")
    for key, raw in dict.fromkeys(LIMITS.findall(record["text"])):
        notes.append(f"NOT ({key} = {raw}): w tej gałęzi musi być mniej niż {raw}.")
    return notes[:9]
