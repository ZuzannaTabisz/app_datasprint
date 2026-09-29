"""Eksport danych do statycznej strony (GitHub Pages).

Agreguje transakcje do postaci: dzień x kod pocztowy x kategoria sprzedawcy (liczba transakcji)
i zapisuje jako małe pliki JSON w docs/data/. Strona (docs/index.html) tylko je wczytuje,
więc 64 mln rekordów NIE trafia do przeglądarki: tylko agregaty.

Wszystkie pliki wejściowe leżą w tym samym folderze co skrypt (app/):
    poznan_dataset_mini.parquet   mniejszy zbiór (szybki test)
    poznan_dataset.parquet        pełny zbiór
    kody.json                     GeoJSON kodów pocztowych
    osiedla.json                  GeoJSON osiedli
    duze_wydarzenia*.csv          lista wydarzeń

Uruchomienie (w środowisku conda datasprint):
    python export_data.py                    (zbiór wybrany w DATASET poniżej)
    python export_data.py --dataset full     (pełny zbiór)
    python export_data.py --dataset mini     (mniejszy zbiór)
    python export_data.py --parquet C:/sciezka/plik.parquet   (dowolny inny plik)
"""
import argparse
import json
import math
import sys
from pathlib import Path

import duckdb
import pandas as pd

from kategorie_glowne import GLOWNE, INNE, case_sql      # agregacja kategorii (przepisana z zapytania SQL)

HERE = Path(__file__).resolve().parent
OUT = HERE / "docs" / "data"

DATASET = "mini"              # domyślny zbiór: "mini" (poznan_dataset_mini.parquet) albo "full" (poznan_dataset.parquet)
DATASETS = {"mini": "poznan_dataset_mini.parquet", "full": "poznan_dataset.parquet"}
KOD_PREFIKSY = None           # None = wszystkie kody z GeoJSON (jak w mapie Folium); ("60", "61") = tylko miasto Poznań
KATEGORIE = "glowne"          # "glowne" = kategorie zagregowane (kategorie_glowne.py), "szczegolowe" = surowe mrch_catg_nm
TOP_KAT = 40                  # tylko dla "szczegolowe": tyle kategorii osobno; reszta trafia do "(pozostałe)"

# grupa analizy (wg zapytania SQL): indeks g = 0..3, ustalany z kraju wydawcy karty (issr_ctry_cd) i gminy karty (lau_enr)
GRUPY = ["Poznań", "Obwarzanek (okolice)", "Obcokrajowcy", "Poza metropolią"]
OBWARZANEK = ("BUK", "CZERWONAK", "DOPIEWO", "KLESZCZEWO", "KOMORNIKI", "KORNIK", "KOSTRZYN", "LUBON", "MOSINA",
              "MUROWANA GOSLINA", "POBIEDZISKA", "PUSZCZYKOWO", "ROKIETNICA", "STESZEW", "SUCHY LAS", "SWARZEDZ",
              "TARNOWO PODGORNE")
# pora dnia (wg zapytania SQL, godzina z tran_id_gmt_tm, czas GMT/UTC): indeks b = 0..1
PORY = ["Dzień (8–17)", "Wieczór/noc (18–7)"]
MIN_N = 1                     # ukryj komórki (dzień x kod x kategoria) z mniejszą liczbą transakcji (prywatność)
MEM = "4GB"                   # limit pamięci DuckDB

ap = argparse.ArgumentParser()
ap.add_argument("--dataset", choices=sorted(DATASETS), default=DATASET)   # mini albo full (pliki w folderze app)
ap.add_argument("--parquet")    # dowolna ścieżka do pliku parquet (ma pierwszeństwo przed --dataset)
ap.add_argument("--geojson")
ap.add_argument("--events")     # CSV z kolumnami data_od, data_do, nazwa (domyślnie duze_wydarzenia*.csv obok skryptu)
ap.add_argument("--osiedla")    # GeoJSON osiedli (domyślnie osiedla.json obok skryptu)
args = ap.parse_args()


