from src.worker.adapter import parse_experiences


def test_parse_experiences_without_separator():
    text = """Data Analyst
Jan 2022 – Present
- Membuat dashboard"""

    exps = parse_experiences(text, text)
    assert len(exps) == 1
    assert exps[0]["title"] == "Data Analyst"
    assert exps[0]["start"]["value"] == "2022-01"
    assert exps[0]["end"]["value"] == "present"
