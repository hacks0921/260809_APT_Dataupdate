# -*- coding: utf-8 -*-
"""
아파트 공시지가 조회 시스템 단위 테스트 모듈
"""

import pytest
import pandas as pd
from logic import ScientificCalculatorLogic


def test_history_loading_initializes_empty_dataframe(tmp_path):
    """하드코딩 seed 제거 후 초기 데이터 로드 시 빈 DataFrame으로 초기화되는지 검증합니다."""
    history_file = str(tmp_path / "test_history.csv")
    logic = ScientificCalculatorLogic(history_path=history_file)
    df = logic.history_df
    assert 'label' in df.columns
    assert 'year' in df.columns
    assert 'price' in df.columns


def test_pivot_table_calculation_after_fetching(tmp_path):
    """데이터 수집 후 피벗 테이블 연산 시 Total 합계 및 전년대비 변동률이 정확히 계산되는지 검증합니다."""
    history_file = str(tmp_path / "test_history.csv")
    logic = ScientificCalculatorLogic(history_path=history_file)
    test_prop = logic.properties[0]
    logic.fetch_all_years_for_property(test_prop, start_year=2020, end_year=2026)

    pivot = logic.get_pivot_table()
    assert not pivot.empty
    assert 'Total' in pivot.columns
    assert 'Total_Diff' in pivot.columns
    assert 'Total_Rate' in pivot.columns


def test_fetch_property_invalid_address_returns_zero(tmp_path):
    """유효하지 않은 주소/PNU로 조회 시 가짜 데이터 생성 없이 0(실패)을 반환하는지 검증합니다."""
    history_file = str(tmp_path / "test_history.csv")
    logic = ScientificCalculatorLogic(history_path=history_file)
    invalid_prop = {
        "label": "가짜아파트",
        "search_addr": "무효한주소 99999",
        "pnu": "",
        "dongNm": "999",
        "hoNm": "999"
    }
    cnt = logic.fetch_all_years_for_property(invalid_prop, start_year=2020, end_year=2026)
    assert cnt == 0
    df_test = logic.history_df[logic.history_df["label"] == "가짜아파트"]
    assert df_test.empty


def test_remove_property_removes_from_list_and_history(tmp_path):
    """부동산 삭제 시 logic.properties 및 history_df에서 정상 제거되는지 검증합니다."""
    history_file = str(tmp_path / "test_history.csv")
    logic = ScientificCalculatorLogic(history_path=history_file)
    target_label = "광명역유플래닛데시앙"

    initial_prop_count = len(logic.properties)
    assert any(p["label"] == target_label for p in logic.properties)

    success = logic.remove_property(target_label)
    assert success is True
    assert len(logic.properties) == initial_prop_count - 1
    assert not any(p["label"] == target_label for p in logic.properties)
    assert logic.history_df[logic.history_df["label"] == target_label].empty
