# -*- coding: utf-8 -*-
"""
브이월드(V-World) API를 이용한 보유 부동산 공시가격 자동 조회 CLI/GUI 메인 엔트리포인트

사용법:
    1. GUI 모드 실행 (기본):
        python main.py

    2. CLI 모드 2020년~현재 연도 전수 API 데이터 수집:
        python main.py --cli

    3. PNU 자동 검색:
        python main.py --find-pnu
"""

import sys
from datetime import datetime
import pandas as pd

from logic import ApartmentPriceLogic, PROPERTIES_DEFAULT, logger


def run_find_pnu():
    """등록된 부동산의 PNU를 브이월드 검색 API로 자동 탐색합니다."""
    logger.info("=== PNU 자동 검색 개시 ===")
    logic = ApartmentPriceLogic()
    for prop in PROPERTIES_DEFAULT:
        pnu = logic.find_pnu_from_api(prop["search_addr"])
        if pnu:
            logger.info(f"🟢 [{prop['label']}]: PNU = {pnu}")
        else:
            logger.warning(f"🔴 [{prop['label']}]: PNU 검색 실패")


def run_cli_mode():
    """CLI 모드: 등록된 전체 부동산에 대해 2020년부터 현재 연도까지 전수 API 수집 실행"""
    logger.info("=== CLI 모드: 2020년~현재 연도 공시지가 API 전수 수집 시작 ===")
    logic = ApartmentPriceLogic()
    current_year = datetime.now().year
    total_count = 0

    for prop in logic.properties:
        cnt = logic.fetch_all_years_for_property(prop, start_year=2020, end_year=current_year)
        total_count += cnt

    history_df = logic.load_or_create_history()

    if not history_df.empty:
        logger.info("\n=== 📊 수집된 연도별 실제 공시지가 현황 ===")
        pivot = history_df.pivot(index='year', columns='label', values='price')
        logger.info("\n" + str(pivot))
    else:
        logger.warning("\n⚠️ 수집된 실제 공시지가 데이터가 없습니다. (API 인증키 및 도메인을 확인하세요)")


if __name__ == "__main__":
    if "--find-pnu" in sys.argv:
        run_find_pnu()
        sys.exit(0)

    if "--cli" in sys.argv:
        run_cli_mode()
        sys.exit(0)

    # 기본 실행 모드: PyQt6 GUI 실행
    from app_gui import main as run_gui
    run_gui()
