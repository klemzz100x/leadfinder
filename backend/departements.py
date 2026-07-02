"""Mapping code postal -> département (France métropolitaine).

Règle : les 2 premiers chiffres du code postal = code département, sauf la
Corse qui est regroupée en un seul groupe "20" (pas de distinction 2A/2B).
Les DOM-TOM (codes postaux 97xxx/98xxx) ne sont volontairement pas mappés :
`postcode_to_departement` renvoie None pour ces cas (hors scope métropole).

Les centroïdes sont approximés par les coordonnées de la préfecture de
chaque département — suffisant pour positionner une bulle sur la carte
(Phase 4), pas pour un usage cartographique précis.
"""

from __future__ import annotations

from typing import Optional

DEPARTEMENTS: dict[str, str] = {
    "01": "Ain", "02": "Aisne", "03": "Allier", "04": "Alpes-de-Haute-Provence",
    "05": "Hautes-Alpes", "06": "Alpes-Maritimes", "07": "Ardèche", "08": "Ardennes",
    "09": "Ariège", "10": "Aube", "11": "Aude", "12": "Aveyron",
    "13": "Bouches-du-Rhône", "14": "Calvados", "15": "Cantal", "16": "Charente",
    "17": "Charente-Maritime", "18": "Cher", "19": "Corrèze", "20": "Corse",
    "21": "Côte-d'Or", "22": "Côtes-d'Armor", "23": "Creuse", "24": "Dordogne",
    "25": "Doubs", "26": "Drôme", "27": "Eure", "28": "Eure-et-Loir",
    "29": "Finistère", "30": "Gard", "31": "Haute-Garonne", "32": "Gers",
    "33": "Gironde", "34": "Hérault", "35": "Ille-et-Vilaine", "36": "Indre",
    "37": "Indre-et-Loire", "38": "Isère", "39": "Jura", "40": "Landes",
    "41": "Loir-et-Cher", "42": "Loire", "43": "Haute-Loire", "44": "Loire-Atlantique",
    "45": "Loiret", "46": "Lot", "47": "Lot-et-Garonne", "48": "Lozère",
    "49": "Maine-et-Loire", "50": "Manche", "51": "Marne", "52": "Haute-Marne",
    "53": "Mayenne", "54": "Meurthe-et-Moselle", "55": "Meuse", "56": "Morbihan",
    "57": "Moselle", "58": "Nièvre", "59": "Nord", "60": "Oise",
    "61": "Orne", "62": "Pas-de-Calais", "63": "Puy-de-Dôme", "64": "Pyrénées-Atlantiques",
    "65": "Hautes-Pyrénées", "66": "Pyrénées-Orientales", "67": "Bas-Rhin", "68": "Haut-Rhin",
    "69": "Rhône", "70": "Haute-Saône", "71": "Saône-et-Loire", "72": "Sarthe",
    "73": "Savoie", "74": "Haute-Savoie", "75": "Paris", "76": "Seine-Maritime",
    "77": "Seine-et-Marne", "78": "Yvelines", "79": "Deux-Sèvres", "80": "Somme",
    "81": "Tarn", "82": "Tarn-et-Garonne", "83": "Var", "84": "Vaucluse",
    "85": "Vendée", "86": "Vienne", "87": "Haute-Vienne", "88": "Vosges",
    "89": "Yonne", "90": "Territoire de Belfort", "91": "Essonne", "92": "Hauts-de-Seine",
    "93": "Seine-Saint-Denis", "94": "Val-de-Marne", "95": "Val-d'Oise",
}

