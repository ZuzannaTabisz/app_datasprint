# Mapa transakcji kartowych w Poznaniu
## English below :)

Interaktywna mapa (strona statyczna, działa na GitHub Pages), która pokazuje, **ile i gdzie w Poznaniu zostawiają pieniędzy różne grupy osób**: mieszkańcy Poznania, mieszkańcy obwarzanka, obcokrajowcy i osoby spoza metropolii. Dane pochodzą z syntetycznych, zanonimizowanych transakcji kartowych (hackathon DataSprint, Visa; kwoty w fikcyjnej walucie).

Strona: https://zuzannatabisz.github.io/app_datasprint/

> [!TIP]
> ## 👉 [OTWÓRZ APLIKACJĘ](https://zuzannatabisz.github.io/app_datasprint/)
> **Naciśnij ▶ Play** i zobacz, jak dane zmieniają się w czasie.
> **Wybierz osiedle** i sprawdź, ile pieniędzy trafia do danej okolicy.

## Co potrafi aplikacja
- **Baner z kwotą wydatków na terenie Poznania**.
- **Heatmapa kodów pocztowych** rysowana wg **łącznej kwoty** (domyślnie) albo **liczby transakcji**. Promień plamy zależy od powierzchni kodu, kolor od kategorii (jasny = mało, ciemny = dużo).
- **Filtry:** kategoria (kategorie zagregowane), osiedle, grupa (wybór wielokrotny, dwuklik = tylko ta grupa), pora dnia (dzień 8–17 / wieczór-noc 18–7).
- **Oś czasu:** przełącznik per miesiąc / per dzień, strzałki, suwak dni, Play.
- **Osiedla:** 42 osiedla, wybór kliknięciem albo z listy. Karta pokazuje liczbę transakcji i średnią kwotę transakcji względem średniej (zielone „+”, czerwone „−”).
- **Wydarzenia w Poznaniu** z kwotą „dodatkowe wydatki ponad zwykły dzień” dla wybranych filtrów.
- Liczby transakcji poniżej 30 są pokazywane jako „<30” w celu zapewnienia zgodności z wymaganiami.

## Stack
| Warstwa | Technologie |
|---|---|
| Dane źródłowe | Parquet, słownik kolumn w Excelu (dane przekazane przez organizatorów) |
| Przetwarzanie | **Python 3.12**, **DuckDB** (agregacja bez ładowania pliku do RAM), **pandas**, **numpy**, **shapely** (przeliczenie kodów pocztowych na osiedla), `gzip`/`struct` (format binarny) |
| Środowisko | conda (`datasprint`) |
| Dane geograficzne | GeoJSON: kody pocztowe (`kody.json`), osiedla (`osiedla.json`) |
| Frontend | HTML + CSS + JavaScript bez frameworka, **Leaflet 1.9.4**, własny renderer heatmapy na `canvas`, kafelki **Esri World Light Gray** |
| Format danych na stronie | miesięczne pliki `.bin` (gzip, tablice typowane) albo `.json` (awaryjnie) |
| Hosting | **GitHub Pages** (folder `docs/`) |

Przeglądarka nie dostaje surowych rekordów, tylko agregaty. Wymagana jest nowsza przeglądarka (Chrome/Edge 80+, Firefox 126+, Safari 16.4+: `DecompressionStream`, CSS `zoom`).

## Pipeline
### 1. Przygotowanie danych (offline)
```mermaid
flowchart TD
    B["poznan_dataset.py<br/>filtr: POS, cp_flag = 1,<br/>fua_enr = POZNAN lub miasto zawiera POZNAN"]
    C[("poznan_dataset.parquet (pełny)<br/>poznan_dataset_mini.parquet (12,97 mln)")]
    D["export_data.py<br/>DuckDB: agregacja dzień × kod pocztowy × kategoria<br/>× grupa analizy × pora dnia"]
    K["kategorie_glowne.py<br/>mapowanie kategorii sprzedawców"]
    G1["kody.json<br/>GeoJSON kodów pocztowych"]
    G2["osiedla.json<br/>GeoJSON osiedli"]
    E1["duze_wydarzenia*.csv<br/>lista wydarzeń"]
    S["shapely<br/>udział każdego kodu w każdym osiedlu"]
    O[("docs/data/<br/>meta.json (kody, kategorie, skale kolorów)<br/>m/*.bin (dane miesięczne)<br/>osiedla.geojson, osiedla_w.json<br/>events.json")]
    P["GitHub Pages<br/>(folder docs/)"]

    B --> C --> D
    K --> D
    G1 --> D
    G2 --> S --> D
    E1 --> D
    D --> O --> P
```

