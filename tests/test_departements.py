from backend.departements import DEPARTEMENTS, postcode_to_departement


def test_postcode_charente_maritime():
    # Diagnostic session : vérifie que La Rochelle (17000) est bien rattachée
    # au département 17, pas un bug de mapping.
    assert postcode_to_departement("17000") == "17"
    assert DEPARTEMENTS["17"] == "Charente-Maritime"


def test_postcode_known_codes():
    assert postcode_to_departement("33000") == "33"   # Bordeaux -> Gironde
    assert postcode_to_departement("24000") == "24"   # Périgueux -> Dordogne
    assert postcode_to_departement("75002") == "75"   # Paris
    assert postcode_to_departement("20090") == "20"   # Corse (groupée)


def test_postcode_dom_tom_not_mapped():
    # Hors scope métropole (décision validée en session précédente).
    assert postcode_to_departement("97400") is None


def test_postcode_invalid():
    assert postcode_to_departement(None) is None
    assert postcode_to_departement("") is None
    assert postcode_to_departement("abcde") is None
    assert postcode_to_departement("1234") is None
