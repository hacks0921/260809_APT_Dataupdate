# -*- coding: utf-8 -*-
"""
아파트 공시지가 조회 비즈니스 로직 단위 테스트 모듈
"""

import os
import pytest
import pandas as pd
from app_gui import ScientificCalculatorLogic

@pytest.fixture
def logic_instance(tmp_path):
    """임시 CSV 파일을 사용하는 ScientificCalculatorLogic 픽스처"""
    test_csv = tmp_path / "test_history.csv"
    logic = ScientificCalculatorLogic(history_path=str(test_csv))
    return logic

def test_load_or_create_history_initial_seed_loaded(logic_instance):
    """초기 시드 데이터가 올바르게 로드되는지 테스트"""
    df = logic_instance.history_df
    assert not df.empty
    assert "label" in df.columns
    assert "year" in df.columns
    assert "price" in df.columns

def test_get_available_years_returns_sorted_years(logic_instance):
    """저장된 데이터의 연도 목록이 정렬되어 반환되는지 테스트"""
    years = logic_instance.get_available_years()
    assert isinstance(years, list)
    assert years == sorted(years)

def test_get_pivot_table_calculates_totals_and_diffs(logic_instance):
    """피벗 테이블 연산 시 Total 합계 및 전년대비 변동(액/률)이 정확히 계산되는지 테스트"""
    pivot = logic_instance.get_pivot_table(up_to_year=None)
    assert "Total" in pivot.columns
    assert "Total_Diff" in pivot.columns
    assert "Total_Rate" in pivot.columns
    
    # 2026년도 데이터 검증
    if 2026 in pivot.index:
        total_2026 = pivot.loc[2026, "Total"]
        # 각 주택 가격의 합과 Total 컬럼 값이 동일한지 검증
        prop_labels = [p["label"] for p in logic_instance.properties]
        sum_prices = pivot.loc[2026, prop_labels].sum(skipna=True)
        assert total_2026 == sum_prices

def test_get_pivot_table_filtered_by_up_to_year(logic_instance):
    """상한 연도 필터링 시 해당 연도 이하 데이터만 포함되는지 테스트"""
    up_to = 2022
    pivot = logic_instance.get_pivot_table(up_to_year=up_to)
    assert max(pivot.index) <= up_to
