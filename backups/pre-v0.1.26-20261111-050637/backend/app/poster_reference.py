"""Curated offline discovery facts for the ten requested chemical elements."""
from __future__ import annotations
import re
from typing import Any

ELEMENTS: dict[str, dict[str, Any]] = {
    "Cl": {"atomic_number":17,"name":"Chlorine","year":1774,"date":"1774 · first production","discoverer":"Carl Wilhelm Scheele · Uppsala, Sweden","institution":"Scheele’s laboratory and pharmacy, Uppsala","detail":"Scheele produced greenish-yellow chlorine by heating hydrochloric acid with pyrolusite. Humphry Davy later proved it was an element (1810).","classification":"HALOGEN · GROUP 17 · PERIOD 3","category":"halogen","visual":"chlorine_flask"},
    "I": {"atomic_number":53,"name":"Iodine","year":1811,"date":"1811 · first observed","discoverer":"Bernard Courtois · Paris, France","institution":"Courtois’s saltpetre works and laboratory, Paris","detail":"Courtois saw violet vapour while processing seaweed ash. Gay-Lussac later named the element after its violet colour.","classification":"HALOGEN · GROUP 17 · PERIOD 5","category":"halogen","visual":"iodine_crystals"},
    "Br": {"atomic_number":35,"name":"Bromine","year":1826,"date":"1826 · discovery published","discoverer":"Antoine-Jérôme Balard · Montpellier, France","institution":"University of Montpellier","detail":"Balard identified an orange-red liquid in brine residues. Carl Löwig had independently produced a sample in 1825.","classification":"HALOGEN · GROUP 17 · PERIOD 4","category":"halogen","visual":"bromine_vial"},
    "He": {"atomic_number":2,"name":"Helium","year":1868,"date":"1868 · solar detection","discoverer":"Pierre Janssen (India) & Norman Lockyer (England)","institution":"Independent solar-spectroscopy observations; Janssen at Guntur and Lockyer in England","detail":"Janssen and Lockyer independently detected a new yellow line in the Sun’s spectrum. Helium was isolated on Earth in 1895.","classification":"NOBLE GAS · GROUP 18 · PERIOD 1","category":"noble_gas","visual":"helium_spectrum"},
    "Yb": {"atomic_number":70,"name":"Ytterbium","year":1878,"date":"1878 · isolated as an oxide","discoverer":"Jean Charles Galissard de Marignac · Geneva, Switzerland","institution":"University of Geneva chemical laboratory","detail":"De Marignac separated a new oxide from erbium. The material still contained lutetium, which was separated in 1907.","classification":"LANTHANOID · f-BLOCK · PERIOD 6","category":"lanthanoid","visual":"ytterbium_ore"},
    "F": {"atomic_number":9,"name":"Fluorine","year":1886,"date":"1886 · first isolation","discoverer":"Henri Moissan · Paris, France","institution":"École supérieure de pharmacie de Paris","detail":"Moissan isolated F₂ by electrolysing potassium bifluoride in liquid hydrogen fluoride after decades of dangerous failed attempts.","classification":"HALOGEN · GROUP 17 · PERIOD 2","category":"halogen","visual":"fluorine_cell"},
    "At": {"atomic_number":85,"name":"Astatine","year":1940,"date":"1940 · first synthesis","discoverer":"Dale R. Corson, Kenneth R. MacKenzie & Emilio Segrè · Berkeley, USA","institution":"University of California, Berkeley Radiation Laboratory","detail":"Bombarding bismuth with alpha particles produced this extremely radioactive element. Only tiny quantities can be made.","classification":"HALOGEN · GROUP 17 · PERIOD 6","category":"halogen","visual":"astatine_nucleus"},
    "Md": {"atomic_number":101,"name":"Mendelevium","year":1955,"date":"1955 · first synthesis","discoverer":"Albert Ghiorso, Glenn Seaborg & Berkeley team · Berkeley, USA","institution":"University of California Radiation Laboratory; 60-inch cyclotron","detail":"Seventeen atoms were made by bombarding einsteinium-253 with alpha particles. Recoil separation enabled atom-at-a-time identification.","classification":"ACTINOID · f-BLOCK · PERIOD 7","category":"actinoid","visual":"mendelevium_cyclotron"},
    "No": {"atomic_number":102,"name":"Nobelium","year":1965,"date":"1965 · conclusive synthesis","discoverer":"Joint Institute for Nuclear Research team · Dubna, USSR","institution":"Joint Institute for Nuclear Research (JINR), Dubna","detail":"After disputed 1957–58 claims, Dubna achieved a conclusive synthesis in 1965. The early Swedish claim was later shown to be incorrect.","classification":"ACTINOID · f-BLOCK · PERIOD 7","category":"actinoid","visual":"nobelium_accelerator"},
    "Ts": {"atomic_number":117,"name":"Tennessine","year":2009,"date":"2009–2010 · synthesis reported","discoverer":"JINR Dubna · Lawrence Livermore · Oak Ridge collaboration","institution":"JINR U-400 cyclotron; Oak Ridge and Lawrence Livermore national laboratories","detail":"Calcium-48 ions were fused with berkelium-249. IUPAC confirmed the discovery in 2015 and approved the name in 2016.","classification":"HALOGEN · GROUP 17 · PERIOD 7","category":"halogen","visual":"tennessine_collision"},
}


