import pytest

from apply_pipeline.adapters.llm.evidence import check_answers, normalize_for_search
from apply_pipeline.adapters.llm.schemas import CriterionAnswer
from apply_pipeline.domain.criteria import CriterionResult, CriterionStatus

MET = CriterionStatus.MET
NOT_MET = CriterionStatus.NOT_MET
UNKNOWN = CriterionStatus.UNKNOWN

VACANCY = """Position: Junior Python Developer
Company: Acme

Шукаємо Junior Python розробника.
Робота лише з офісу
у Києві. Досвід від 1 року."""

IDS = {"python", "office", "crypto"}


def _answer(criterion_id: str, status: CriterionStatus, evidence: str | None) -> CriterionAnswer:
    return CriterionAnswer(criterion_id=criterion_id, status=status, evidence=evidence)


def _check(*answers: CriterionAnswer) -> tuple[tuple[CriterionResult, ...], int]:
    checked = check_answers(answers, criterion_ids=IDS, vacancy_text=VACANCY)
    return checked.results, checked.discarded


def test_normalize_collapses_whitespace_and_case() -> None:
    assert normalize_for_search("  Робота\n лише\tз   ОФІСУ ") == "робота лише з офісу"


def test_normalize_uses_casefold() -> None:
    assert normalize_for_search("STRASSE") == normalize_for_search("straße")


def test_exact_quote_is_kept() -> None:
    results, discarded = _check(_answer("python", MET, "Junior Python розробника"))

    assert results == (CriterionResult("python", MET, "Junior Python розробника"),)
    assert discarded == 0


def test_not_met_with_real_quote_is_kept() -> None:
    results, _ = _check(_answer("office", NOT_MET, "Робота лише з офісу"))

    assert results[0].status is NOT_MET


def test_quote_across_line_break_and_case_is_found() -> None:
    results, discarded = _check(_answer("office", MET, "робота лише з ОФІСУ у Києві"))

    assert results[0].status is MET
    # The user sees the quote as the model gave it, not the normalized search form.
    assert results[0].evidence == "робота лише з ОФІСУ у Києві"
    assert discarded == 0


@pytest.mark.parametrize(
    "wrapped",
    ['"Досвід від 1 року"', "«Досвід від 1 року»", "„Досвід від 1 року“", "“Досвід від 1 року”"],
    ids=["straight", "guillemets", "german", "english"],
)
def test_surrounding_quotes_are_removed(wrapped: str) -> None:
    results, discarded = _check(_answer("python", MET, wrapped))

    assert results[0].evidence == "Досвід від 1 року"
    assert discarded == 0


def test_invented_quote_becomes_unknown() -> None:
    results, discarded = _check(_answer("python", MET, "Remote work from anywhere"))

    assert results == (CriterionResult("python", UNKNOWN),)
    assert discarded == 1


def test_paraphrased_quote_becomes_unknown() -> None:
    results, discarded = _check(_answer("office", MET, "Робота тільки з офісу у Києві"))

    assert results[0].status is UNKNOWN
    assert discarded == 1


@pytest.mark.parametrize(
    "evidence", [None, "", "   ", '""'], ids=["none", "empty", "blank", "quotes"]
)
def test_decision_without_quote_becomes_unknown(evidence: str | None) -> None:
    results, discarded = _check(_answer("python", MET, evidence))

    assert results[0].status is UNKNOWN
    assert discarded == 1


def test_unknown_drops_quote_without_penalty() -> None:
    results, discarded = _check(_answer("crypto", UNKNOWN, "Junior Python розробника"))

    assert results == (CriterionResult("crypto", UNKNOWN),)
    assert discarded == 0


def test_unknown_criterion_id_is_discarded() -> None:
    results, discarded = _check(
        _answer("kotlin", MET, "Junior Python розробника"),
        _answer("python", MET, "Junior Python розробника"),
    )

    assert [result.criterion_id for result in results] == ["python"]
    assert discarded == 1


def test_first_answer_wins_on_duplicates() -> None:
    results, discarded = _check(
        _answer("python", MET, "Junior Python розробника"),
        _answer("python", NOT_MET, "Досвід від 1 року"),
    )

    assert results == (CriterionResult("python", MET, "Junior Python розробника"),)
    assert discarded == 1


def test_missing_answers_are_not_invented() -> None:
    results, discarded = _check(_answer("python", MET, "Junior Python розробника"))

    # score_match treats the silent criteria as unknown; the check adds nothing.
    assert len(results) == 1
    assert discarded == 0


def test_order_follows_the_model() -> None:
    results, _ = _check(
        _answer("crypto", UNKNOWN, None),
        _answer("python", MET, "Junior Python розробника"),
    )

    assert [result.criterion_id for result in results] == ["crypto", "python"]
