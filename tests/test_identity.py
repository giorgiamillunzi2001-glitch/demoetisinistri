import pandas as pd

from retisinistri.identity import risolvi_identita


def test_risolvi_identita_unisce_cf_e_telefono_senza_unire_solo_cognome():
    df = pd.DataFrame([
        {"nome": "Luca", "cognome": "Ferrara", "codice_fiscale": "FRRLCU80A01F205X", "telefono": "3331234567", "email": "luca1@example.it"},
        {"nome": "L. Ferrara", "cognome": "Ferrara", "codice_fiscale": "FRRLCU80A01F205X", "telefono": "3339876543", "email": "luca2@example.it"},
        {"nome": "Marco", "cognome": "Rossi", "codice_fiscale": "RSSMRC80A01F205Y", "telefono": "3331234567", "email": "marco@example.it"},
        {"nome": "Paola", "cognome": "Rossi", "codice_fiscale": None, "telefono": "3334445555", "email": "paola@example.it"},
        {"nome": "Paola", "cognome": "Rossi", "codice_fiscale": None, "telefono": "3334445555", "email": "paola2@example.it"},
    ])
    out = risolvi_identita(df)
    first = out.iloc[0]["id_persona"]
    second = out.iloc[1]["id_persona"]
    third = out.iloc[2]["id_persona"]
    fourth = out.iloc[3]["id_persona"]
    fifth = out.iloc[4]["id_persona"]
    assert first == second
    assert fourth == fifth
    assert third != first
