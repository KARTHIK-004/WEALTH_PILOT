"""Phase 2 completion criterion: quality report generation is covered by a
test on a fixture subset — small, controlled CSVs with known nulls,
duplicates and label values, so the assertions check exact expected numbers
rather than whatever happens to be in the real dataset today.
"""

import wealthpilot.data.quality as quality


FAR_TRANS_FIXTURE_CUSTOMERS = """customerID,customerType,riskLevel,investmentCapacity,lastQuestionnaireDate,timestamp
C1,Mass,Conservative,CAP_LT30K,2020-01-01,2020-01-01
C1,Mass,Balanced,CAP_LT30K,2021-06-01,2021-06-01
C2,Premium,Predicted_Balanced,CAP_30K_80K,2019-05-01,2019-05-01
C3,Mass,Not_Available,,2018-02-01,2018-02-01
"""

FAR_TRANS_FIXTURE_TRANSACTIONS = """customerID,ISIN,transactionID,transactionType,timestamp,totalValue,units,channel,marketID
C1,ISIN1,T1,Buy,2020-01-02,100.0,10.0,Internet Banking,M1
C1,ISIN1,T1,Buy,2020-01-02,100.0,10.0,Internet Banking,M1
C2,ISIN1,T2,Sell,2020-02-02,50.0,5.0,Branch,M1
"""


def _write_far_trans_fixture(tmp_path, monkeypatch):
    far_trans_dir = tmp_path / "FAR-Trans"
    far_trans_dir.mkdir()
    (far_trans_dir / "customer_information.csv").write_text(FAR_TRANS_FIXTURE_CUSTOMERS, encoding="utf-8")
    (far_trans_dir / "transactions.csv").write_text(FAR_TRANS_FIXTURE_TRANSACTIONS, encoding="utf-8")
    monkeypatch.setattr(quality, "FAR_TRANS_DIR", far_trans_dir)
    return far_trans_dir


def test_customer_information_quality_on_fixture(tmp_path, monkeypatch):
    _write_far_trans_fixture(tmp_path, monkeypatch)

    report = quality.check_customer_information()

    assert report.row_count == 4
    assert report.extra["unique_customer_count"] == 3
    assert report.extra["risk_level_distribution"] == {
        "Conservative": 1,
        "Balanced": 1,
        "Predicted_Balanced": 1,
        "Not_Available": 1,
    }
    assert report.extra["genuine_label_row_count"] == 2
    # Both genuine rows (Conservative, Balanced) belong to C1 alone.
    assert report.extra["genuine_label_customer_count"] == 1
    assert report.null_counts["investmentCapacity"] == 1


def test_transactions_quality_on_fixture_detects_duplicate_transaction_id(tmp_path, monkeypatch):
    _write_far_trans_fixture(tmp_path, monkeypatch)

    report = quality.check_transactions()

    assert report.row_count == 3
    assert report.extra["unique_transaction_id_count"] == 2
    # T1 appears twice as an EXACT duplicate row here (unlike the real data's
    # joint-account pattern), so both the full-row-duplicate count and the
    # transactionID-repeat note should reflect that.
    assert report.duplicate_full_rows == 1
    assert any("transactionID is not a unique row key" in note for note in report.notes)


def test_questionnaires_quality_on_fixture_confirms_not_csv(tmp_path, monkeypatch):
    far_trans_dir = tmp_path / "FAR-Trans"
    far_trans_dir.mkdir()
    (far_trans_dir / "questionnaires.csv").write_text(
        "Section 1\n\n\t1. Question one?\n\t\ta. Yes\n\t\tb. No\n\n\t2. Question two?\n\t\ta. Yes\n\t\tb. No\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(quality, "FAR_TRANS_DIR", far_trans_dir)

    report = quality.check_questionnaires()

    assert report.extra["question_count"] == 2
    assert any("NOT a CSV file" in note for note in report.notes)


def test_kaggle_file_quality_on_fixture(tmp_path, monkeypatch):
    kaggle_dir = tmp_path / "kaggle"
    kaggle_dir.mkdir()
    (kaggle_dir / "sample.csv").write_text(
        "user_id,monthly_income_usd\nU1,1000\nU2,2000\nU1,1000\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(quality, "KAGGLE_DIR", kaggle_dir)

    report = quality.check_kaggle_file("sample.csv")

    assert report.row_count == 3
    assert report.extra["unique_user_id_count"] == 2
    assert report.duplicate_full_rows == 1