def extract_explicit_element_symbols(prompt: str) -> list[str]:
    """Extract an explicit list such as ``Md (Mendelevium), F, ...``.

    The list may be embedded in a long assignment brief. Stop at the first
    sentence boundary after the list so trailing requirements are not treated
    as additional element tokens.
    """
    text = str(prompt or "")
    matches = list(re.finditer(r"\b(?:elements|symbols)\s*:\s*", text, re.IGNORECASE))
    if not matches:
        return []
    raw = text[matches[-1].end():]
    raw = re.split(r"[\r\n]", raw, maxsplit=1)[0]
    sentence_end = re.search(r"(?<=[A-Za-z0-9)])\.(?=\s|$)", raw)
    if sentence_end:
        raw = raw[:sentence_end.start()]
    raw_tokens = re.split(r",|;|/|\band\b", raw, flags=re.IGNORECASE)
    symbols: list[str] = []
    for raw_token in raw_tokens:
        cleaned = raw_token.strip().strip(" .:[]{}\t\"")
        token_match = re.fullmatch(r"([A-Z][a-z]?)(?:\s*\([^)]*\))?", cleaned)
        token = token_match.group(1) if token_match else cleaned
        if token in ELEMENTS and token not in symbols:
            symbols.append(token)
    return symbols


def build_element_discovery_poster(prompt: str) -> dict[str, Any] | None:
    symbols = extract_explicit_element_symbols(prompt)
    if len(symbols) < 2:
        return None
    items = [{**ELEMENTS[symbol], "label": symbol, "title": ELEMENTS[symbol]["name"]} for symbol in symbols]
    items.sort(key=lambda item: (int(item["year"]), int(item["atomic_number"])))
    categories = ("halogen", "noble_gas", "lanthanoid", "actinoid")
    labels = {"halogen":"GROUP 17 · HALOGENS","noble_gas":"GROUP 18 · NOBLE GAS","lanthanoid":"LANTHANOIDS · f-BLOCK","actinoid":"ACTINOIDS · f-BLOCK"}
    chips = [{"category": cat, "label": labels[cat], "count": sum(x["category"] == cat for x in items)} for cat in categories if any(x["category"] == cat for x in items)]
    return {
        "layout":"element_discovery",
        "title":"ELEMENT DISCOVERY & PERIODIC-TABLE ORGANIZATION",
        "subtitle":f"{len(items)} selected elements · from {items[0]['date'].split('·')[0].strip()} to {items[-1]['date'].split('·')[0].strip()}",
        "intro":"Element discovery transformed chemistry: from identifying substances in minerals and gases to detecting atoms made in laboratories.",
        "items":items,
        "category_chips":chips,
        "key_takeaways":["Evidence matters: first observation, isolation, synthesis and official recognition can occur in different years."],
        "footer":"Discovery advanced from chemical isolation and solar spectroscopy to accelerator-made nuclei through international collaboration.",
        "sources":"Sources: Royal Society of Chemistry element histories · ACS Transuranium Elements at Berkeley Lab · IUPAC discovery and naming reports.",
    }
