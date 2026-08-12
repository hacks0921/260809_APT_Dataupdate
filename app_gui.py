# -*- coding: utf-8 -*-
"""
아파트 공시지가 및 Total 금액 연도별 변동 조회 GUI 애플리케이션 (실제 API 수집 전용)

새로운 아파트 주소를 입력하거나 등록된 집의 '⚡ 데이터 조회' 버튼을 클릭하면
국토부/브이월드 API를 통해 2020년부터 현재 연도까지의 공시가 실데이터를 자동 수집하여
테이블과 차트에 실시간으로 표출합니다.
"""

import sys
import logging
from pathlib import Path
from datetime import datetime
import pandas as pd
import matplotlib
matplotlib.use('QtAgg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QLabel, QPushButton, QComboBox, QTableWidget,
    QTableWidgetItem, QHeaderView, QSplitter, QMessageBox, QFrame,
    QGroupBox, QStatusBar, QStyleFactory, QTextEdit, QLineEdit
)
from PyQt6.QtCore import Qt, pyqtSignal, QObject
from PyQt6.QtGui import QFont, QColor

# 비즈니스 로직 모듈 불러오기 (Single Source of Truth)
from logic import ApartmentPriceLogic, PROPERTIES_DEFAULT, logger, HISTORY_PATH

# 한글 폰트 및 마이너스 깨짐 방지
plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False


# ── 커스텀 GUI 로그 핸들러 ────────────────────────────────────
class QLogSignal(QObject):
    log_signal = pyqtSignal(str)


class QTextEditLogger(logging.Handler):
    """logging 모듈의 출력을 PyQt GUI QTextEdit 위젯으로 전달하는 핸들러"""
    def __init__(self):
        super().__init__()
        self.signals = QLogSignal()

    def emit(self, record):
        msg = self.format(record)
        self.signals.log_signal.emit(msg)


# GUI 전용 로거 핸들러 등록
gui_log_handler = QTextEditLogger()
gui_log_handler.setFormatter(logging.Formatter('[%(asctime)s] %(levelname)s - %(message)s', '%H:%M:%S'))
logger.addHandler(gui_log_handler)


