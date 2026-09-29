# Mapa transakcji kartowych w Poznaniu (GitHub Pages)

Statyczna strona (Leaflet + leaflet.heat) z heatmapą liczby transakcji:
- u góry: wybór **kategorii sprzedawcy** (`mrch_catg_nm`),
- na dole: **oś czasu po dniach** miesiąca (miesiąc + suwak dni, Play/Pause, opcja „cały miesiąc”),
- po prawej: suma, top 5 kodów pocztowych, promień plamy, punkty z podpisami.

Przeglądarka NIE dostaje 64 mln rekordów, tylko zagregowane pliki JSON (dzień × kod pocztowy × kategoria).

## 1. Wygeneruj dane
W Anaconda Prompt:

```
conda activate datasprint
cd %USERPROFILE%\Desktop\datasprint\app
python export_data.py
```

Skrypt szuka `poznan_dataset_mini.parquet` (np. w `..\poznan\`) i `kody.json`. Inne pliki podasz przez
`--parquet SCIEZKA` i `--geojson SCIEZKA`. Ustawienia na górze `export_data.py`:
`KOD_PREFIKSY`, `TOP_KAT` (ile kategorii osobno), `MIN_N` (minimalna liczba transakcji w komórce).
Wynik: `docs/data/*.json` (na końcu skrypt wypisuje łączny rozmiar).

## 2. Sprawdź lokalnie
`fetch` nie działa przy otwarciu pliku z dysku, więc uruchom serwer:

```
cd docs
python -m http.server 8000
```

i otwórz http://localhost:8000

## 3. Opublikuj na GitHub Pages
Pages obsługuje tylko katalog główny repozytorium albo folder `/docs` w jego korzeniu. Dwie drogi:
- **Osobne repo z folderu `app`:** `cd app`, `git init`, dodaj `docs/` i skrypty, wypchnij do nowego repo. Settings → Pages → branch `main`, folder `/docs`.
- **Istniejące repo:** skopiuj zawartość `app/docs/` do folderu `docs/` w korzeniu repo, potem Settings → Pages → `/docs`.

Dane w repo będą publiczne: to agregaty po kodzie pocztowym, kategorii i dniu. Jeśli chcesz ukryć małe liczby (prywatność), podnieś `MIN_N` (np. na 5).