### 2. Działanie w przeglądarce
```mermaid
flowchart LR
    U["Użytkownik:<br/>kategoria, miesiąc/dzień,<br/>grupa, pora dnia, osiedle"]
    M["meta.json<br/>(kody, kategorie, skale)"]
    F["Plik miesięczny<br/>m/&lt;kategoria&gt;_&lt;RRRR-MM&gt;.bin<br/>(gzip → tablice typowane)"]
    A["Agregacja w JS:<br/>filtr grup i pory dnia<br/>kwota lub liczba per kod"]
    H["Heatmapa (canvas):<br/>plama na kod, promień z powierzchni,<br/>kolor wg kategorii"]
    W["Baner, największa kategoria,<br/>karta osiedla, wydarzenia"]

    U --> F
    M --> A
    F --> A --> H
    A --> W
```
Strona ładuje tylko wybrany miesiąc (i w tle pozostałe kategorie tego miesiąca do policzenia największej kategorii), a skala kolorów jest wspólna dla wszystkich miesięcy dzięki maksimom wyliczonym w `export_data.py`.

## Z jakich kolumn korzysta eksport
| Kolumna | Użycie |
|---|---|
| `mrch_ctry_nm` | filtr: tylko `POLAND` |
| `mrch_postal_code` | **rejon heatmapy** (kod pocztowy sprzedawcy, normalizowany do `XX-XXX`) |
| `prch_dt` | dzień |
| `mrch_catg_nm` | kategoria (agregowana do kategorii głównych) |
| `tran_id_gmt_tm` | godzina UTC → pora dnia |
| `issr_ctry_cd` | `<> 616` = obcokrajowcy |
| `lau_enr` | grupa: Poznań, obwarzanek (lista 17 gmin), poza metropolią |
| `cs_tran_amt` | kwoty (łączna i średnia) |

Karta osiedla i heatmapa używają kodu pocztowego **sprzedawcy** (gdzie zapłacono), a nie miejsca zamieszkania karty.

## Definicje i założenia
- **Grupa analizy:** kraj wydawcy ≠ Polska → Obcokrajowcy; `lau_enr` = `POZNAN` → Poznań; `lau_enr` z listy gmin wokół Poznania → Obwarzanek; reszta → Poza metropolią.
- **Pora dnia:** godziny z `tran_id_gmt_tm` (UTC): 8–17 dzień, 18–7 wieczór/noc.
- **„W Poznaniu”:** kody pocztowe przeliczone na osiedla wagami z `osiedla_w.json` (udział powierzchni kodu w osiedlu), zakładając równomierny rozkład transakcji w obrębie kodu. To przybliżenie.
- **Dodatkowe wydatki wydarzenia:** kwota z dni wydarzenia minus liczba dni × średnia dzienna kwota z dni tego samego miesiąca bez żadnego wydarzenia. To prosty szacunek, który nie uwzględnia dnia tygodnia ani świąt, i nie dowodzi związku przyczynowego.
- **Największa kategoria** jest liczona po wszystkich kategoriach niezależnie od wyboru kategorii.

## Compliance (wymogi regulacyjne wyzwania)
Wymogi z opisu wyzwania: (1) brak możliwości identyfikacji pojedynczych osób, czyli analizy i prezentacje tylko na grupach obejmujących **co najmniej 30 kart**; (2) każda grupa porównawcza obejmuje **co najmniej 3 podmioty/graczy**, a udział żadnego z nich nie przekracza **75%** grupy. Rozwiązanie nie może umożliwiać identyfikacji pojedynczych użytkowników, kart, transakcji ani podmiotów.

### Dostosowanie do wymogów
- **Tylko agregaty.** Na stronę trafiają wyłącznie sumy i liczby dla komórek *dzień × kod pocztowy × kategoria × grupa analizy × pora dnia*. Nie publikujemy numerów kart (`pymt_crd_acct_num_raw` nie jest używany w eksporcie), nazw sprzedawców (`mrch_nm_raw`), pojedynczych transakcji ani godzin z dokładnością do minut. Przeglądarka nie dostaje surowych rekordów.
- **Wyniki dla grup, nie dla osób.** Prezentowane są kody pocztowe, osiedla, kategorie i grupy (Poznań, obwarzanek, obcokrajowcy, poza metropolią), a nie użytkownicy.
- **Maskowanie małych liczb w interfejsie.** Liczba transakcji poniżej 30 jest pokazywana jako „<30” (okno statystyk, punkty kodów, karta osiedla, lista kategorii).
- **Parametr `MIN_N`** w `export_data.py` pozwala usunąć z publikowanych plików komórki z mniejszą liczbą transakcji.

