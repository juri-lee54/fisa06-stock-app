import datetime
from io import BytesIO

import streamlit as st
import pandas as pd
import FinanceDataReader as fdr
import plotly.graph_objects as go


@st.cache_data(ttl=60 * 60 * 24)
def get_krx_company_list() -> pd.DataFrame:
    url = "http://kind.krx.co.kr/corpgeneral/corpList.do?method=download&searchType=13"
    df = pd.read_html(url, header=0, encoding="EUC-KR")[0]
    df = df[["회사명", "종목코드"]].copy()
    df["종목코드"] = df["종목코드"].apply(lambda x: f"{x:06}")
    return df


def get_stock_code_by_company(company_name: str) -> str:
    df = get_krx_company_list()
    result = df[df["회사명"] == company_name]["종목코드"]
    if result.empty:
        raise ValueError(f"'{company_name}'을(를) 찾을 수 없습니다.")
    return result.iloc[0]

st.sidebar.title("📈 국내 주가 비교 분석")

company_df = get_krx_company_list()

selected_companies = st.sidebar.multiselect(
    "비교할 기업 선택 (최대 3개)",
    options=company_df["회사명"].tolist(),
    max_selections=3,
)

selected_dates = st.sidebar.date_input(
    "조회 기간 선택",
    value=[
        datetime.date.today() - datetime.timedelta(days=30),
        datetime.date.today(),
    ],
)

show_candle = st.sidebar.checkbox("개별 기업 캔들차트 표시", value=False)
confirm_btn = st.sidebar.button("조회하기")


if confirm_btn:
    if not selected_companies:
        st.warning("최소 1개 이상의 기업을 선택하세요.")
        st.stop()

    if len(selected_dates) != 2:
        st.warning("시작일과 종료일을 모두 선택하세요.")
        st.stop()

    start_date = selected_dates[0].strftime("%Y%m%d")
    end_date = selected_dates[1].strftime("%Y%m%d")

    price_data = {}
    failed_companies = []

    try:
        # 데이터 수집 
        with st.spinner("데이터를 불러오는 중..."):
            for company in selected_companies:
                try:
                    code = get_stock_code_by_company(company)
                    df = fdr.DataReader(code, start_date, end_date)

                    if df.empty:
                        failed_companies.append(company)
                        continue

                    df = df.reset_index()
                    price_data[company] = df

                except Exception:
                    failed_companies.append(company)

        if failed_companies:
            st.warning(
                "다음 기업은 데이터를 불러올 수 없습니다:\n- "
                + "\n- ".join(failed_companies)
            )

        if not price_data:
            st.error("조회 가능한 데이터가 없습니다.")
            st.stop()

        #  정규화 비교
        st.subheader("📊 정규화(100 기준) 종가 비교")

        fig_norm = go.Figure()

        for company, df in price_data.items():
            base = df["Close"].iloc[0]
            df["Normalized"] = df["Close"] / base * 100

            fig_norm.add_trace(
                go.Scatter(
                    x=df["Date"],
                    y=df["Normalized"],
                    mode="lines",
                    name=company,
                )
            )

        fig_norm.update_layout(
            title="정규화 종가 비교 (시작일 = 100)",
            xaxis_title="Date",
            yaxis_title="Normalized Price",
            hovermode="x unified",
        )

        st.plotly_chart(fig_norm, use_container_width=True)

        # 수익률 테이블 
        st.subheader("📈 기간 수익률 비교")

        returns = []
        for company, df in price_data.items():
            ret = (df["Close"].iloc[-1] / df["Close"].iloc[0] - 1) * 100
            returns.append(
                {
                    "기업명": company,
                    "시작 종가": round(df["Close"].iloc[0], 2),
                    "마지막 종가": round(df["Close"].iloc[-1], 2),
                    "수익률(%)": round(ret, 2),
                }
            )

        st.dataframe(
            pd.DataFrame(returns).sort_values("수익률(%)", ascending=False),
            use_container_width=True,
        )

        #  캔들차트 
        if show_candle:
            st.markdown( '---' )
            st.subheader("📊 개별 기업 캔들차트")

            for company, df in price_data.items():
                fig = go.Figure(
                    data=[
                        go.Candlestick(
                            x=df["Date"],
                            open=df["Open"],
                            high=df["High"],
                            low=df["Low"],
                            close=df["Close"],
                            increasing_line_color="red",
                            decreasing_line_color="blue",
                        )
                    ]
                )

                fig.update_layout(
                    title=f"{company} 캔들차트",
                    xaxis_rangeslider_visible=False,
                )

                st.plotly_chart(fig, use_container_width=True)


        if st.button("기업별 데이터테이블 보기"):
            st.markdown( '---' )
            for company, df in price_data.items():
                st.write(df)
                st.dataframe(df.tail(10), use_container_width=True)

        # 엑셀 다운로드 
        output = BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            for company, df in price_data.items():
                df.to_excel(writer, index=False, sheet_name=company[:30])

        st.download_button(
            "📥 엑셀 다운로드 (기업별 시트)",
            data=output.getvalue(),
            file_name="주가_비교_분석.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    except Exception as e:
        st.error(f"오류 발생: {e}")