def find(explicit, names, what):
    cands = [Path(explicit)] if explicit else [Path(n) for n in names]
    for p in cands:
        if p.exists():
            return p.resolve()
    sys.exit(f"Nie znaleziono {what}. Sprawdzono:\n  " + "\n  ".join(str(p.resolve()) for p in cands)
             + "\nPodaj ścieżkę przez --parquet / --geojson.")


parquet = find(args.parquet, [HERE / DATASETS[args.dataset]], "pliku parquet")
geojson = find(args.geojson, [HERE / "kody.json"], "pliku GeoJSON (kody pocztowe)")
print(f"Zbiór: {args.dataset if not args.parquet else 'własny'} | Parquet: {parquet} ({parquet.stat().st_size / 1e9:.2f} GB)")
print("GeoJSON:", geojson)


# środek każdego kodu pocztowego (przybliżenie: średnia współrzędnych największego wielokąta)
def centroid(feature):
    geom = feature["geometry"]
    polys = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]
    ring = max((p[0] for p in polys), key=len)
    lon = sum(c[0] for c in ring) / len(ring)
    lat = sum(c[1] for c in ring) / len(ring)
    return float(lat), float(lon)


# --- agregacja w DuckDB: dzień x kod x kategoria ---
prefix_sql = ""
if KOD_PREFIKSY:
    prefix_sql = " AND substr(k, 1, 2) IN (" + ", ".join(f"'{p}'" for p in KOD_PREFIKSY) + ")"

POSTAL_RE = r"^[0-9]{5}$"      # kod 5-cyfrowy (z myślnikiem lub bez), normalizowany do XX-XXX

con = duckdb.connect()
con.sql(f"SET memory_limit='{MEM}'")
con.sql("SET preserve_insertion_order=false")
con.sql("SET enable_progress_bar=true")

obw_sql = ", ".join("'" + n + "'" for n in OBWARZANEK)
kat_sql = case_sql("catg_u") if KATEGORIE == "glowne" else "COALESCE(NULLIF(trim(mrch_catg_nm), ''), '(brak kategorii)')"

df = con.sql(f"""
WITH p AS (
  SELECT CAST(prch_dt AS DATE) AS dt,
         replace(mrch_postal_code, '-', '') AS k,
         mrch_catg_nm,
         UPPER(TRIM(mrch_catg_nm)) AS catg_u,
         CAST(SUBSTR(LPAD(tran_id_gmt_tm, 6, '0'), 1, 2) AS INTEGER) AS hh,
         issr_ctry_cd,
         UPPER(TRIM(lau_enr)) AS lau_u,
         CAST(cs_tran_amt AS DOUBLE) AS amt
  FROM read_parquet('{parquet.as_posix()}')
  WHERE upper(mrch_ctry_nm) = 'POLAND'
),
q AS (
  SELECT dt,
         substr(k, 1, 2) || '-' || substr(k, 3, 3) AS kod,
         {kat_sql} AS kat,
         CASE WHEN issr_ctry_cd <> 616 THEN 2
              WHEN lau_u = 'POZNAN' THEN 0
              WHEN lau_u IN ({obw_sql}) THEN 1
              ELSE 3 END AS g,
         CASE WHEN hh BETWEEN 8 AND 17 THEN 0 ELSE 1 END AS b,
         amt
  FROM p
  WHERE regexp_matches(k, '{POSTAL_RE}'){prefix_sql}
)
SELECT dt, kod, kat, g, b, COUNT(*) AS n, SUM(amt) AS s
FROM q
GROUP BY ALL
HAVING COUNT(*) >= {MIN_N}
""").df()
print(f"Wiersze zagregowane (dzień x kod x kategoria x grupa x pora): {len(df):,}")

# --- dopasowanie do GeoJSON ---
geo = json.load(open(geojson, encoding="utf-8"))
centroids = {f["properties"]["NAZWA"]: centroid(f) for f in geo["features"]}