## Uruchomienie
Pliki wejściowe leżą w folderze głównym (nie trafiają do repozytorium: `*.parquet` jest w `.gitignore`):
`poznan_dataset_mini.parquet`, `poznan_dataset.parquet`, `kody.json`, `osiedla.json`, `duze_wydarzenia*.csv`.

### 1. Wygeneruj dane
```
conda activate datasprint
conda install -y -c conda-forge shapely
cd app
python export_data.py --dataset mini
```
`--dataset full` używa pełnego zbioru, `--parquet ŚCIEŻKA` dowolnego pliku. Ustawienia na górze `export_data.py`: `DATASET`, `KOD_PREFIKSY`, `KATEGORIE` (`glowne` lub `szczegolowe`), `FORMAT` (`bin` lub `json`), `MIN_N`. Skrypt wypisuje rozmiar wyników i największego pliku miesięcznego.

### 2. Sprawdź lokalnie
Uuruchom serwer:
```
cd docs
python -m http.server 8000
```
i otwórz http://localhost:8000

### 3. Strona opublikuowana na GitHub Pages
```
https://zuzannatabisz.github.io/app_datasprint/index.html
```


# Card Transactions Map of Poznań

An interactive map (static site, hosted on GitHub Pages) showing **how much money different groups of people leave in Poznań, and where**: Poznań residents, residents of the "obwarzanek" (the ring of municipalities around Poznań), foreigners, and people from outside the metropolitan area. The data comes from synthetic, anonymized card transactions (DataSprint hackathon, Visa; amounts are in a fictional currency).

Website: https://zuzannatabisz.github.io/app_datasprint/

> [!TIP]
> ## 👉 [OPEN THE APP](https://zuzannatabisz.github.io/app_datasprint/)
> **Press ▶ Play** and watch how the data changes over time.
> **Select a district** and see how much money flows into that area.

## What the app can do
- **A headline banner** with the amount spent within Poznań.
- **A postal-code heatmap** drawn by **total amount** (default) or **number of transactions**. The size of each blob depends on the area of the postal code, and the color depends on the category (light = low, dark = high).
- **Filters:** category (aggregated categories), district, group (multi-select; double-click = only that group), time of day (day 8–17 / evening–night 18–7).
- **Timeline:** per month / per day switch, arrows, day slider, Play.
- **Districts:** 42 districts, selectable by clicking on the map or from a list. The card shows the number of transactions and the average transaction amount compared with the average (green "+", red "−").
- **Events in Poznań** with the amount of "additional spending above a regular day" for the selected filters.
- Transaction counts below 30 are shown as "<30" to comply with the requirements.

## Stack
| Layer | Technologies |
|---|---|
| Source data | Parquet, column dictionary in Excel (data provided by the organizers) |
| Processing | **Python 3.12**, **DuckDB** (aggregation without loading the file into RAM), **pandas**, **numpy**, **shapely** (converting postal codes to districts), `gzip`/`struct` (binary format) |
| Environment | conda (`datasprint`) |
| Geographic data | GeoJSON: postal codes (`kody.json`), districts (`osiedla.json`) |
| Frontend | HTML + CSS + JavaScript without a framework, **Leaflet 1.9.4**, custom `canvas` heatmap renderer, **Esri World Light Gray** tiles |
| Data format on the site | monthly `.bin` files (gzip, typed arrays) or `.json` (fallback) |
| Hosting | **GitHub Pages** (`docs/` folder) |

The browser does not receive raw records, only aggregates. A modern browser is required (Chrome/Edge 80+, Firefox 126+, Safari 16.4+: `DecompressionStream`, CSS `zoom`).

## Pipeline
### 1. Data preparation (offline)
```mermaid
flowchart TD
    B["poznan_dataset.py<br/>filter: POS, cp_flag = 1,<br/>fua_enr = POZNAN or city contains POZNAN"]
    C[("poznan_dataset.parquet (full)<br/>poznan_dataset_mini.parquet (12.97 M)")]
    D["export_data.py<br/>DuckDB: aggregation day × postal code × category<br/>× analysis group × time of day"]
    K["kategorie_glowne.py<br/>merchant category mapping"]
    G1["kody.json<br/>postal codes GeoJSON"]
    G2["osiedla.json<br/>districts GeoJSON"]
    E1["duze_wydarzenia*.csv<br/>list of events"]
    S["shapely<br/>share of each postal code in each district"]
    O[("docs/data/<br/>meta.json (codes, categories, color scales)<br/>m/*.bin (monthly data)<br/>osiedla.geojson, osiedla_w.json<br/>events.json")]
    P["GitHub Pages<br/>(docs/ folder)"]

    B --> C --> D
    K --> D
    G1 --> D
    G2 --> S --> D
    E1 --> D
    D --> O --> P
```

