import datetime
from io import BytesIO

import streamlit as st
import pandas as pd
import FinanceDataReader as fdr
import matplotlib.pyplot as plt
import koreanize_matplotlib
import plotly.graph_objects as go


@st.cache_data(ttl=60 * 60 * 24)
def get_krx_company_list() -> pd.DataFrame:
    url = "http://kind.krx.co.kr/corpgeneral/corpList.do?method=download&searchType=13"
    df = pd.read_html(url, header=0, encoding="EUC-KR")[0]
    df = df[["회사명", "종목코드"]].copy()
    df["종목코드"] = df["종목코드"].apply(lambda x: f"{x:06}")
    return df


def get_stock_code_by_company(company_name: str) -> str:
    company_name = company_name.strip()

    # 종목코드 직접 입력한 경우
    if company_name.isdigit() and len(company_name) == 6:
        return company_name

    df = get_krx_company_list()
    result = df[df["회사명"] == company_name]["종목코드"]

    if result.empty:
        raise ValueError(f"'{company_name}'을(를) 찾을 수 없습니다.")
    return result.iloc[0]


st.sidebar.title("📈 국내 주가 조회")

company_name = st.sidebar.text_input("조회할 회사명 또는 종목코드")

selected_dates = st.sidebar.date_input(
    "조회 기간 선택",
    value=[
        datetime.date.today() - datetime.timedelta(days=30),
        datetime.date.today(),
    ],
)

confirm_btn = st.sidebar.button("조회하기")

if confirm_btn:
    if not company_name:
        st.warning("회사명을 입력하세요.")
        st.stop()

    if len(selected_dates) != 2:
        st.warning("시작일과 종료일을 모두 선택하세요.")
        st.stop()

    try:
        with st.spinner("데이터를 불러오는 중..."):
            stock_code = get_stock_code_by_company(company_name)

            start_date = selected_dates[0].strftime("%Y%m%d")
            end_date = selected_dates[1].strftime("%Y%m%d")

            price_df = fdr.DataReader(stock_code, start_date, end_date)

        if price_df.empty:
            st.info("해당 기간의 주가 데이터가 없습니다.")
            st.stop()

        # index → Date 컬럼으로 변환
        price_df = price_df.reset_index()

        st.subheader(f"📊 [{company_name}] 주가 데이터")
        st.dataframe(price_df.tail(10), use_container_width=True)

        fig, ax = plt.subplots(figsize=(12, 5))
        ax.plot(price_df["Date"], price_df["Close"], color="red")
        ax.set_title(f"{company_name} 종가 추이", fontsize=14)
        ax.grid(True)
        st.pyplot(fig)

        fig = go.Figure(
            data=[
                go.Candlestick(
                    x=price_df["Date"],
                    open=price_df["Open"],
                    high=price_df["High"],
                    low=price_df["Low"],
                    close=price_df["Close"],
                    increasing_line_color= 'red', decreasing_line_color= 'blue'
                )
            ]
        )

        fig.update_layout(
            title=f"{company_name} 캔들차트",
            xaxis_title="Date",
            yaxis_title="Price",
            xaxis_rangeslider_visible=False,

        )

        st.plotly_chart(fig, use_container_width=True)

        output = BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            price_df.to_excel(writer, index=False, sheet_name="Price")

        st.download_button(
            label="📥 엑셀 파일 다운로드",
            data=output.getvalue(),
            file_name=f"{company_name}_주가.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    except Exception as e:
        st.error(f"오류 발생: {e}")
