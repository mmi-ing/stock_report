"""Stock Lab — Streamlit 웹 앱."""
from __future__ import annotations

import os

import streamlit as st
import streamlit.components.v1 as components

from stocklab import indicators, output
from stocklab.analysts import stock as analyst_stock
from stocklab.data import yahoo
from stocklab.render import renderer
from stocklab.router import parse

st.set_page_config(page_title="Stock Lab", page_icon="📊", layout="wide")

# ── 비밀번호 게이트 ──────────────────────────────────────────────────
APP_PASSWORD = os.environ.get("APP_PASSWORD", "stocklab")

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.title("📊 Stock Lab")
    pw = st.text_input("비밀번호", type="password")
    if st.button("입장"):
        if pw == APP_PASSWORD:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("비밀번호가 틀렸습니다.")
    st.stop()

# ── 메인 앱 ──────────────────────────────────────────────────────────
st.title("📊 Stock Lab")
st.caption("개별 종목 · 테마 발굴 · 종목 비교 리포트")

col1, col2 = st.columns([4, 1])
with col1:
    query = st.text_input(
        "종목/테마 검색",
        placeholder="NVDA  /  005930  /  AI 반도체  /  NVDA vs AMD",
        label_visibility="collapsed",
    )
with col2:
    use_ai = st.toggle("AI 서술", value=False)

run = st.button("리포트 생성", type="primary", use_container_width=True)

if run and query.strip():
    spec = parse(query.strip())

    if spec.mode == "ambiguous":
        st.warning(f"'{query}' 가 모호합니다. 더 구체적으로 입력해 주세요.")
        for opt in spec.ambiguous_options:
            st.write(f"  - {opt}")
        st.stop()

    with st.spinner("데이터 수집 · 리포트 생성 중..."):
        try:
            if spec.mode == "A":
                assert spec.ticker and spec.asset_class
                if spec.asset_class == "kr_stock" and "." not in spec.ticker:
                    snap = yahoo.fetch_kr_with_fallback(spec.ticker)
                else:
                    snap = yahoo.fetch(spec.ticker, spec.asset_class)

                if snap.price is None and snap.ohlc.empty:
                    st.error(f"'{query}' 데이터를 가져오지 못했습니다.")
                    st.stop()

                ind = indicators.compute(snap.ohlc) if not snap.ohlc.empty else None
                if ind is None:
                    st.error("OHLC 데이터 부족으로 리포트를 생성할 수 없습니다.")
                    st.stop()

                narrative_data = None
                if use_ai:
                    from stocklab import narrative as narr_mod
                    narrative_data = narr_mod.generate(snap, ind, weights=spec.weights)

                ctx = analyst_stock.build_context(
                    snap, ind, weights=spec.weights, narrative_override=narrative_data
                )
                html = renderer.render("mode_a.html.j2", ctx)

            elif spec.mode == "B":
                from stocklab.analysts import theme as analyst_theme
                ctx = analyst_theme.build_context(
                    theme=spec.theme or query, candidates=spec.candidates, weights=spec.weights
                )
                html = renderer.render("mode_b.html.j2", ctx)

            elif spec.mode == "C":
                from stocklab.analysts import compare as analyst_compare
                ctx = analyst_compare.build_context(
                    left_raw=spec.left or "", right_raw=spec.right or "", weights=spec.weights
                )
                html = renderer.render("mode_c.html.j2", ctx)

            else:
                st.error("알 수 없는 모드입니다.")
                st.stop()

        except RuntimeError as e:
            st.error(str(e))
            st.stop()

    components.html(html, height=900, scrolling=True)

    st.download_button(
        label="HTML 다운로드",
        data=html,
        file_name=f"{query.strip().replace(' ', '_')}_report.html",
        mime="text/html",
    )
