import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# Simple page config
st.set_page_config(page_title="Aadhaar Lifecycle Analytics", page_icon="📊", layout="wide")

# Load data
@st.cache_data
def load_data():
    import os
    current_dir = os.path.dirname(os.path.abspath(__file__))
    data_path = os.path.join(current_dir, "data/processed/lifecycle_aggregated.csv")
    return pd.read_csv(data_path, parse_dates=["date"])

df = load_data()

# Normalize state names to avoid duplicates/variants
def _canonicalize_state_column(df: pd.DataFrame) -> pd.DataFrame:
    s = df['state'].astype(str).str.strip()
    s = s.str.replace(r"\s+", " ", regex=True)
    s = s.str.replace("&", "and", regex=False)
    s = s.str.lower()

    canonical_map = {
        "andaman and nicobar islands": "Andaman and Nicobar Islands",
        "jammu and kashmir": "Jammu and Kashmir",
        "west bengal": "West Bengal",
        "westbengal": "West Bengal",
        "uttarakhand": "Uttarakhand",
    }

    def proper_case(name: str) -> str:
        return " ".join([w.capitalize() if w != "and" else "and" for w in name.split()])

    df['state_clean'] = s.apply(lambda x: canonical_map.get(x, proper_case(x)))
    return df

df = _canonicalize_state_column(df)

# Header
st.title("📊 Aadhaar Lifecycle Analytics Dashboard")
st.caption("UIDAI Data Hackathon 2026 · Lifecycle-based Decision Support System")

# Sidebar controls
with st.sidebar:
    st.header("🎯 Controls")
    # Show only valid, deduplicated state names
    state_options = sorted(list(set([x for x in df["state_clean"].dropna().unique() if not str(x).isdigit() and len(str(x)) > 2])))
    state = st.selectbox("🗺️ State", state_options)

    min_date = pd.to_datetime(df['date'].min()).date()
    max_date = pd.to_datetime(df['date'].max()).date()
    date_range = st.date_input("📅 Date Range", value=(min_date, max_date), min_value=min_date, max_value=max_date)

    st.markdown("---")
    with st.expander("ℹ️ Metrics Guide"):
        st.markdown(
            """
            - **Avg Enrolment**: Mean of `total_enrolment` in the selected period.
            - **DUI (Demographic Update Intensity)**: `demographic_updates ÷ total_enrolment`.
            - **BUBI (Biometric Update Burden Index)**: `biometric_updates ÷ total_enrolment`.
            - **Delta vs National**: KPI minus the national average for the same metric.
            """
        )

# Filter data
filtered = df[df["state_clean"] == state].copy()
if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
    start_date = pd.Timestamp(date_range[0])
    end_date = pd.Timestamp(date_range[1])
else:
    start_date = pd.Timestamp(df['date'].min())
    end_date = pd.Timestamp(df['date'].max())

filtered = filtered[(filtered['date'] >= start_date) & (filtered['date'] <= end_date)].sort_values("date")
if filtered.empty:
    st.warning("No data for the selected filters. Adjust state or date range.")
    st.stop()

# National benchmarks
@st.cache_data
def get_national_benchmarks(df):
    return df.groupby("date")[['DUI', 'BUBI']].mean().mean()

national_avg = get_national_benchmarks(df)

# KPIs
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("📝 Avg Enrolment", f"{int(filtered['total_enrolment'].mean()):,}")
with col2:
    dui_mean = round(filtered["DUI"].mean(), 3)
    st.metric("🔄 DUI", dui_mean, delta=round(dui_mean - national_avg["DUI"], 3))
with col3:
    bubi_mean = round(filtered["BUBI"].mean(), 3)
    st.metric("👤 BUBI", bubi_mean, delta=round(bubi_mean - national_avg["BUBI"], 3), delta_color="inverse")
with col4:
    total_updates = int(filtered['demographic_updates'].sum() + filtered['biometric_updates'].sum())
    st.metric("📊 Total Updates", f"{total_updates:,}")

