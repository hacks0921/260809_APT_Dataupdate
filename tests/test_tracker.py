# -*- coding: utf-8 -*-
"""
아파트 공시지가 조회 시스템 단위 테스트 모듈
"""

import pytest
import pandas as pd
from app_gui import ScientificCalculatorLogic


def test_history_loading_existing_file_returns_dataframe():
    """기본 데이터 로드 시 2020년~2026년 공시가격 데이터가 로드되는지 검증합니다."""
    logic = ScientificCalculatorLogic()
    df = logic.history_df
    assert not df.empty
    assert 'label' in df.columns
    assert 'year' in df.columns
    assert 'price' in df.columns


def test_pivot_table_calculation_returns_total_and_rates():
    """피벗 테이블 연산 시 Total 합계 및 전년대비 변동률이 정확히 계산되는지 검증합니다."""
    logic = ScientificCalculatorLogic()
    pivot = logic.get_pivot_table()
    assert not pivot.empty
    assert 'Total' in pivot.columns
    assert 'Total_Diff' in pivot.columns
    assert 'Total_Rate' in pivot.columns


def test_fetch_property_custom_addition_creates_seven_years_data():
    """신규 아파트 추가 시 2020년부터 2026년까지 7개 연도 데이터가 정상 생성되는지 검증합니다."""
    logic = ScientificCalculatorLogic()
    test_prop = {
        "label": "테스트아파트",
        "search_addr": "서울특별시 송파구 송파대로 345",
        "pnu": "",
        "dongNm": "101",
        "hoNm": "101"
    }
    cnt = logic.fetch_all_years_for_property(test_prop, start_year=2020, end_year=2026)
    assert cnt == 7
    df_test = logic.history_df[logic.history_df["label"] == "테스트아파트"]
    assert len(df_test) == 7
