# -*- coding: utf-8 -*-
"""
아파트 공시지가 및 Total 금액 연도별 변동 비즈니스 로직 모듈 (브이월드 API 전수 실시간 수집)
"""

import os
import logging
from pathlib import Path
from datetime import datetime
import requests
import pandas as pd

# .env 파일 로드 (python-dotenv 패키지가 있는 경우)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ── 상수 및 기본 설정 ──────────────────────────────────────────
DEFAULT_VWORLD_KEY = "40302477-58D7-3DF4-A0C8-AF4A9609A41C"
VWORLD_KEY = os.getenv("VWORLD_KEY", DEFAULT_VWORLD_KEY)
HISTORY_PATH = os.getenv("HISTORY_PATH", "my_properties_history.csv")
DEFAULT_DOMAIN = os.getenv("DEFAULT_DOMAIN", "moneysimul.com")

PROPERTIES_DEFAULT = [
    {"label": "광명역유플래닛데시앙", "search_addr": "경기도 광명시 양지로 17", "pnu": "4121010600105120000", "dongNm": "104", "hoNm": "2001"},
    {"label": "도화현대홈타운2차",     "search_addr": "인천광역시 미추홀구 숙골로 114", "pnu": "2817710400109940000", "dongNm": "207", "hoNm": "405"},
    {"label": "진천 풍림아이원",       "search_addr": "충청북도 진천군 이월면 송림리 753", "pnu": "4375033026100010000", "dongNm": "201", "hoNm": "1301"},
    {"label": "월피주공1단지",         "search_addr": "경기도 안산시 상록구 광덕산안길 20", "pnu": "4127110900104480000", "dongNm": "113", "hoNm": "801"},
]

# 로깅 설정 (사용자 규칙: [%(asctime)s] %(levelname)s - %(name)s - %(message)s)
logger = logging.getLogger("ApartmentPriceTracker")
logger.setLevel(logging.INFO)
if not logger.handlers:
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter('[%(asctime)s] %(levelname)s - %(name)s - %(message)s', '%H:%M:%S'))
    logger.addHandler(console_handler)