# ── UI 뷰 클래스 ───────────────────────────────────────────────
class ApartmentPriceGUI(QMainWindow):
    """아파트 공시지가 자동 조회 및 시각화 GUI 클래스"""

    def __init__(self):
        super().__init__()
        self.logic = ApartmentPriceLogic()
        self.active_labels = []  # 사용자가 조회한 부동산 목록만 담는 리스트
        self.init_ui()

    def init_ui(self):
        """UI 구성요소 초기화 및 레이아웃 설정"""
        self.setWindowTitle("아파트 공시지가 연도별 변동 및 자산 분석 시스템 (브이월드 API 실데이터 수집)")
        self.resize(1360, 920)
        self.setStyle(QStyleFactory.create("Fusion"))

        widget_central = QWidget()
        self.setCentralWidget(widget_central)
        layout_main = QVBoxLayout(widget_central)
        layout_main.setSpacing(10)
        layout_main.setContentsMargins(12, 12, 12, 12)

        # 1. 📌 내 등록 부동산 목록 (원클릭 조회 카드 뷰)
        self.group_cards = QGroupBox("📌 내 보유 부동산 목록 (조회할 집의 '⚡ 데이터 조회' 버튼을 클릭하세요)")
        self.group_cards.setFont(QFont("Malgun Gothic", 9, QFont.Weight.Bold))
        self.layout_cards_container = QVBoxLayout(self.group_cards)
        self.layout_cards_container.setContentsMargins(8, 6, 8, 8)
        
        self.render_property_cards()
        layout_main.addWidget(self.group_cards)

        # 2. ➕ 신규 아파트 등록 & 전수 수집 패널
        group_input = QGroupBox("➕ 신규 아파트 등록 & 2020년~현재 브이월드 API 실시간 데이터 조회")
        group_input.setFont(QFont("Malgun Gothic", 9, QFont.Weight.Bold))
        layout_input_grid = QGridLayout(group_input)
        layout_input_grid.setContentsMargins(10, 8, 10, 8)
        layout_input_grid.setSpacing(8)

        lbl_name = QLabel("부동산 별칭:")
        lbl_name.setFont(QFont("Malgun Gothic", 9))
        self.txt_name = QLineEdit()
        self.txt_name.setPlaceholderText("예: 파주 한양수자인")

        lbl_addr = QLabel("도로명/지번 주소:")
        lbl_addr.setFont(QFont("Malgun Gothic", 9))
        self.txt_addr = QLineEdit()
        self.txt_addr.setPlaceholderText("예: 경기도 파주시 문산읍 당동리 947")

        lbl_dong = QLabel("동:")
        lbl_dong.setFont(QFont("Malgun Gothic", 9))
        self.txt_dong = QLineEdit()
        self.txt_dong.setPlaceholderText("104")
        self.txt_dong.setMaximumWidth(70)

        lbl_ho = QLabel("호:")
        lbl_ho.setFont(QFont("Malgun Gothic", 9))
        self.txt_ho = QLineEdit()
        self.txt_ho.setPlaceholderText("304")
        self.txt_ho.setMaximumWidth(70)

        self.btn_add_and_fetch = QPushButton("🚀 2020년~현재 데이터 조회 및 차트 업데이트")
        self.btn_add_and_fetch.setFont(QFont("Malgun Gothic", 9, QFont.Weight.Bold))
        self.btn_add_and_fetch.setStyleSheet("""
            QPushButton {
                background-color: #0D6EFD; color: white; border-radius: 5px; padding: 6px 14px;
            }
            QPushButton:hover { background-color: #0B5ED7; }
        """)
        self.btn_add_and_fetch.clicked.connect(self.handle_add_custom_property)

        layout_input_grid.addWidget(lbl_name, 0, 0)
        layout_input_grid.addWidget(self.txt_name, 0, 1)
        layout_input_grid.addWidget(lbl_addr, 0, 2)
        layout_input_grid.addWidget(self.txt_addr, 0, 3, 1, 3)
        layout_input_grid.addWidget(lbl_dong, 0, 6)
        layout_input_grid.addWidget(self.txt_dong, 0, 7)
        layout_input_grid.addWidget(lbl_ho, 0, 8)
        layout_input_grid.addWidget(self.txt_ho, 0, 9)
        layout_input_grid.addWidget(self.btn_add_and_fetch, 0, 10)

        layout_main.addWidget(group_input)

        # 3. 컨트롤 패널 (연도 선택 & 전체 부동산 일괄 API 수집 버튼)
        panel_control = QHBoxLayout()

        lbl_year_select = QLabel("📅 누적 조회 연도 선택:")
        lbl_year_select.setFont(QFont("Malgun Gothic", 9, QFont.Weight.Bold))

        self.cmb_target_year = QComboBox()
        self.cmb_target_year.setFont(QFont("Malgun Gothic", 9))
        self.cmb_target_year.setMinimumWidth(130)

        self.btn_filter_year = QPushButton("🔍 연도 필터링 업데이트")
        self.btn_filter_year.setFont(QFont("Malgun Gothic", 9, QFont.Weight.Bold))
        self.btn_filter_year.clicked.connect(self.handle_filter_year)

        self.btn_fetch_all_default = QPushButton("⚡ 전체 집 2020~현재 API 일괄 조회 및 업데이트")
        self.btn_fetch_all_default.setFont(QFont("Malgun Gothic", 9, QFont.Weight.Bold))
        self.btn_fetch_all_default.setStyleSheet("""
            QPushButton {
                background-color: #198754; color: white; border-radius: 5px; padding: 6px 14px;
            }
            QPushButton:hover { background-color: #157347; }
        """)
        self.btn_fetch_all_default.clicked.connect(self.handle_fetch_all_properties)

        panel_control.addWidget(lbl_year_select)
        panel_control.addWidget(self.cmb_target_year)
        panel_control.addWidget(self.btn_filter_year)
        panel_control.addSpacing(15)
        panel_control.addWidget(self.btn_fetch_all_default)
        panel_control.addStretch()

        layout_main.addLayout(panel_control)

        # 4. 메인 시각화 영역 (QSplitter: 좌측 테이블, 우측 차트)
        splitter_main = QSplitter(Qt.Orientation.Horizontal)

        # 4-1. 테이블 영역
        group_table = QGroupBox("📊 연도별 공시지가 현황표 (조회 시 업데이트됨)")
        group_table.setFont(QFont("Malgun Gothic", 10, QFont.Weight.Bold))
        layout_table = QVBoxLayout(group_table)

        self.tbl_price_history = QTableWidget()
        self.tbl_price_history.setFont(QFont("Malgun Gothic", 9))
        self.tbl_price_history.setAlternatingRowColors(True)
        self.tbl_price_history.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout_table.addWidget(self.tbl_price_history)

        # 4-2. 차트 영역 (Matplotlib)
        group_chart = QGroupBox("📈 공시지가 및 Total 연도별 변동 추이 그래프")
        group_chart.setFont(QFont("Malgun Gothic", 10, QFont.Weight.Bold))
        layout_chart = QVBoxLayout(group_chart)

        self.fig_chart = Figure(figsize=(7.5, 5.5), dpi=100)
        self.canvas_chart = FigureCanvas(self.fig_chart)
        layout_chart.addWidget(self.canvas_chart)

        splitter_main.addWidget(group_table)
        splitter_main.addWidget(group_chart)
        splitter_main.setSizes([480, 820])

        layout_main.addWidget(splitter_main, stretch=1)

        # 5. 실시간 진행 로그 패널 (Log Viewer)
        group_log = QGroupBox("📜 시스템 실시간 데이터 연동 및 API 조회 진행 로그")
        group_log.setFont(QFont("Malgun Gothic", 9, QFont.Weight.Bold))
        layout_log = QVBoxLayout(group_log)
        layout_log.setContentsMargins(6, 6, 6, 6)

        self.txt_log_viewer = QTextEdit()
        self.txt_log_viewer.setReadOnly(True)
        self.txt_log_viewer.setFont(QFont("Consolas", 9))
        self.txt_log_viewer.setStyleSheet("background-color: #1E1E1E; color: #D4D4D4; border-radius: 4px;")
        self.txt_log_viewer.setMaximumHeight(130)
        layout_log.addWidget(self.txt_log_viewer)

        layout_main.addWidget(group_log)

        # 6. 상태바 설정
        self.statusBar_info = QStatusBar()
        self.setStatusBar(self.statusBar_info)
        self.statusBar_info.showMessage("조회 대기 상태 — 원하는 집 카드의 '⚡ 데이터 조회' 버튼을 클릭하여 조회를 시작하세요.")

        # 로그 신호 연결
        gui_log_handler.signals.log_signal.connect(self.append_log)

        # 연도 선택지 구성
        self.populate_year_combo()
        
        # 시작 시 대기 화면 표출
        self.render_empty_dashboard()

    def render_empty_dashboard(self):
        """시작 시 테이블과 차트를 조회 대기 상태로 유지합니다."""
        self.tbl_price_history.setRowCount(0)
        self.tbl_price_history.setColumnCount(0)
        self.fig_chart.clear()

        ax = self.fig_chart.add_subplot(1, 1, 1)
        ax.text(
            0.5, 0.5, "💡 상단 부동산 카드의 [⚡ 데이터 조회] 버튼이나\n[➕ 신규 아파트 등록]을 이용하면 실제 API 그래프가 표출됩니다.",
            ha='center', va='center', fontsize=12, fontweight='bold', color='#495057'
        )
        ax.axis('off')
        self.canvas_chart.draw()
        logger.info("시스템 시작 준비 완료 — 조회를 원하는 부동산의 '⚡ 데이터 조회' 버튼을 누르면 브이월드 API 데이터 수집을 진행합니다.")

    def _clear_layout(self, layout):
        """레이아웃 내부의 모든 위젯과 하위 레이아웃을 재귀 삭제합니다."""
        if layout is not None:
            while layout.count():
                item = layout.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()
                elif item.layout() is not None:
                    self._clear_layout(item.layout())

    def render_property_cards(self):
        """내 등록 부동산 목록을 카드 형태로 시각화"""
        self._clear_layout(self.layout_cards_container)

        layout_cards = QHBoxLayout()
        layout_cards.setSpacing(10)

        for prop in self.logic.properties:
            card = QFrame()
            card.setFrameShape(QFrame.Shape.StyledPanel)
            card.setStyleSheet("""
                QFrame {
                    background-color: #F8F9FA;
                    border: 1px solid #CED4DA;
                    border-radius: 6px;
                    padding: 6px;
                }
                QFrame:hover {
                    background-color: #E9ECEF;
                    border-color: #0D6EFD;
                }
            """)
            layout_card = QVBoxLayout(card)
            layout_card.setContentsMargins(6, 6, 6, 6)
            layout_card.setSpacing(4)

            lbl_title = QLabel(f"🏢 {prop['label']} ({prop['dongNm']}동 {prop['hoNm']}호)")
            lbl_title.setFont(QFont("Malgun Gothic", 9, QFont.Weight.Bold))
            lbl_title.setStyleSheet("color: #0D6EFD;")

            lbl_addr = QLabel(f"📍 {prop['search_addr']}")
            lbl_addr.setFont(QFont("Malgun Gothic", 8))
            lbl_addr.setStyleSheet("color: #495057;")

            pnu_txt = prop['pnu'] if prop.get('pnu') else 'PNU 검색 예정'
            lbl_pnu = QLabel(f"🔑 PNU: {pnu_txt}")
            lbl_pnu.setFont(QFont("Malgun Gothic", 8))
            lbl_pnu.setStyleSheet("color: #6C757D;")

            layout_btns = QHBoxLayout()
            layout_btns.setSpacing(4)

            btn_fetch_single = QPushButton("⚡ 데이터 조회")
            btn_fetch_single.setFont(QFont("Malgun Gothic", 8, QFont.Weight.Bold))
            btn_fetch_single.setStyleSheet("""
                QPushButton {
                    background-color: #212529; color: white; border-radius: 4px; padding: 4px 6px;
                }
                QPushButton:hover { background-color: #0D6EFD; }
            """)
            btn_fetch_single.clicked.connect(lambda checked, p=prop: self.handle_fetch_single_property(p))

            btn_remove_single = QPushButton("🗑️ 삭제")
            btn_remove_single.setFont(QFont("Malgun Gothic", 8, QFont.Weight.Bold))
            btn_remove_single.setStyleSheet("""
                QPushButton {
                    background-color: #DC3545; color: white; border-radius: 4px; padding: 4px 6px;
                }
                QPushButton:hover { background-color: #BB2D3B; }
            """)
            btn_remove_single.clicked.connect(lambda checked, p=prop: self.handle_remove_property(p))

            layout_btns.addWidget(btn_fetch_single)
            layout_btns.addWidget(btn_remove_single)

            layout_card.addWidget(lbl_title)
            layout_card.addWidget(lbl_addr)
            layout_card.addWidget(lbl_pnu)
            layout_card.addLayout(layout_btns)

            layout_cards.addWidget(card)

        self.layout_cards_container.addLayout(layout_cards)

    def handle_remove_property(self, prop: dict):
        """선택한 부동산 삭제 처리 및 대시보드 갱신"""
        label = prop["label"]
        reply = QMessageBox.question(
            self, "부동산 삭제 확인",
            f"정말로 '{label}' ({prop['dongNm']}동 {prop['hoNm']}호) 부동산을 목록 및 이력 데이터에서 삭제하시겠습니까?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            success = self.logic.remove_property(label)
            if success:
                if label in self.active_labels:
                    self.active_labels.remove(label)

                self.render_property_cards()
                self.populate_year_combo()
                self.refresh_dashboard()

                self.statusBar_info.showMessage(f"[{label}] 부동산 데이터가 정상 삭제되었습니다.", 5000)
                QMessageBox.information(self, "삭제 완료", f"'{label}' 부동산 데이터가 성공적으로 제거되었습니다.")

    def handle_fetch_single_property(self, prop: dict):
        """선택한 개별 부동산의 API 실데이터 조회 및 알람 처리"""
        label = prop["label"]
        self.statusBar_info.showMessage(f"[{label}] 브이월드 API 데이터 조회 및 업데이트 실행 중...")

        current_year = datetime.now().year
        cnt = self.logic.fetch_all_years_for_property(prop, start_year=2020, end_year=current_year)

        if cnt == 0:
            self.statusBar_info.showMessage(f"⚠️ [{label}] 브이월드 API 데이터 조회 실패", 5000)
            QMessageBox.warning(
                self, "조회 실패 알림",
                f"⚠️ [{label}] 브이월드 API 조회가 진행되지 않았습니다.\n\n"
                f"사유:\n"
                f"1. 입력된 주소('{prop['search_addr']}')로 PNU 코드를 검색할 수 없습니다.\n"
                f"2. 국토교통부 브이월드 서버에 해당 부동산 공시가격 응답 데이터가 없습니다.\n\n"
                f"주소를 정확하게 입력했는지 확인해 주세요."
            )
            return

        if label not in self.active_labels:
            self.active_labels.append(label)

        self.populate_year_combo()
        self.refresh_dashboard()

        self.statusBar_info.showMessage(f"조회 완료: [{label}] 실제 API 데이터가 업데이트되었습니다!", 5000)
        QMessageBox.information(self, "조회 및 업데이트 완료", f"[{label}] 2020년~{current_year}년 공시가격 데이터 수집 완료!\n테이블과 차트에 업데이트되었습니다.")

    def append_log(self, text: str):
        """실시간 로그 위젯에 로그 추가"""
        self.txt_log_viewer.append(text)
        self.txt_log_viewer.ensureCursorVisible()
        QApplication.processEvents()

    def populate_year_combo(self):
        """연도 선택 ComboBox 갱신"""
        self.cmb_target_year.clear()
        years = self.logic.get_available_years()
        self.cmb_target_year.addItem("전체 (전체 누적)", None)
        for year in reversed(years):
            self.cmb_target_year.addItem(f"{year}년까지 누적", year)

    def handle_add_custom_property(self):
        """신규 아파트 등록 및 2020년~현재 데이터 API 자동 조회"""
        name = self.txt_name.text().strip()
        addr = self.txt_addr.text().strip()
        dong = self.txt_dong.text().strip()
        ho = self.txt_ho.text().strip()

        if not name or not addr or not dong or not ho:
            QMessageBox.warning(self, "입력 오류", "별칭, 주소, 동, 호수를 모두 정확히 입력해 주세요.")
            return

        new_prop = {
            "label": name,
            "search_addr": addr,
            "pnu": "",
            "dongNm": dong,
            "hoNm": ho
        }

        self.statusBar_info.showMessage(f"'{name}' 2020년~현재 실데이터 자동 조회 중...")

        current_year = datetime.now().year
        cnt = self.logic.fetch_all_years_for_property(new_prop, start_year=2020, end_year=current_year)

        if cnt == 0:
            self.statusBar_info.showMessage(f"⚠️ [{name}] 데이터 조회 실패로 등록 취소됨", 5000)
            QMessageBox.warning(
                self, "신규 등록 및 API 조회 실패",
                f"⚠️ [{name}] 입력한 주소('{addr}')로 브이월드 API 데이터를 조회할 수 없습니다.\n\n"
                f"조회가 불가능한 주소이므로 부동산 신규 등록이 취소되었습니다.\n"
                f"도로명/지번 주소를 다시 확인 후 시도해 주세요."
            )
            return

        if not any(p["label"] == name for p in self.logic.properties):
            self.logic.properties.append(new_prop)

        if name not in self.active_labels:
            self.active_labels.append(name)

        self.render_property_cards()
        self.populate_year_combo()
        self.refresh_dashboard()

        self.statusBar_info.showMessage(f"[{name}] 등록 완료! API 데이터가 차트에 반영되었습니다.", 5000)
        QMessageBox.information(
            self, "신규 아파트 등록 완료",
            f"[{name}] ({addr} {dong}동 {ho}호) 등록 완료!\n2020년~{current_year}년 공시가 실데이터가 테이블과 차트에 반영되었습니다."
        )

    def handle_fetch_all_properties(self):
        """전체 부동산 일괄 API 조회 및 알림"""
        current_year = datetime.now().year

        logger.info(f"==================================================")
        logger.info(f"📊 전체 등록 부동산 ({len(self.logic.properties)}개) 2020~{current_year}년 API 수집 일괄 실행")

        success_count = 0
        fail_labels = []

        for prop in self.logic.properties:
            cnt = self.logic.fetch_all_years_for_property(prop, start_year=2020, end_year=current_year)
            if cnt > 0:
                success_count += 1
                if prop["label"] not in self.active_labels:
                    self.active_labels.append(prop["label"])
            else:
                fail_labels.append(prop["label"])

        self.render_property_cards()
        self.populate_year_combo()
        self.refresh_dashboard()

        if fail_labels:
            msg = f"일부 부동산({len(fail_labels)}건: {', '.join(fail_labels)})은 API 조회 실패로 제외되고, 정상 수집된 {success_count}건이 업데이트되었습니다."
            self.statusBar_info.showMessage(f"⚠️ {msg}", 5000)
            QMessageBox.warning(self, "일괄 조회 부분 완료 알림", f"⚠️ {msg}")
        else:
            self.statusBar_info.showMessage("전체 부동산 일괄 조회 및 테이블/차트 업데이트 완료!", 5000)
            QMessageBox.information(
                self, "전수 업데이트 완료",
                f"전체 부동산 2020년~{current_year}년 공시가격 실데이터가 테이블과 차트에 성공적으로 일괄 업데이트되었습니다!"
            )

    def handle_filter_year(self):
        """선택 연도까지 필터링 적용"""
        selected_year = self.cmb_target_year.currentData()
        self.refresh_dashboard(selected_year)

    def refresh_dashboard(self, up_to_year: int | None = None):
        """테이블과 차트 대시보드 새로고침"""
        try:
            active = self.active_labels if self.active_labels else None
            pivot_df = self.logic.get_pivot_table(up_to_year, active_labels=active)
            self.update_table(pivot_df)
            self.update_chart(pivot_df)
        except Exception as e:
            logger.error(f"대시보드 갱신 에러: {e}")

    def update_table(self, pivot_df: pd.DataFrame):
        """QTableWidget 표출 (열=연도, 행=부동산 및 합계/변동항목)"""
        if pivot_df.empty:
            self.tbl_price_history.setRowCount(0)
            self.tbl_price_history.setColumnCount(0)
            return

        years = [int(y) for y in pivot_df.index]
        prop_labels = [p["label"] for p in self.logic.properties if p["label"] in pivot_df.columns]

        headers = ["부동산 / 항목"] + [f"{y}년" for y in years]
        row_items = prop_labels + ["Total (합계)", "전년대비 변동액", "변동률 (%)"]

        self.tbl_price_history.setRowCount(len(row_items))
        self.tbl_price_history.setColumnCount(len(headers))
        self.tbl_price_history.setHorizontalHeaderLabels(headers)

        for row_idx, label in enumerate(row_items):
            item_label = QTableWidgetItem(label)
            is_special = label in ["Total (합계)", "전년대비 변동액", "변동률 (%)"]
            item_label.setTextAlignment(Qt.AlignmentFlag.AlignCenter if is_special else Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            item_label.setFont(QFont("Malgun Gothic", 9, QFont.Weight.Bold))
            if label == "Total (합계)":
                item_label.setBackground(QColor("#E7F1FF"))
            self.tbl_price_history.setItem(row_idx, 0, item_label)

        for col_idx, year in enumerate(years, start=1):
            year_row = pivot_df.loc[year]

            for row_idx, prop_name in enumerate(prop_labels):
                price = year_row.get(prop_name)
                val_str = f"{price / 1e8:.2f}억" if pd.notna(price) and price > 0 else "-"
                item_price = QTableWidgetItem(val_str)
                item_price.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.tbl_price_history.setItem(row_idx, col_idx, item_price)

            total_row_idx = len(prop_labels)
            total_val = year_row.get("Total", 0)
            val_total_str = f"{total_val / 1e8:.2f}억" if pd.notna(total_val) and total_val > 0 else "-"
            item_total = QTableWidgetItem(val_total_str)
            item_total.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            item_total.setFont(QFont("Malgun Gothic", 9, QFont.Weight.Bold))
            item_total.setBackground(QColor("#E7F1FF"))
            self.tbl_price_history.setItem(total_row_idx, col_idx, item_total)

            diff_row_idx = len(prop_labels) + 1
            diff_val = year_row.get("Total_Diff")
            if pd.notna(diff_val):
                diff_str = f"{diff_val / 1e8:+.2f}억"
                color_diff = QColor("#D63384") if diff_val > 0 else (QColor("#0D6EFD") if diff_val < 0 else QColor("#212529"))
            else:
                diff_str = "-"
                color_diff = QColor("#6C757D")
            item_diff = QTableWidgetItem(diff_str)
            item_diff.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            item_diff.setForeground(color_diff)
            self.tbl_price_history.setItem(diff_row_idx, col_idx, item_diff)

            rate_row_idx = len(prop_labels) + 2
            rate_val = year_row.get("Total_Rate")
            if pd.notna(rate_val):
                rate_str = f"{rate_val:+.1f}%"
                color_rate = QColor("#DC3545") if rate_val > 0 else (QColor("#0D6EFD") if rate_val < 0 else QColor("#212529"))
            else:
                rate_str = "-"
                color_rate = QColor("#6C757D")
            item_rate = QTableWidgetItem(rate_str)
            item_rate.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item_rate.setFont(QFont("Malgun Gothic", 9, QFont.Weight.Bold))
            item_rate.setForeground(color_rate)
            self.tbl_price_history.setItem(rate_row_idx, col_idx, item_rate)

    def update_chart(self, pivot_df: pd.DataFrame):
        """Matplotlib 그래프 표출"""
        self.fig_chart.clear()

        if pivot_df.empty:
            self.canvas_chart.draw()
            return

        ax1 = self.fig_chart.add_subplot(2, 1, 1)
        ax2 = self.fig_chart.add_subplot(2, 1, 2)

        years_num = [int(y) for y in pivot_df.index]
        prop_labels = [p["label"] for p in self.logic.properties if p["label"] in pivot_df.columns]
        colors = ['#0D6EFD', '#198754', '#D63384', '#6F42C1', '#FD7E14', '#20C997', '#E83E8C']
        markers = ['o', 's', '^', 'D', 'v', 'p', '*']

        # 1. 개별 부동산 추이선
        for idx, label in enumerate(prop_labels):
            if label in pivot_df.columns:
                prices = pivot_df[label] / 100000000
                ax1.plot(
                    years_num, prices, label=label, marker=markers[idx % len(markers)],
                    color=colors[idx % len(colors)], linewidth=2.2, markersize=6
                )
                for x_val, y_val in zip(years_num, prices):
                    if pd.notna(y_val) and y_val > 0:
                        ax1.annotate(
                            f"{y_val:.2f}억", (x_val, y_val),
                            textcoords="offset points", xytext=(0, 6), ha='center', fontsize=8
                        )

        ax1.set_title("🏢 보유 부동산별 연도별 공시가격 추이 (억원)", fontsize=11, fontweight='bold', pad=8)
        ax1.set_ylabel("공시가격 (억원)", fontsize=9)
        ax1.grid(True, linestyle='--', alpha=0.5)
        ax1.legend(loc='upper left', fontsize=8)

        # 2. Total (합계) 막대 그래프
        totals = pivot_df['Total'] / 100000000
        bars = ax2.bar(years_num, totals, color='#0D6EFD', alpha=0.75, width=0.45, label='Total 합계')
        for bar in bars:
            height = bar.get_height()
            if pd.notna(height) and height > 0:
                ax2.annotate(
                    f"{height:.2f}억", (bar.get_x() + bar.get_width() / 2, height),
                    textcoords="offset points", xytext=(0, 4), ha='center', fontsize=8, fontweight='bold'
                )

        ax2.set_title("📊 전체 부동산 총 공시가격 합계 (Total)", fontsize=11, fontweight='bold', pad=8)
        ax2.set_xlabel("연도", fontsize=9)
        ax2.set_ylabel("총 합계 (억원)", fontsize=9)
        ax2.grid(True, linestyle='--', alpha=0.5)

        self.fig_chart.tight_layout()
        self.canvas_chart.draw()


# 기존 코드 호환성용 에일리어스 (ScientificCalculatorGUI)
ScientificCalculatorGUI = ApartmentPriceGUI


def main():
    app = QApplication(sys.argv)
    window = ApartmentPriceGUI()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