# Metrics details
st.subheader("ℹ️ Metrics Details")
latest = filtered.iloc[-1]
latest_date = latest['date'].date()

# Avoid divide-by-zero
den = latest['total_enrolment'] if latest['total_enrolment'] else None
calc_dui_latest = (latest['demographic_updates'] / den) if den else float('nan')
calc_bubi_latest = (latest['biometric_updates'] / den) if den else float('nan')

d1, d2 = st.columns(2)
with d1:
    st.metric("Latest Enrolment", f"{int(latest['total_enrolment']):,}")
    st.metric("Latest Demo Updates", f"{int(latest['demographic_updates']):,}")
    st.metric("Latest Bio Updates", f"{int(latest['biometric_updates']):,}")
with d2:
    st.metric("Latest DUI (reported)", f"{latest['DUI']:.3f}")
    st.caption(f"Computed: {calc_dui_latest:.3f} on {latest_date}")
    st.metric("Latest BUBI (reported)", f"{latest['BUBI']:.3f}")
    st.caption(f"Computed: {calc_bubi_latest:.3f} on {latest_date}")

st.markdown(
    f"Average DUI: **{filtered['DUI'].mean():.3f}** · National: **{national_avg['DUI']:.3f}** | "
    f"Average BUBI: **{filtered['BUBI'].mean():.3f}** · National: **{national_avg['BUBI']:.3f}**"
)

# Charts: enrolment and updates
st.subheader("📈 Enrolment and Updates Over Time")
fig = go.Figure()
fig.add_trace(go.Scatter(x=filtered['date'], y=filtered['total_enrolment'], name='Total Enrolment', mode='lines+markers'))
fig.add_trace(go.Scatter(x=filtered['date'], y=filtered['demographic_updates'], name='Demographic Updates', mode='lines+markers'))
fig.add_trace(go.Scatter(x=filtered['date'], y=filtered['biometric_updates'], name='Biometric Updates', mode='lines+markers'))
st.plotly_chart(fig, width='stretch')

# DUI/BUBI ratios
st.subheader("📉 DUI and BUBI")
fig_ratios = go.Figure()
fig_ratios.add_trace(go.Scatter(x=filtered['date'], y=filtered['DUI'], name='DUI'))
fig_ratios.add_trace(go.Scatter(x=filtered['date'], y=filtered['BUBI'], name='BUBI'))
fig_ratios.add_hline(y=national_avg['DUI'], line_dash="dash", line_color="gray")
fig_ratios.add_hline(y=national_avg['BUBI'], line_dash="dash", line_color="gray")
st.plotly_chart(fig_ratios, width='stretch')

# Comparison tab (optional simple)
st.subheader("🌍 National Comparison")
all_states = df.groupby("state_clean")[['DUI', 'BUBI']].mean().reset_index()
fig_scatter = px.scatter(all_states, x='DUI', y='BUBI', hover_name='state_clean', color='BUBI', size='BUBI', color_continuous_scale='RdYlGn_r')
selected_state_data = all_states[all_states['state_clean'] == state]
if not selected_state_data.empty:
    fig_scatter.add_trace(go.Scatter(x=selected_state_data['DUI'], y=selected_state_data['BUBI'], mode='markers', marker=dict(size=18, color='red', symbol='star'), name=f'{state}'))
fig_scatter.add_hline(y=national_avg['BUBI'], line_dash="dash", line_color="gray")
fig_scatter.add_vline(x=national_avg['DUI'], line_dash="dash", line_color="gray")
st.plotly_chart(fig_scatter, width='stretch')

with st.sidebar:
    st.download_button(
        "⬇️ Download filtered CSV",
        data=filtered.to_csv(index=False).encode("utf-8"),
        file_name=f"filtered_{state}_{start_date.date()}_{end_date.date()}.csv",
        mime="text/csv"
    )

st.caption("Built for UIDAI Data Hackathon 2026")
