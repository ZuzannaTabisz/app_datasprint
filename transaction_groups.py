"""Classification of cardholders by issuer country and municipality."""

GRUPY = ["Poznań", "Obwarzanek (okolice)", "Obcokrajowcy", "Poza metropolią", "Brak danych gminy"]

OBWARZANEK = (
    "BUK", "CZERWONAK", "DOPIEWO", "KLESZCZEWO", "KOMORNIKI", "KORNIK", "KOSTRZYN", "LUBON", "MOSINA",
    "MUROWANA GOSLINA", "POBIEDZISKA", "PUSZCZYKOWO", "ROKIETNICA", "STESZEW", "SUCHY LAS", "SWARZEDZ",
    "TARNOWO PODGORNE",
)


def group_sql(issuer_country_col, municipality_col):
    obwarzanek = ", ".join("'" + name.replace("'", "''") + "'" for name in OBWARZANEK)
    return (
        f"CASE WHEN {issuer_country_col} <> 616 THEN 2 "
        f"WHEN {municipality_col} IS NULL OR TRIM({municipality_col}) = '' THEN 4 "
        f"WHEN UPPER(TRIM({municipality_col})) = 'POZNAN' THEN 0 "
        f"WHEN UPPER(TRIM({municipality_col})) IN ({obwarzanek}) THEN 1 "
        "ELSE 3 END"
    )