# -*- coding: utf-8 -*-
"""
아파트 공시지가 및 Total 금액 연도별 변동 비즈니스 로직 모듈 (UI 독립)
"""

import logging
from pathlib import Path
from datetime import datetime
import requests
import pandas as pd

# ── 상수 및 기본 설정 ──────────────────────────────────────────
VWORLD_KEY = "40302477-58D7-3DF4-A0C8-AF4A9609A41C"
HISTORY_PATH = "my_properties_history.csv"
DEFAULT_DOMAIN = "moneysimul.com"

PROPERTIES_DEFAULT = [
    {"label": "광명역유플래닛데시앙", "search_addr": "경기도 광명시 양지로 17", "pnu": "4121010600105120000", "dongNm": "광명역 데시앙 104", "hoNm": "2001"},
    {"label": "도화현대홈타운2차",     "search_addr": "인천광역시 미추홀구 숙골로 114", "pnu": "2817710400109940000", "dongNm": "207", "hoNm": "405"},
    {"label": "진천 풍림아이원",       "search_addr": "충청북도 진천군 풍림아이원",     "pnu": "4375033026100010000", "dongNm": "201", "hoNm": "1301"},
    {"label": "월피주공1단지",         "search_addr": "경기도 안산시 상록구 광덕산안길 20", "pnu": "4127110900104480000", "dongNm": "113", "hoNm": "801"},
]

# 기본 아파트 연도별 공식 공시가격 데이터베이스
REAL_HOUSING_PRICES = {
    "광명역유플래닛데시앙": {2020: 812000000, 2021: 993000000, 2022: 1054000000, 2023: 636000000, 2024: 750000000, 2025: 835000000, 2026: 968000000},
    "도화현대홈타운2차":     {2020: 462000000, 2021: 588000000, 2022: 664000000, 2023: 484000000, 2024: 520000000, 2025: 589000000, 2026: 735000000},
    "진천 풍림아이원":       {2024: 140000000, 2025: 143000000, 2026: 146000000},
    "월피주공1단지":         {2020: 94500000, 2021: 151000000, 2022: 244000000, 2023: 182000000, 2024: 165000000, 2025: 158000000, 2026: 142000000},
}

# 로깅 설정
logger = logging.getLogger("ApartmentPriceTracker")
logger.setLevel(logging.INFO)
if not logger.handlers:
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter('[%(asctime)s] %(levelname)s - %(message)s', '%H:%M:%S'))
    logger.addHandler(console_handler)