# promień "równoważnego koła" kodu w metrach: r = sqrt(powierzchnia / pi); powierzchnia z wielokąta (przybliżenie płaskie)
def radius_m(feature):
    geom = feature["geometry"]
    polys = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]
    area = 0.0
    for poly in polys:
        for i, ring in enumerate(poly):                       # pierwszy pierścień = obrys, kolejne = dziury
            lat0 = sum(p[1] for p in ring) / len(ring)
            kx = 111320.0 * math.cos(math.radians(lat0))
            ky = 110540.0
            s = 0.0
            for (x1, y1), (x2, y2) in zip(ring, ring[1:] + ring[:1]):
                s += (x1 * kx) * (y2 * ky) - (x2 * kx) * (y1 * ky)
            area += (abs(s) / 2.0) * (1 if i == 0 else -1)
    return int(round(math.sqrt(max(area, 1.0) / math.pi)))


radii = {f["properties"]["NAZWA"]: radius_m(f) for f in geo["features"]}
df = df[df["kod"].isin(centroids)].copy()
if df.empty:
    sys.exit("Brak wierszy po dopasowaniu kodów do GeoJSON (sprawdź KOD_PREFIKSY i format kodu XX-XXX).")

df["dt"] = pd.to_datetime(df["dt"])
kody = df.groupby("kod")["n"].sum().sort_values(ascending=False).index.tolist()
kod_idx = {k: i for i, k in enumerate(kody)}
df["c"] = df["kod"].map(kod_idx)

d0, d1 = df["dt"].min(), df["dt"].max()
dni = pd.date_range(d0, d1, freq="D")
df["d"] = (df["dt"] - d0).dt.days

df["f"] = df["g"] * 2 + df["b"]          # filtr: grupa analizy (0..3) x pora dnia (0..1) -> 0..7

if KATEGORIE == "glowne":
    df["kat2"] = df["kat"]                # kategorie główne z kategorie_glowne.py, "Inne" na końcu listy
    tail = INNE
else:
    lacznie = df.groupby("kat")["n"].sum().sort_values(ascending=False)
    top_names = lacznie.index[:TOP_KAT].tolist()
    df["kat2"] = df["kat"].where(df["kat"].isin(top_names), "(pozostałe)")
    tail = "(pozostałe)"
kat_sum = df.groupby("kat2")["n"].sum().sort_values(ascending=False)
kat_order = [k for k in kat_sum.index if k != tail] + ([tail] if tail in kat_sum.index else [])

OUT.mkdir(parents=True, exist_ok=True)
for old in OUT.glob("*.json"):
    old.unlink()


def dump(name, frame):
    g = frame.groupby(["d", "c", "f"], as_index=False)[["n", "s"]].sum().sort_values(["d", "c", "f"])
    payload = {"d": g["d"].astype(int).tolist(), "c": g["c"].astype(int).tolist(), "f": g["f"].astype(int).tolist(),
               "n": g["n"].astype(int).tolist(),
               "s": g["s"].round(0).astype(int).tolist()}      # s = suma kwot transakcji (zaokrąglona do jedności)
    p = OUT / name
    p.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    return p.stat().st_size


sizes = {"all.json": dump("all.json", df)}
cats = []
for i, name in enumerate(kat_order):
    fn = f"cat_{i}.json"
    sizes[fn] = dump(fn, df[df["kat2"] == name])
    cats.append({"name": name, "n": int(kat_sum[name]), "file": fn})