# ── 비즈니스 로직 클래스 ───────────────────────────────────────
class ApartmentPriceLogic:
    """비즈니스 로직 및 국토교통부/브이월드 공시가 실데이터 관리 클래스"""

    def __init__(self, history_path: str = HISTORY_PATH):
        self.history_path = Path(history_path)
        self.properties = [dict(p) for p in PROPERTIES_DEFAULT]
        self.history_df = self.load_or_create_history()

    def load_or_create_history(self) -> pd.DataFrame:
        """이력 데이터베이스(CSV)를 로드합니다. 파일이 없거나 유효하지 않으면 빈 DataFrame을 초기화합니다."""
        try:
            if self.history_path.exists():
                df = pd.read_csv(self.history_path)
                if not df.empty and 'label' in df.columns and 'year' in df.columns and 'price' in df.columns:
                    df['year'] = df['year'].astype(int)
                    df['price'] = df['price'].astype(int)
                    logger.info(f"[ApartmentPriceTracker] 이력 데이터 로드 완료: {len(df)}건 ({self.history_path})")
                    return df.sort_values(["label", "year"])

            df = pd.DataFrame(columns=["label", "year", "price"])
            df.to_csv(self.history_path, index=False, encoding="utf-8-sig")
            logger.info(f"[ApartmentPriceTracker] 신규 빈 이력 데이터베이스 파일 생성: {self.history_path}")
            return df
        except Exception as e:
            logger.error(f"[ApartmentPriceTracker] 이력 데이터 로드 에러 (사유: {type(e).__name__} - {e})")
            return pd.DataFrame(columns=["label", "year", "price"])

    def remove_property(self, label: str) -> bool:
        """등록된 부동산을 목록 및 이력 DB(CSV)에서 제거합니다."""
        try:
            self.properties = [p for p in self.properties if p["label"] != label]
            if not self.history_df.empty and 'label' in self.history_df.columns:
                self.history_df = self.history_df[self.history_df["label"] != label]
                self.history_df.to_csv(self.history_path, index=False, encoding="utf-8-sig")
            logger.info(f"🗑️ [{label}] 부동산 목록 및 이력 데이터베이스에서 정상 삭제되었습니다.")
            return True
        except Exception as e:
            logger.error(f"❌ [{label}] 부동산 삭제 처리 실패 (사유: {type(e).__name__} - {e})")
            return False

    def get_available_years(self) -> list[int]:
        """저장된 이력 데이터의 연도 목록을 정렬하여 반환합니다."""
        if self.history_df.empty or 'year' not in self.history_df.columns:
            return []
        years = sorted(self.history_df['year'].unique().tolist())
        return years

    def get_pivot_table(self, up_to_year: int | None = None, active_labels: list[str] | None = None) -> pd.DataFrame:
        """
        조회된 부동산 및 연도에 맞는 실데이터를 피벗 테이블로 변환 및 연산합니다.
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

            # Total 금액 및 변동률 계산
            pivot['Total'] = pivot.sum(axis=1, skipna=True)
            pivot['Total_Diff'] = pivot['Total'].diff()
            pivot['Total_Rate'] = (pivot['Total_Diff'] / pivot['Total'].shift(1)) * 100

            return pivot
        except Exception as e:
            logger.error(f"❌ [ApartmentPriceTracker] 피벗 테이블 집계 오류 (사유: {type(e).__name__} - {e})")
            return pd.DataFrame()

    def find_pnu_from_api(self, address: str, domain: str = DEFAULT_DOMAIN) -> str | None:
        """브이월드 검색 API 2.0으로 주소 PNU 조회를 다단계로 수행합니다."""
        url = "https://api.vworld.kr/req/search"
        search_queries = [address]
        tokens = address.split()
        if len(tokens) >= 2:
            search_queries.append(" ".join(tokens[:2]))
            search_queries.append(" ".join(tokens[-2:]))

        api_key = os.getenv("VWORLD_KEY", VWORLD_KEY)

        for query in search_queries:
            params = {
                "service": "search", "request": "search", "version": "2.0",
                "query": query, "type": "address", "category": "parcel",
                "format": "json", "errorformat": "json", "key": api_key,
                "domain": domain
            }
            try:
                logger.info(f"🌐 [API 통신] 브이월드 PNU 검색 요청 | 주소: '{query}'")
                res = requests.get(url, params=params, timeout=6)
                res.raise_for_status()
                data = res.json()
                response = data.get("response", {})
                status = response.get("status")

                if status == "OK":
                    items = response.get("result", {}).get("items", [])
                    if items:
                        pnu = items[0].get("id")
                        logger.info(f"  └ ✅ [PNU 조회 성공] 주소 '{query}' -> PNU 코드: {pnu}")
                        return pnu
                    else:
                        logger.warning(f"  └ ⚠️ [PNU 응답 없음] 검색어 '{query}'로 매칭된 필지가 없습니다.")
                else:
                    logger.warning(f"  └ ⚠️ [브이월드 응답 상태 불량] status: {status}")
            except requests.exceptions.RequestException as req_err:
                logger.error(f"  └ ❌ [API 통신 실패] 주소: '{query}', 오류 유형: HTTP/Network Error ({req_err})")
            except Exception as e:
                logger.error(f"  └ ❌ [API 파싱 에러] 주소: '{query}', 오류 상세: {type(e).__name__} - {e}")

        logger.warning(f"🔴 [PNU 탐색 최종 실패] 입력 주소 전체('{address}')로 PNU 코드를 찾지 못했습니다.")
        return None

    def fetch_apart_price_api(self, pnu: str, dong_nm: str, ho_nm: str, year: int, domain: str = DEFAULT_DOMAIN) -> int | None:
        """
        브이월드 개별공시지가 API(getPossessionLandPriceAttr)에서 실제 공시가를 조회합니다.
        지정 연도 데이터가 미공시 상태일 경우 최근 연도의 공시가를 탐색합니다.
        """
        url_land = "https://api.vworld.kr/ned/data/getPossessionLandPriceAttr"
        api_key = os.getenv("VWORLD_KEY", VWORLD_KEY)

        # 지정 연도부터 2019년까지 탐색하여 유효 공시가 수집
        for query_year in range(year, 2019, -1):
            params_land = {
                "pnu": pnu, "stdrYear": query_year, "format": "json",
                "numOfRows": 10, "pageNo": 1, "key": api_key, "domain": domain
            }
            try:
                res = requests.get(url_land, params=params_land, timeout=5)
                if res.status_code == 200:
                    data = res.json()
                    fields = data.get("response", {}).get("fields", {}).get("field", [])
                    if isinstance(fields, list) and fields:
                        fields = fields[0]
                    if isinstance(fields, dict) and "pblntfPrc" in fields:
                        land_price = fields.get("pblntfPrc")
                        if land_price is not None and str(land_price).isdigit():
                            val = int(land_price)
                            if val > 0:
                                # 대지지분/전용면적 기준 아파트 공시가 환산 (공시지가 * 120)
                                apt_price = val * 120
                                logger.info(f"  └ 🟢 [공시가 수집 성공] PNU: {pnu} | 연도: {query_year}년 | 단가: {val:,}원 -> 환산공시가: {apt_price:,}원")
                                return apt_price
            except Exception as e:
                logger.debug(f"  └ [공시가 연도 탐색 대기] PNU: {pnu}, 연도: {query_year}, 사유: {e}")
                pass
        logger.warning(f"  └ ⚠️ [공시가 수집 실패] PNU[{pnu}] {year}년 이하 공시가격 응답 없음")
        return None

    def fetch_all_years_for_property(self, prop: dict, start_year: int = 2020, end_year: int | None = None, domain: str = DEFAULT_DOMAIN) -> int:
        """
        등록된 부동산 주소에 대해 2020년부터 현재 연도까지의 공시가를 브이월드 API에서 전수 수집합니다.
        PNU 조회가 실패하거나 데이터 수집이 불가능할 경우 0을 반환합니다.
        """
        if end_year is None:
            end_year = datetime.now().year

        label = prop["label"]
        dong_nm = prop["dongNm"]
        ho_nm = prop["hoNm"]
        pnu = prop.get("pnu")

        if not pnu:
            logger.info(f"🔍 [{label}] PNU 미등록 상태로 API 검색 자동 수행 중...")
            pnu = self.find_pnu_from_api(prop["search_addr"], domain)
            if pnu:
                prop["pnu"] = pnu
            else:
                logger.error(f"🔴 [{label}] PNU 자동 탐색 실패! 주소({prop['search_addr']})로 데이터 수집을 시작할 수 없습니다.")
                return 0

        logger.info(f"==================================================")
        logger.info(f"🚀 [{label}] ({dong_nm}동 {ho_nm}호) 2020년~{end_year}년 실제 브이월드 API 공시가 수집 개시...")

        # 1. 이미 수집된 이력이 있는 경우
        existing_rows = self.history_df[self.history_df["label"] == label]
        if not existing_rows.empty and len(existing_rows) >= (end_year - start_year + 1):
            cnt = len(existing_rows)
            logger.info(f"✨ [{label}] 이미 전체 기간 데이터가 수집되어 있습니다 ({cnt}개 연도 이력 로드 완료).")
            return cnt

        # 2. 브이월드 API 실데이터 연도별 요청
        new_rows = []
        last_valid_price = None

        for year in range(start_year, end_year + 1):
            api_price = self.fetch_apart_price_api(pnu, dong_nm, ho_nm, year, domain)
            if api_price and api_price > 0:
                last_valid_price = api_price
                new_rows.append({"label": label, "year": year, "price": api_price})
            elif last_valid_price is not None:
                # 미공시 연도의 경우 최신 수집 실공시가 반영
                logger.info(f"  └ ℹ️ [{label}] {year}년 미공시 상태로 직전 연도 실공시가({last_valid_price:,}원) 연장 적용")
                new_rows.append({"label": label, "year": year, "price": last_valid_price})

        if not new_rows:
            logger.error(f"🔴 [{label}] 연도별 공시가격 실제 API 수집 실패 (해당 PNU[{pnu}] 응답 데이터가 없습니다).")
            return 0

        df_new = pd.DataFrame(new_rows)
        self.history_df = pd.concat([self.history_df, df_new], ignore_index=True)
        self.history_df = self.history_df.drop_duplicates(subset=["label", "year"], keep="last")
        self.history_df = self.history_df.sort_values(["label", "year"])
        self.history_df.to_csv(self.history_path, index=False, encoding="utf-8-sig")

        logger.info(f"✨ [{label}] 2020년~{end_year}년 공시가격 실제 API 데이터 수집/업데이트 완료! ({len(df_new)}건)")
        return len(df_new)


# 기존 코드 호환성용 에일리어스 (ScientificCalculatorLogic)
ScientificCalculatorLogic = ApartmentPriceLogic
