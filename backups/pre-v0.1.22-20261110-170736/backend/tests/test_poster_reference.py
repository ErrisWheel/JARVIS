from app.poster_reference import build_element_discovery_poster, extract_explicit_element_symbols


def test_explicit_element_list_is_parsed_exactly():
    prompt = (
        "Create a chronological timeline of discovery and organization of these elements: "
        "Md, F, Cl, Br, I, At, Ts, Yb, No, He"
    )
    assert extract_explicit_element_symbols(prompt) == ["Md", "F", "Cl", "Br", "I", "At", "Ts", "Yb", "No", "He"]


def test_element_discovery_poster_is_detailed_and_chronologically_sorted():
    prompt = "Create a chronological timeline of discovery and organization of these elements: Md, F, Cl, Br, I, At, Ts, Yb, No, He"
    data = build_element_discovery_poster(prompt)

    assert data is not None
    assert data["layout"] == "element_discovery"
    assert [item["label"] for item in data["items"]] == ["Cl", "I", "Br", "He", "Yb", "F", "At", "Md", "No", "Ts"]
    assert len(data["items"]) == 10
    for item in data["items"]:
        assert item["atomic_number"] > 0
        assert item["date"].strip()
        assert item["discoverer"].strip()
        assert item["detail"].strip()
        assert item["classification"].strip()
        assert item["visual"].strip()


def test_discovery_poster_has_periodic_table_category_counts():
    prompt = "Make a poster about these elements: Md, F, Cl, Br, I, At, Ts, Yb, No, He"
    data = build_element_discovery_poster(prompt)
    assert data is not None
    counts = {item["category"]: item["count"] for item in data["category_chips"]}
    assert counts == {"halogen": 6, "noble_gas": 1, "lanthanoid": 1, "actinoid": 2}


def test_unstructured_generic_prompt_does_not_trigger_element_reference():
    assert build_element_discovery_poster("Create a poster about photosynthesis.") is None



def test_full_assignment_brief_extracts_parenthetical_element_names_without_trailing_requirements():
    prompt = (
        "Create a highly detailed academic poster about the following chemical elements: "
        "Md (Mendelevium), F (Fluorine), Cl (Chlorine), Br (Bromine), I (Iodine), "
        "At (Astatine), Ts (Tennessine), Yb (Ytterbium), No (Nobelium), and He (Helium). "
        "Required Content: add discovery dates, institutions, descriptions, visual diagrams and references."
    )
    assert extract_explicit_element_symbols(prompt) == ["Md", "F", "Cl", "Br", "I", "At", "Ts", "Yb", "No", "He"]
    data = build_element_discovery_poster(prompt)
    assert data is not None
    assert [item["label"] for item in data["items"]] == ["Cl", "I", "Br", "He", "Yb", "F", "At", "Md", "No", "Ts"]