meta = {
    "days": [d.strftime("%Y-%m-%d") for d in dni],
    "codes": [{"k": k, "lat": round(centroids[k][0], 5), "lon": round(centroids[k][1], 5), "r": radii[k]} for k in kody],
    "cats": cats,
    "grupy": GRUPY,
    "pory": PORY,
    "total": int(df["n"].sum()),
}
(OUT / "meta.json").write_text(json.dumps(meta, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")

# --- wydarzenia (opcjonalnie): CSV z kolumnami data_od, data_do, nazwa -> docs/data/events.json ---
ev_candidates = [Path(args.events)] if args.events else sorted(HERE.glob("duze_wydarzenia*.csv"))
ev_file = next((p for p in ev_candidates if p.exists()), None)
if ev_file is None:
    print("Brak pliku z wydarzeniami (duze_wydarzenia*.csv obok skryptu), pomijam events.json")
else:
    ev = pd.read_csv(ev_file, sep=None, engine="python", encoding="utf-8-sig")
    ev["data_od"] = pd.to_datetime(ev["data_od"]).dt.strftime("%Y-%m-%d")
    ev["data_do"] = pd.to_datetime(ev["data_do"]).dt.strftime("%Y-%m-%d")
    ev = ev.sort_values(["data_od", "data_do", "nazwa"])
    (OUT / "events.json").write_text(
        json.dumps(ev[["data_od", "data_do", "nazwa"]].values.tolist(), separators=(",", ":"), ensure_ascii=False),
        encoding="utf-8")
    print(f"Wydarzenia: {len(ev)} z pliku {ev_file.name}")

# --- osiedla (opcjonalnie): geometria + udział każdego kodu pocztowego w każdym osiedlu ---
# W danych są tylko kody pocztowe, więc transakcje kodu dzielimy na osiedla proporcjonalnie do powierzchni
# części kodu leżącej w danym osiedlu (zakładamy równomierny rozkład transakcji w obrębie kodu: to przybliżenie).
os_candidates = [Path(args.osiedla)] if args.osiedla else [HERE / "osiedla.json"]
os_file = next((p for p in os_candidates if p.exists()), None)
if os_file is None:
    print("Brak pliku osiedla.json obok skryptu, pomijam osiedla")
else:
    try:
        from shapely.geometry import shape
        from shapely.strtree import STRtree
        from shapely.validation import make_valid
    except ImportError:
        sys.exit("Do obsługi osiedli potrzebna jest biblioteka shapely. Zainstaluj: conda install -y -c conda-forge shapely")

    def to_geom(feature):
        g = shape(feature["geometry"])
        return g if g.is_valid else make_valid(g)

    def rnd(coords):                                   # zaokrąglenie współrzędnych do 5 miejsc (mniejszy plik)
        if isinstance(coords[0], (int, float)):
            return [round(coords[0], 5), round(coords[1], 5)]
        return [rnd(c) for c in coords]

    og = json.load(open(os_file, encoding="utf-8"))
    o_feats = og["features"]
    o_shapes = [to_geom(f) for f in o_feats]
    code_shapes = {f["properties"]["NAZWA"]: to_geom(f) for f in geo["features"] if f["properties"]["NAZWA"] in kod_idx}

    tree = STRtree(o_shapes)
    weights = [[] for _ in o_shapes]
    for k, P in code_shapes.items():
        area = P.area
        if area <= 0:
            continue
        for j in tree.query(P):
            w = P.intersection(o_shapes[int(j)]).area / area
            if w >= 0.001:
                weights[int(j)].append([kod_idx[k], round(w, 4)])

    feats = [{"type": "Feature", "properties": {"i": i, "name": f["properties"].get("name", f"osiedle {i}")},
              "geometry": {"type": f["geometry"]["type"], "coordinates": rnd(f["geometry"]["coordinates"])}}
             for i, f in enumerate(o_feats)]
    (OUT / "osiedla.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": feats},
                                                     separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    (OUT / "osiedla_w.json").write_text(json.dumps(weights, separators=(",", ":")), encoding="utf-8")

    code_n = df.groupby("c")["n"].sum()
    covered = sum(float(w) * float(code_n.get(c, 0)) for ws in weights for c, w in ws)
    print(f"Osiedla: {len(feats)} z pliku {os_file.name} | transakcje przypisane do osiedli: {100 * covered / meta['total']:.1f}%")

total_mb = (sum(sizes.values()) + (OUT / "meta.json").stat().st_size) / 1e6
print(f"Dni: {len(dni)} | kody: {len(kody)} | kategorie: {len(cats)} | transakcje: {meta['total']:,}")
print(f"Zapisano do {OUT}: łącznie {total_mb:.1f} MB (największy plik: {max(sizes.values()) / 1e6:.1f} MB)")
if total_mb > 80:
    print("UWAGA: dużo danych na Pages. Zmniejsz TOP_KAT, zawęź KOD_PREFIKSY albo podnieś MIN_N.")