# (lat, lng) — approximation par la préfecture de chaque département.
DEPARTEMENT_CENTROIDS: dict[str, tuple[float, float]] = {
    "01": (46.2058, 5.2265), "02": (49.5642, 3.6203), "03": (46.5658, 3.3350),
    "04": (44.0925, 6.2358), "05": (44.5594, 6.0790), "06": (43.7102, 7.2620),
    "07": (44.7355, 4.5994), "08": (49.7736, 4.7160), "09": (42.9647, 1.6053),
    "10": (48.2973, 4.0744), "11": (43.2130, 2.3491), "12": (44.3506, 2.5754),
    "13": (43.2965, 5.3698), "14": (49.1829, -0.3707), "15": (44.9328, 2.4444),
    "16": (45.6484, 0.1560), "17": (46.1603, -1.1511), "18": (47.0810, 2.3988),
    "19": (45.2648, 1.7715), "20": (42.1500, 9.1000), "21": (47.3220, 5.0415),
    "22": (48.5142, -2.7652), "23": (46.1701, 1.8683), "24": (45.1848, 0.7218),
    "25": (47.2380, 6.0243), "26": (44.9334, 4.8924), "27": (49.0242, 1.1508),
    "28": (48.4470, 1.4893), "29": (47.9960, -4.0977), "30": (43.8367, 4.3601),
    "31": (43.6047, 1.4442), "32": (43.6455, 0.5854), "33": (44.8378, -0.5792),
    "34": (43.6108, 3.8767), "35": (48.1173, -1.6778), "36": (46.8106, 1.6960),
    "37": (47.3941, 0.6848), "38": (45.1885, 5.7245), "39": (46.6739, 5.5551),
    "40": (43.8907, -0.4980), "41": (47.5861, 1.3359), "42": (45.4397, 4.3872),
    "43": (45.0430, 3.8850), "44": (47.2184, -1.5536), "45": (47.9029, 1.9093),
    "46": (44.4478, 1.4409), "47": (44.2029, 0.6199), "48": (44.5178, 3.5006),
    "49": (47.4784, -0.5632), "50": (49.1147, -1.0899), "51": (48.9573, 4.3634),
    "52": (48.1114, 5.1391), "53": (48.0698, -0.7700), "54": (48.6921, 6.1844),
    "55": (48.7706, 5.1613), "56": (47.6582, -2.7603), "57": (49.1193, 6.1757),
    "58": (46.9896, 3.1610), "59": (50.6292, 3.0573), "60": (49.4295, 2.0807),
    "61": (48.4322, 0.0913), "62": (50.2910, 2.7776), "63": (45.7772, 3.0870),
    "64": (43.2951, -0.3708), "65": (43.2327, 0.0781), "66": (42.6886, 2.8948),
    "67": (48.5734, 7.7521), "68": (48.0794, 7.3585), "69": (45.7640, 4.8357),
    "70": (47.6236, 6.1546), "71": (46.3069, 4.8281), "72": (48.0061, 0.1996),
    "73": (45.5646, 5.9178), "74": (45.8992, 6.1294), "75": (48.8566, 2.3522),
    "76": (49.4431, 1.0993), "77": (48.5388, 2.6600), "78": (48.8014, 2.1301),
    "79": (46.3237, -0.4590), "80": (49.8942, 2.2957), "81": (43.9298, 2.1480),
    "82": (44.0181, 1.3536), "83": (43.1242, 5.9280), "84": (43.9493, 4.8055),
    "85": (46.6705, -1.4269), "86": (46.5802, 0.3404), "87": (45.8336, 1.2611),
    "88": (48.1740, 6.4494), "89": (47.7982, 3.5731), "90": (47.6379, 6.8629),
    "91": (48.6299, 2.4406), "92": (48.8924, 2.2153), "93": (48.9091, 2.4392),
    "94": (48.7904, 2.4553), "95": (49.0364, 2.0770),
}


def postcode_to_departement(postcode: Optional[str]) -> Optional[str]:
    """Code département à partir d'un code postal à 5 chiffres, ou None.

    Renvoie None pour les DOM-TOM (97xxx/98xxx, hors scope métropole) et
    pour tout code postal invalide/absent.
    """
    if not postcode:
        return None
    postcode = postcode.strip()
    if len(postcode) != 5 or not postcode.isdigit():
        return None
    code = postcode[:2]
    return code if code in DEPARTEMENTS else None
