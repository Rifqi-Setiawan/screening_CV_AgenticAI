from src.domain.text_match import match_skill


def test_match_skill_word_boundary_false_positives():
    # "java" must NOT match "JavaScript"
    assert not match_skill("Saya menguasai JavaScript", "java")
    assert not match_skill("Senior JavaScript Developer", "java")


def test_match_skill_negation_detection():
    # Negation words before skill keyword must return False
    assert not match_skill("Tidak menguasai Python", "python")
    assert not match_skill("Belum pernah menggunakan Docker", "docker")
    assert not match_skill("Bukan developer Java", "java")
    assert not match_skill("No experience with Kubernetes", "kubernetes")


def test_match_skill_positive_matches():
    assert match_skill("Berpengalaman dengan Python dan FastAPI", "python")
    assert match_skill("Solid understanding of PostgreSQL and SQL queries", "sql")
    assert match_skill("Menguasai Java Spring Boot", "java")


def test_match_skill_sql_vs_sqlite():
    # SQLite should not trigger generic enterprise SQL requirement
    assert not match_skill("Menggunakan SQLite untuk local cache", "sql")
    assert match_skill("Menggunakan PostgreSQL dan SQL query", "sql")
