# -*- coding: utf-8 -*-
"""
아파트 공시지가 연도별 변동 및 자산 분석 웹 시스템 (Streamlit 전용)
"""

import sys
import logging
from datetime import datetime
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import streamlit as st

from logic import PROPERTIES_DEFAULT, ScientificCalculatorLogic, logger

# 한글 폰트 설정
plt.rcParams['axes.unicode_minus'] = False
try:
    plt.rcParams['font.family'] = 'NanumGothic'
except Exception:
    pass

st.set_page_config(
    page_title="아파트 공시지가 연도별 변동 분석 시스템",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 세션 상태 초기화
if "logic" not in st.session_state:
    st.session_state.logic = ScientificCalculatorLogic()

if "active_labels" not in st.session_state:
    st.session_state.active_labels = [p["label"] for p in st.session_state.logic.properties]

logic = st.session_state.logic

# ── 헤더 타이틀 ────────────────────────────────────────────────
st.title("🏢 아파트 공시지가 연도별 변동 및 자산 분석 시스템")
st.caption("국토교통부/브이월드 공시가격 데이터를 기반으로 연도별 변동 추이와 총 자산 가치를 시각화합니다.")
st.markdown("---")

# ── 1. 내 보유 부동산 목록 (카드 뷰) ─────────────────────────
st.subheader("📌 내 보유 부동산 목록")
cols = st.columns(len(logic.properties) if logic.properties else 1)

for idx, prop in enumerate(logic.properties):
    with cols[idx % len(cols)]:
        with st.container(border=True):
            st.markdown(f"### 🏢 {prop['label']}")
            st.write(f"**동/호수:** {prop['dongNm']}동 {prop['hoNm']}호")
            st.write(f"📍 {prop['search_addr']}")
            pnu_txt = prop['pnu'] if prop['pnu'] else 'PNU 검색 필요'
            st.caption(f"🔑 PNU: {pnu_txt}")

            c1, c2 = st.columns(2)
            if c1.button("⚡ 조회", key=f"fetch_{idx}"):
                with st.spinner(f"[{prop['label']}] 공시가 수집 중..."):
                    cnt = logic.fetch_all_years_for_property(prop, start_year=2020, end_year=datetime.now().year)
                    if cnt == 0:
                        st.error(f"⚠️ [{prop['label']}] 브이월드 API 조회가 불가능하거나 PNU를 찾지 못했습니다.")
                    else:
                        if prop['label'] not in st.session_state.active_labels:
                            st.session_state.active_labels.append(prop['label'])
                        st.success(f"[{prop['label']}] {cnt}개 연도 데이터 조회 완료!")
                        st.rerun()

            if c2.button("🗑️ 삭제", key=f"del_{idx}"):
                label = prop['label']
                logic.remove_property(label)
                if label in st.session_state.active_labels:
                    st.session_state.active_labels.remove(label)
                st.warning(f"[{label}] 삭제되었습니다.")
                st.rerun()

st.markdown("---")

# ── 2. 사이드바 (신규 추가 & 연도 필터링) ────────────────────
with st.sidebar:
    st.header("➕ 신규 아파트 등록")
    with st.form("form_add_property", clear_on_submit=True):
        txt_name = st.text_input("부동산 별칭", placeholder="예: 파주 한양수자인")
        txt_addr = st.text_input("주소 (도로명/지번)", placeholder="예: 경기도 광명시 양지로 17")
        txt_dong = st.text_input("동 명칭", placeholder="예: 광명역 데시앙 104동")
        txt_ho = st.text_input("호수", placeholder="예: 2001")
        btn_submit = st.form_submit_button("🚀 2020년~현재 데이터 수집")

        if btn_submit:
            if not txt_name or not txt_addr or not txt_dong or not txt_ho:
                st.error("모든 항목을 입력해 주세요.")
            else:
                new_prop = {
                    "label": txt_name.strip(),
                    "search_addr": txt_addr.strip(),
                    "pnu": "",
                    "dongNm": txt_dong.strip(),
                    "hoNm": txt_ho.strip()
                }
                with st.spinner(f"[{txt_name}] 수집 중..."):
                    cnt = logic.fetch_all_years_for_property(new_prop, start_year=2020, end_year=datetime.now().year)
                    if cnt == 0:
                        st.error(f"⚠️ [{txt_name}] 브이월드 API 조회가 조회가 실패하여 등록이 취소되었습니다.")
                    else:
                        if not any(p["label"] == txt_name for p in logic.properties):
                            logic.properties.append(new_prop)
                        if txt_name not in st.session_state.active_labels:
                            st.session_state.active_labels.append(txt_name)
                        st.success(f"[{txt_name}] 등록 및 데이터 수집 성공!")
                        st.rerun()

    st.markdown("---")
    st.header("📅 연도 필터링")
    years = logic.get_available_years()
    year_options = ["전체 (전체 누적)"] + [f"{y}년까지 누적" for y in reversed(years)]
    selected_option = st.selectbox("누적 연도 선택", year_options)
    
    target_year = None
    if selected_option != "전체 (전체 누적)":
        target_year = int(selected_option.replace("년까지 누적", ""))

# ── 3. 메인 대시보드 (테이블 & 차트) ──────────────────────────
pivot_df = logic.get_pivot_table(up_to_year=target_year, active_labels=st.session_state.active_labels)

col_table, col_chart = st.columns([1, 1])

with col_table:
    st.subheader("📊 연도별 공시지가 현황표")
    if pivot_df.empty:
        st.info("💡 상단 부동산의 [⚡ 조회] 버튼을 눌러 데이터를 수집해 주세요.")
    else:
        years_list = [int(y) for y in pivot_df.index]
        prop_labels = [p["label"] for p in logic.properties if p["label"] in pivot_df.columns]
        row_items = prop_labels + ["Total (합계)", "전년대비 변동액", "변동률 (%)"]

        table_data = []
        for label in row_items:
            row_dict = {"부동산 / 항목": label}
            for year in years_list:
                year_row = pivot_df.loc[year]
                if label in prop_labels:
                    val = year_row.get(label)
                    row_dict[f"{year}년"] = f"{val / 1e8:.2f}억" if pd.notna(val) and val > 0 else "-"
                elif label == "Total (합계)":
                    val = year_row.get("Total")
                    row_dict[f"{year}년"] = f"{val / 1e8:.2f}억" if pd.notna(val) and val > 0 else "-"
                elif label == "전년대비 변동액":
                    val = year_row.get("Total_Diff")
                    row_dict[f"{year}년"] = f"{val / 1e8:+.2f}억" if pd.notna(val) else "-"
                elif label == "변동률 (%)":
                    val = year_row.get("Total_Rate")
                    row_dict[f"{year}년"] = f"{val:+.1f}%" if pd.notna(val) else "-"
            table_data.append(row_dict)

        df_display = pd.DataFrame(table_data)
        st.dataframe(df_display, use_container_width=True, hide_index=True)

with col_chart:
    st.subheader("📈 공시지가 및 Total 추이 그래프")
    if pivot_df.empty:
        st.info("데이터를 수집하면 그래프가 표출됩니다.")
    else:
        years_num = [int(y) for y in pivot_df.index]
        prop_labels = [p["label"] for p in logic.properties if p["label"] in pivot_df.columns]

        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(7, 6))

        colors = ['#0D6EFD', '#198754', '#D63384', '#6F42C1', '#FD7E14']
        markers = ['o', 's', '^', 'D', 'v']

        # Subplot 1: 개별 추이선
        for idx, label in enumerate(prop_labels):
            if label in pivot_df.columns:
                prices = pivot_df[label] / 1e8
                ax1.plot(years_num, prices, label=label, marker=markers[idx % len(markers)], color=colors[idx % len(colors)], linewidth=2)
                for x_val, y_val in zip(years_num, prices):
                    if pd.notna(y_val) and y_val > 0:
                        ax1.annotate(f"{y_val:.2f}억", xy=(x_val, y_val), xytext=(0, 4), textcoords="offset points", ha='center', fontsize=7.5, fontweight='bold')

        ax1.set_title("🏢 선택 부동산별 공시지가 추이 (단위: 억원)", fontsize=10, fontweight='bold')
        ax1.set_ylabel("공시가 (억원)", fontsize=8.5)
        ax1.set_xticks(years_num)
        ax1.set_xticklabels([f"{y}년" for y in years_num], fontsize=8)
        ax1.grid(True, linestyle='--', alpha=0.5)
        ax1.legend(loc='upper left', fontsize=8)

        # Subplot 2: Total 추이
        totals = pivot_df['Total'] / 1e8
        bars = ax2.bar(years_num, totals, color='#339AF0', alpha=0.5, width=0.4, label='Total 합계')
        ax2.plot(years_num, totals, color='#1864AB', marker='o', linewidth=2, label='Total 추이')

        for bar in bars:
            h = bar.get_height()
            if pd.notna(h) and h > 0:
                ax2.annotate(f"{h:.2f}억원", xy=(bar.get_x() + bar.get_width() / 2, h), xytext=(0, 3), textcoords="offset points", ha='center', fontsize=8, fontweight='bold', color='#1864AB')

        ax2.set_title("💰 Total 총 자산 연도별 변동 (단위: 억원)", fontsize=10, fontweight='bold')
        ax2.set_xlabel("조회 연도", fontsize=8.5)
        ax2.set_ylabel("Total (억원)", fontsize=8.5)
        ax2.set_xticks(years_num)
        ax2.set_xticklabels([f"{y}년" for y in years_num], fontsize=8)
        ax2.grid(True, linestyle='--', alpha=0.5)
        ax2.legend(loc='upper left', fontsize=8)

        fig.tight_layout()
        st.pyplot(fig)
