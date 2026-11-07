from __future__ import annotations

import re
from typing import Any

import pandas as pd


def _normalizza_testo(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    text = str(value).strip().lower()
    text = text.replace("'", "")
    text = text.replace("-", "")
    text = text.replace(".", "")
    text = text.replace(" ", "")
    text = re.sub(r"[^a-z0-9]", "", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    return text


def _cf_valido(codice_fiscale: Any) -> bool:
    if codice_fiscale is None or pd.isna(codice_fiscale):
        return False
    cf = re.sub(r"[^A-Za-z0-9]", "", str(codice_fiscale)).upper()
    return len(cf) >= 11 and cf.isalnum()


def risolvi_identita(persone_raw: pd.DataFrame) -> pd.DataFrame:
    """Assegna un id_persona univoco con un union-find e regole deterministiche."""
    df = persone_raw.copy()
    if df.empty:
        df["id_persona"] = pd.Series(dtype=str)
        return df

    df["_norm_nome"] = df["nome"].fillna("").map(_normalizza_testo)
    df["_norm_cognome"] = df["cognome"].fillna("").map(_normalizza_testo)
    df["_telefono_norm"] = df["telefono"].fillna("").map(_normalizza_testo)
    df["_email_norm"] = df["email"].fillna("").map(_normalizza_testo)
    df["_cf_norm"] = df["codice_fiscale"].fillna("").map(lambda v: _normalizza_testo(v).upper())

    parent = {idx: idx for idx in range(len(df))}

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for idx in range(len(df)):
        row = df.iloc[idx]
        cf = row["_cf_norm"]
        if _cf_valido(cf):
            for jdx in range(idx + 1, len(df)):
                other = df.iloc[jdx]
                if _cf_valido(other["_cf_norm"]) and other["_cf_norm"] == cf:
                    union(idx, jdx)

    for idx in range(len(df)):
        row = df.iloc[idx]
        tel = row["_telefono_norm"]
        cognome = row["_norm_cognome"]
        if tel and cognome:
            for jdx in range(idx + 1, len(df)):
                other = df.iloc[jdx]
                if other["_telefono_norm"] == tel and other["_norm_cognome"] == cognome:
                    union(idx, jdx)

    for idx in range(len(df)):
        row = df.iloc[idx]
        email = row["_email_norm"]
        if email:
            for jdx in range(idx + 1, len(df)):
                other = df.iloc[jdx]
                if other["_email_norm"] == email:
                    union(idx, jdx)

    roots: dict[int, str] = {}
    for idx in range(len(df)):
        root = find(idx)
        if root not in roots:
            roots[root] = f"P{len(roots) + 1:06d}"
        df.loc[idx, "id_persona"] = roots[root]

    return df.drop(columns=["_norm_nome", "_norm_cognome", "_telefono_norm", "_email_norm", "_cf_norm"])
