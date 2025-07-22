# app.py
import streamlit as st
import pandas as pd
import calendar
from datetime import date
from dateutil.relativedelta import relativedelta
import warnings

warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl")

# Relevante Gruppen
RELEVANT_GROUPS = [
    "Firmendaten Manager", "Website", "SEO", "Google Ads",
    "Postings", "Superkombis", "Social Media Werbeanzeigen"
]

# Monatsliste
def last_12_full_months(ref_date: date):
    last_full = ref_date.replace(day=1) - relativedelta(days=1)
    months = []
    for i in range(12):
        start = (last_full - relativedelta(months=i)).replace(day=1)
        end = start.replace(day=calendar.monthrange(start.year, start.month)[1])
        months.append((start, end))
    return list(reversed(months))

# Gruppenzuordnung
def map_group(row):
    cat = row['Produktkategorie']
    if cat != "Social Media":
        return cat
    prod = row['Produkt']
    postings = {
        "Social Media Postingpaket 12 Postings",
        "Social Media Postingpaket 24 Postings",
        "Social Media Postingpaket 52 Postings"
    }
    superk = {
        "Social Media SUPERKOMBI 12er", "Social Media SUPERKOMBI 12er (alt)",
        "Social Media SUPERKOMBI 24er", "Social Media SUPERKOMBI 24er (alt)",
        "Social Media SUPERKOMBI 52er", "Social Media SUPERKOMBI 52er (alt)"
    }
    ads = {"Social Media Werbeanzeigen Kampagnenbudget"}
    if prod in postings:
        return "Postings"
    if prod in superk:
        return "Superkombis"
    if prod in ads:
        return "Social Media Werbeanzeigen"
    return "Unbekannt"

# Hauptlogik
def churn_auswerten(df: pd.DataFrame):
    df = df[df['Abo'].astype(str).str.lower().isin(['ja','yes','true','1'])].copy()
    df['ProductGroup'] = df.apply(map_group, axis=1)
    df = df[df['ProductGroup'].isin(RELEVANT_GROUPS)]
    df['Beginn'] = pd.to_datetime(df['Beginn'], errors='coerce')
    df['Ende'] = pd.to_datetime(df['Ende'], errors='coerce')

    ## Monats-Churn (12 Monate)
    months = last_12_full_months(date.today())
    records = []
    for group, gdf in df.groupby('ProductGroup'):
        for start_ts, end_ts in months:
            active = gdf[(gdf['Beginn'] < start_ts) & ((gdf['Ende'].isna()) | (gdf['Ende'] >= start_ts))]
            churned = gdf[(gdf['Ende'] >= start_ts) & (gdf['Ende'] <= end_ts)]
            rate = (len(churned) / len(active) * 100) if len(active) > 0 else 0.0
            records.append({'Monat': start_ts.strftime("%Y-%m"), 'Gruppe': group, 'ChurnRate (%)': round(rate, 1)})
    df_monatlich = pd.DataFrame(records)
    df_monat_pivot = df_monatlich.pivot(index='Monat', columns='Gruppe', values='ChurnRate (%)').fillna(0)
    df_avg = df_monatlich.groupby('Gruppe')['ChurnRate (%)'].mean().round(1).reset_index()

    ## Jahres-Churn (12M)
    today = pd.Timestamp.today()
last_full = today.replace(day=1) - pd.Timedelta(days=1)
start = (last_full - relativedelta(months=11)).replace(day=1)
end = last_full
ann_records = []
    for group, gdf in df.groupby('ProductGroup'):
        active = gdf[(gdf['Beginn'] < pd.Timestamp(start)) & ((gdf['Ende'].isna()) | (gdf['Ende'] >= pd.Timestamp(start)))]
        churned = gdf[(gdf['Ende'] >= pd.Timestamp(start)) & (gdf['Ende'] <= pd.Timestamp(end))]
        rate = (len(churned) / len(active) * 100) if len(active) > 0 else 0.0
        ann_records.append({'Gruppe': group, 'Jahres-Churn (12M)': round(rate, 1)})
    df_12m = pd.DataFrame(ann_records)

    ## Kalenderjahre
    start_year = df['Beginn'].dt.year.min()
    end_year = today.year
    yearly_records = []
    for year in range(start_year, end_year + 1):
        start = pd.Timestamp(f"{year}-01-01")
        end = pd.Timestamp(date.today()) if year == end_year else pd.Timestamp(f"{year}-12-31")
        for group, gdf in df.groupby('ProductGroup'):
            active_start = gdf[(gdf['Beginn'] < start) & ((gdf['Ende'].isna()) | (gdf['Ende'] >= start))]
            churned_year = active_start[(active_start['Ende'] >= start) & (active_start['Ende'] <= end)]
            rate = (len(churned_year) / len(active_start) * 100) if len(active_start) > 0 else 0.0
            yearly_records.append({'Jahr': year, 'Gruppe': group, 'ChurnRate (%)': round(rate, 1)})
    df_jahr = pd.DataFrame(yearly_records)
    df_jahr_pivot = df_jahr.pivot(index='Jahr', columns='Gruppe', values='ChurnRate (%)').fillna(0)

    return df_monat_pivot, df_avg, df_12m, df_jahr_pivot

# Streamlit UI
st.set_page_config(layout="wide")
st.title("Churn-Analyse – Edelweiss-Demo")

file = st.file_uploader("Lade eine Excel-Datei hoch", type=["xlsx"])

if file:
    try:
        df = pd.read_excel(file)
        monats_churn, avg_churn, churn_12m, kalender_churn = churn_auswerten(df)

        st.subheader("1. Monats-Churn (pivotiert, letzte 12 Monate)")
        st.dataframe(monats_churn, use_container_width=True)

        st.subheader("2. Ø 12-Monats-Churn pro Gruppe")
        st.dataframe(avg_churn, use_container_width=True)

        st.subheader("3. Jahres-Churn der letzten 12 Monate")
        st.dataframe(churn_12m, use_container_width=True)

        st.subheader("4. Jahres-Churn je Kalenderjahr")
        st.dataframe(kalender_churn, use_container_width=True)

    except Exception as e:
        st.error(f"Fehler beim Verarbeiten der Datei: {e}")