### 2. How it works in the browser
```mermaid
flowchart LR
    U["User:<br/>category, month/day,<br/>group, time of day, district"]
    M["meta.json<br/>(codes, categories, scales)"]
    F["Monthly file<br/>m/&lt;category&gt;_&lt;YYYY-MM&gt;.bin<br/>(gzip → typed arrays)"]
    A["Aggregation in JS:<br/>group and time-of-day filter<br/>amount or count per code"]
    H["Heatmap (canvas):<br/>a blob per code, radius from area,<br/>color by category"]
    W["Banner, top category,<br/>district card, events"]

    U --> F
    M --> A
    F --> A --> H
    A --> W
```
The site loads only the selected month (and, in the background, the other categories of that month in order to compute the top category). The color scale is shared across all months thanks to the maximum values computed in `export_data.py`.

## Columns used by the export
| Column | Usage |
|---|---|
| `mrch_ctry_nm` | filter: `POLAND` only |
| `mrch_postal_code` | **heatmap area** (merchant postal code, normalized to `XX-XXX`) |
| `prch_dt` | day |
| `mrch_catg_nm` | category (aggregated into main categories) |
| `tran_id_gmt_tm` | UTC hour → time of day |
| `issr_ctry_cd` | `<> 616` = foreigners |
| `lau_enr` | group: Poznań, obwarzanek (list of 17 municipalities), outside the metropolitan area |
| `cs_tran_amt` | amounts (total and average) |

The district card and the heatmap use the **merchant's** postal code (where the payment was made), not the cardholder's place of residence.

## Definitions and assumptions
- **Analysis group:** issuer country ≠ Poland → Foreigners; `lau_enr` = `POZNAN` → Poznań; `lau_enr` from the list of municipalities around Poznań → Obwarzanek; everything else → Outside the metropolitan area.
- **Time of day:** hours from `tran_id_gmt_tm` (UTC): 8–17 day, 18–7 evening/night.
- **"In Poznań":** postal codes converted to districts using weights from `osiedla_w.json` (the share of the postal code's area within the district), assuming an even distribution of transactions within a postal code. This is an approximation.
- **Additional event spending:** the amount on the event days minus the number of days × the average daily amount from the days of the same month without any event. This is a simple estimate that does not account for the day of the week or public holidays, and it does not prove causation.
- **The top category** is calculated across all categories, regardless of the selected category.

## Compliance (regulatory requirements of the challenge)
Requirements from the challenge description: (1) no possibility of identifying individuals, i.e. analyses and presentations only for groups of **at least 30 cards**; (2) each comparison group includes **at least 3 entities/players**, and no single one of them exceeds **75%** of the group. The solution must not allow identification of individual users, cards, transactions or entities.

### Compliance measures
- **Aggregates only.** Only sums and counts for cells of *day × postal code × category × analysis group × time of day* are published on the site. We do not publish card numbers (`pymt_crd_acct_num_raw` is not used in the export), merchant names (`mrch_nm_raw`), individual transactions, or times down to the minute. The browser does not receive raw records.
- **Results for groups, not for individuals.** The presented units are postal codes, districts, categories and groups (Poznań, obwarzanek, foreigners, outside the metropolitan area), not users.
- **Masking of small numbers in the interface.** A transaction count below 30 is shown as "<30" (statistics panel, code points, district card, category list).
- **The `MIN_N` parameter** in `export_data.py` allows removing cells with a smaller number of transactions from the published files.

## Running the project
The input files are located in the main folder (they are not committed to the repository: `*.parquet` is in `.gitignore`):
`poznan_dataset_mini.parquet`, `poznan_dataset.parquet`, `kody.json`, `osiedla.json`, `duze_wydarzenia*.csv`.

### 1. Generate the data
```
conda activate datasprint
conda install -y -c conda-forge shapely
cd app
python export_data.py --dataset mini
```
`--dataset full` uses the full dataset, `--parquet PATH` any other file. Settings at the top of `export_data.py`: `DATASET`, `KOD_PREFIKSY`, `KATEGORIE` (`glowne` or `szczegolowe`), `FORMAT` (`bin` or `json`), `MIN_N`. The script prints the size of the output and of the largest monthly file.

### 2. Check locally
Start a server:
```
cd docs
python -m http.server 8000
```
and open http://localhost:8000

### 3. The site published on GitHub Pages
```
https://zuzannatabisz.github.io/app_datasprint/index.html
```