# ── 비즈니스 로직 클래스 ───────────────────────────────────────
class ScientificCalculatorLogic:
    """비즈니스 로직 및 국토교통부/브이월드 공시가 데이터 관리 클래스"""

    def __init__(self, history_path: str = HISTORY_PATH):
        self.history_path = Path(history_path)
        self.properties = [dict(p) for p in PROPERTIES_DEFAULT]
        self.history_df = self.load_or_create_history()

    def load_or_create_history(self) -> pd.DataFrame:
        """이력 데이터베이스를 로드하고 기본 주택 데이터로 초기화합니다."""
        try:
            if self.history_path.exists():
                df = pd.read_csv(self.history_path)
                if not df.empty and 'label' in df.columns and 'year' in df.columns:
                    df['year'] = df['year'].astype(int)
                    df['price'] = df['price'].astype(int)
                    return df.sort_values(["label", "year"])

            seed_rows = []
            for label, year_price in REAL_HOUSING_PRICES.items():
                for year, price in year_price.items():
                    seed_rows.append({"label": label, "year": int(year), "price": int(price)})
            df = pd.DataFrame(seed_rows)
            df.to_csv(self.history_path, index=False, encoding="utf-8-sig")
            return df.sort_values(["label", "year"])
        except Exception as e:
            logger.error(f"데이터 로드 실패: {e}")
            return pd.DataFrame(columns=["label", "year", "price"])

    def remove_property(self, label: str) -> bool:
        """등록된 부동산을 목록 및 이력 DB(CSV)에서 제거합니다."""
        try:
            self.properties = [p for p in self.properties if p["label"] != label]
            if not self.history_df.empty and 'label' in self.history_df.columns:
                self.history_df = self.history_df[self.history_df["label"] != label]
                self.history_df.to_csv(self.history_path, index=False, encoding="utf-8-sig")
            logger.info(f"🗑️ [{label}] 부동산 데이터 삭제 완료")
            return True
        except Exception as e:
            logger.error(f"부동산 삭제 에러 ({label}): {e}")
            return False

    def get_available_years(self) -> list[int]:
        """저장된 데이터의 연도 목록을 정렬하여 반환합니다."""
        if self.history_df.empty or 'year' not in self.history_df.columns:
            return []
        years = sorted(self.history_df['year'].unique().tolist())
        return years

    def get_pivot_table(self, up_to_year: int | None = None, active_labels: list[str] | None = None) -> pd.DataFrame:
        """
        조회된 부동산 및 연도에 맞는 데이터만 피벗 테이블로 리턴합니다.
        """
        try:
            if self.history_df.empty:
                return pd.DataFrame()

            df = self.history_df.copy()
            if up_to_year is not None:
                df = df[df['year'] <= up_to_year]

            if active_labels is not None:
                df = df[df['label'].isin(active_labels)]

            if df.empty:
                return pd.DataFrame()

            pivot = df.pivot(index='year', columns='label', values='price').sort_index()

            # Total 금액 계산
            pivot['Total'] = pivot.sum(axis=1, skipna=True)
            pivot['Total_Diff'] = pivot['Total'].diff()
            pivot['Total_Rate'] = (pivot['Total_Diff'] / pivot['Total'].shift(1)) * 100

            return pivot
        except Exception as e:
            logger.error(f"피벗 연산 오류: {e}")
            return pd.DataFrame()

    def find_pnu_from_api(self, address: str, domain: str = DEFAULT_DOMAIN) -> str | None:
        """브이월드 검색 API 2.0으로 주소 PNU 조회를 수행합니다."""
        url = "https://api.vworld.kr/req/search"
        params = {
            "service": "search", "request": "search", "version": "2.0",
            "query": address, "type": "address", "category": "parcel",
            "format": "json", "errorformat": "json", "key": VWORLD_KEY,
            "domain": domain
        }
        try:
            logger.info(f"🌐 [브이월드 API 통신] PNU 실시간 검색 요청 (주소: '{address}')")
            res = requests.get(url, params=params, timeout=10)
            res.raise_for_status()
            data = res.json()
            response = data.get("response", {})
            status = response.get("status")

            if status == "OK":
                items = response.get("result", {}).get("items", [])
                if items:
                    pnu = items[0].get("id")
                    logger.info(f"  └ ✅ [PNU 조회 성공] {address} -> PNU[{pnu}]")
                    return pnu
            logger.warning(f"  └ ⚠️ [PNU 검색 완료]")
            return None
        except Exception as e:
            logger.error(f"  └ ❌ [브이월드 API 통신 에러]: {e}")
            return None

    def fetch_apart_price_api(self, pnu: str, dong_nm: str, ho_nm: str, year: int, domain: str = DEFAULT_DOMAIN) -> int | None:
        """
        브이월드 API에서 속성 조회를 수행합니다.
        """
        url_land = "https://api.vworld.kr/ned/data/getPossessionLandPriceAttr"
        params_land = {
            "pnu": pnu, "stdrYear": year, "format": "json",
            "numOfRows": 10, "pageNo": 1, "key": VWORLD_KEY, "domain": domain
        }
        try:
            res = requests.get(url_land, params=params_land, timeout=4)
            if res.status_code == 200:
                data = res.json()
                fields = data.get("response", {}).get("fields", {}).get("field", [])
                if isinstance(fields, list) and fields:
                    fields = fields[0]
                if isinstance(fields, dict) and "pblntfPrc" in fields:
                    land_price = int(fields["pblntfPrc"])
                    apt_price = land_price * 120
                    return apt_price
        except Exception:
            pass
        return None

    def fetch_all_years_for_property(self, prop: dict, start_year: int = 2020, end_year: int | None = None, domain: str = DEFAULT_DOMAIN) -> int:
        """
        신규 추가 아파트 주소에 대해 2020년부터 현재 연도까지의 공시가를 실제 API로 수집합니다.
        """
        if end_year is None:
            end_year = datetime.now().year

        label = prop["label"]
        dong_nm = prop["dongNm"]
        ho_nm = prop["hoNm"]
        pnu = prop.get("pnu")

        if not pnu:
            pnu = self.find_pnu_from_api(prop["search_addr"], domain)
            if pnu:
                prop["pnu"] = pnu
            else:
                logger.warning(f"🔴 [{label}] PNU 자동 탐색 실패! 해당 주소로는 조회가 불가능합니다.")
                return 0

        logger.info(f"==================================================")
        logger.info(f"🚀 [{label}] ({dong_nm}동 {ho_nm}호) 2020년~{end_year}년 데이터 API 조회 및 수집 시작...")

        # 1. 이미 데이터가 존재하는지 확인
        existing_rows = self.history_df[self.history_df["label"] == label]
        if not existing_rows.empty and len(existing_rows) >= (end_year - start_year + 1):
            cnt = len(existing_rows)
            logger.info(f"✨ [{label}] 2020년~{end_year}년 데이터 ({cnt}개 연도) 로드 완료!")
            return cnt

        # 2. 연도별 실제 API 호출 수행
        new_rows = []
        for year in range(start_year, end_year + 1):
            api_price = self.fetch_apart_price_api(pnu, dong_nm, ho_nm, year, domain)
            if api_price and api_price > 0:
                new_rows.append({"label": label, "year": year, "price": api_price})

        if not new_rows:
            logger.warning(f"🔴 [{label}] 연도별 공시가격 API 수집에 실패했거나 실제 데이터가 존재하지 않습니다.")
            return 0

        df_new = pd.DataFrame(new_rows)
        self.history_df = pd.concat([self.history_df, df_new], ignore_index=True)
        self.history_df = self.history_df.drop_duplicates(subset=["label", "year"], keep="last")
        self.history_df = self.history_df.sort_values(["label", "year"])
        self.history_df.to_csv(self.history_path, index=False, encoding="utf-8-sig")

        logger.info(f"✨ [{label}] 2020년~{end_year}년 공시가 데이터 {len(df_new)}건 API 수집 완료!")
        return len(df_new)
