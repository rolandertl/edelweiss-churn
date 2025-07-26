import streamlit as st
import pandas as pd
import calendar
from datetime import date
from dateutil.relativedelta import relativedelta
import warnings

warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl")

RELEVANT_GROUPS = [
    "Firmendaten Manager", "Website", "SEO", "Google Ads",
    "Postings", "Superkombis", "Social Media Werbeanzeigen"
]

def last_12_full_months(ref_date: pd.Timestamp):
    last_full = ref_date.replace(day=1) - pd.Timedelta(days=1)
    months = []
    for i in range(12):
        start = (last_full - relativedelta(months=i)).replace(day=1)
        end = start.replace(day=calendar.monthrange(start.year, start.month)[1])
        months.append((start, end))
    return list(reversed(months))

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

def analyze_customer_journey(df: pd.DataFrame, grace_period_days: int = 90):
    """
    Analysiert Kundenverlauf und identifiziert True Churn vs. Reaktivierungen
    """
    # Kundenverlauf pro Kunde/Produkt aufbauen
    df_sorted = df.sort_values(['Kundennummer', 'ProductGroup', 'Beginn'])
    
    churn_events = []
    reactivations = []
    
    for (kunde, group), customer_df in df_sorted.groupby(['Kundennummer', 'ProductGroup']):
        customer_df = customer_df.reset_index(drop=True)
        
        for i, row in customer_df.iterrows():
            # Nur Verträge mit Enddatum betrachten
            if pd.isna(row['Ende']):
                continue
                
            end_date = row['Ende']
            
            # Prüfen ob es einen Folgevertrag gibt
            future_contracts = customer_df[
                (customer_df['Beginn'] > end_date) & 
                (customer_df.index > i)
            ]
            
            if len(future_contracts) > 0:
                # Nächster Vertrag gefunden
                next_start = future_contracts['Beginn'].min()
                gap_days = (next_start - end_date).days
                
                if gap_days <= grace_period_days:
                    # Reaktivierung (innerhalb Karenzzeit)
                    reactivations.append({
                        'Kundennummer': kunde,
                        'ProductGroup': group,
                        'Ende': end_date,
                        'NeuerBeginn': next_start,
                        'Luecke_Tage': gap_days,
                        'Typ': 'Reaktivierung'
                    })
                else:
                    # True Churn (Lücke zu groß)
                    churn_events.append({
                        'Kundennummer': kunde,
                        'ProductGroup': group,
                        'ChurnDatum': end_date,
                        'Typ': 'True Churn (lange Pause)'
                    })
            else:
                # Kein Folgevertrag = True Churn
                churn_events.append({
                    'Kundennummer': kunde,
                    'ProductGroup': group,
                    'ChurnDatum': end_date,
                    'Typ': 'True Churn (kein Folgevertrag)'
                })
    
    return pd.DataFrame(churn_events), pd.DataFrame(reactivations)

def calculate_true_churn_rates(df: pd.DataFrame, churn_events: pd.DataFrame, grace_period_days: int = 90):
    """
    Berechnet True Churn Raten basierend auf der Kundenverlaufs-Analyse
    """
    months = last_12_full_months(pd.Timestamp.today())
    records = []
    
    for group in RELEVANT_GROUPS:
        group_df = df[df['ProductGroup'] == group]
        group_churn = churn_events[churn_events['ProductGroup'] == group]
        
        if len(group_df) == 0:
            continue
            
        for start_ts, end_ts in months:
            # Aktive Kunden zu Monatsbeginn (basierend auf aktiven Verträgen)
            active_customers = set()
            for kunde, kunde_df in group_df.groupby('Kundennummer'):
                # Kunde ist aktiv wenn mindestens ein Vertrag aktiv ist
                kunde_active = kunde_df[
                    (kunde_df['Beginn'] < start_ts) & 
                    ((kunde_df['Ende'].isna()) | (kunde_df['Ende'] >= start_ts))
                ]
                if len(kunde_active) > 0:
                    active_customers.add(kunde)
            
            # True Churn Events in diesem Monat
            churned_customers = set(group_churn[
                (group_churn['ChurnDatum'] >= start_ts) & 
                (group_churn['ChurnDatum'] <= end_ts)
            ]['Kundennummer'].unique())
            
            # True Churn Rate berechnen
            num_active = len(active_customers)
            num_churned = len(churned_customers)
            true_churn_rate = (num_churned / num_active * 100) if num_active > 0 else 0.0
            
            records.append({
                'Monat': start_ts.strftime("%Y-%m"),
                'Gruppe': group,
                'AktiveKunden': num_active,
                'ChurnedKunden': num_churned,
                'TrueChurnRate (%)': round(true_churn_rate, 1)
            })
    
    return pd.DataFrame(records)

def churn_auswerten_v2(df: pd.DataFrame, grace_period_days: int = 90):
    """
    Erweiterte Churn-Analyse mit True Churn Berechnung
    """
    # Originale v1 Logik
    df = df[df['Abo'].astype(str).str.lower().isin(['ja','yes','true','1'])].copy()
    df['ProductGroup'] = df.apply(map_group, axis=1)
    df = df[df['ProductGroup'].isin(RELEVANT_GROUPS)]
    df['Beginn'] = pd.to_datetime(df['Beginn'], errors='coerce')
    df['Ende'] = pd.to_datetime(df['Ende'], errors='coerce')

    # V1 - Original Churn (Vertragsbasiert)
    months = last_12_full_months(pd.Timestamp.today())
    v1_records = []
    for group, gdf in df.groupby('ProductGroup'):
        for start_ts, end_ts in months:
            active = gdf[(gdf['Beginn'] < start_ts) & ((gdf['Ende'].isna()) | (gdf['Ende'] >= start_ts))]
            churned = gdf[(gdf['Ende'] >= start_ts) & (gdf['Ende'] <= end_ts)]
            rate = (len(churned) / len(active) * 100) if len(active) > 0 else 0.0
            v1_records.append({
                'Monat': start_ts.strftime("%Y-%m"), 
                'Gruppe': group, 
                'OriginalChurn (%)': round(rate, 1)
            })
    df_v1 = pd.DataFrame(v1_records)
    df_v1_pivot = df_v1.pivot(index='Monat', columns='Gruppe', values='OriginalChurn (%)').fillna(0)

    # V2 - True Churn Analyse
    churn_events, reactivations = analyze_customer_journey(df, grace_period_days)
    df_true_churn = calculate_true_churn_rates(df, churn_events, grace_period_days)
    df_v2_pivot = df_true_churn.pivot(index='Monat', columns='Gruppe', values='TrueChurnRate (%)').fillna(0)

    # Vergleichstabelle
    comparison_records = []
    for group in RELEVANT_GROUPS:
        if group in df_v1_pivot.columns and group in df_v2_pivot.columns:
            orig_avg = df_v1_pivot[group].mean()
            true_avg = df_v2_pivot[group].mean()
            improvement = orig_avg - true_avg
            
            comparison_records.append({
                'Produktgruppe': group,
                'Original Churn Ø (%)': round(orig_avg, 1),
                'True Churn Ø (%)': round(true_avg, 1),
                'Verbesserung (%)': round(improvement, 1)
            })
    
    df_comparison = pd.DataFrame(comparison_records)

    # Reaktivierungs-Statistiken
    if len(reactivations) > 0:
        react_stats = reactivations.groupby('ProductGroup').agg({
            'Kundennummer': 'count',
            'Luecke_Tage': 'mean'
        }).round(1).reset_index()
        react_stats.columns = ['Produktgruppe', 'Anzahl Reaktivierungen', 'Ø Pause (Tage)']
    else:
        react_stats = pd.DataFrame(columns=['Produktgruppe', 'Anzahl Reaktivierungen', 'Ø Pause (Tage)'])

    return {
        'v1_pivot': df_v1_pivot,
        'v2_pivot': df_v2_pivot, 
        'comparison': df_comparison,
        'reactivations': react_stats,
        'churn_events': churn_events,
        'reactivation_events': reactivations
    }

# Streamlit App
st.set_page_config(layout="wide")
st.title("Churn-Analyse v2 – EDELWEISS Digital")
st.markdown("**True Churn Analyse** mit Berücksichtigung von Kundenverlauf und Reaktivierungen")

# Sidebar für Einstellungen
st.sidebar.header("Einstellungen")
grace_period = st.sidebar.slider(
    "Karenzzeit für Reaktivierungen (Tage)", 
    min_value=30, 
    max_value=180, 
    value=90, 
    step=15,
    help="Kunden die innerhalb dieser Zeit das gleiche Produkt neu abschließen gelten nicht als Churn"
)

file = st.file_uploader("Lade eine Excel-Datei hoch", type=["xlsx"])

if file:
    try:
        df = pd.read_excel(file)
        
        # Prüfe ob erforderliche Spalten vorhanden sind
        required_cols = ['Abo', 'Produktkategorie', 'Produkt', 'Beginn', 'Ende', 'Kundennummer']
        missing_cols = [col for col in required_cols if col not in df.columns]
        
        if missing_cols:
            st.error(f"Fehlende Spalten: {', '.join(missing_cols)}")
        else:
            results = churn_auswerten_v2(df, grace_period)
            
            # Tabs für bessere Übersicht
            tab1, tab2, tab3, tab4, tab5 = st.tabs([
                "📊 Vergleich v1 vs v2", 
                "📈 True Churn Details", 
                "🔄 Reaktivierungen", 
                "📋 Original Churn (v1)",
                "🔍 Rohdaten"
            ])
            
            with tab1:
                st.subheader("Vergleich: Original vs. True Churn")
                st.dataframe(results['comparison'], use_container_width=True)
                
                col1, col2 = st.columns(2)
                with col1:
                    st.metric(
                        "Durchschnittliche Verbesserung", 
                        f"{results['comparison']['Verbesserung (%)'].mean():.1f}%",
                        help="Wie viel niedriger ist die True Churn Rate im Durchschnitt"
                    )
                with col2:
                    total_reactivations = results['reactivations']['Anzahl Reaktivierungen'].sum() if len(results['reactivations']) > 0 else 0
                    st.metric("Gesamt Reaktivierungen", f"{total_reactivations}")
            
            with tab2:
                st.subheader("True Churn Raten (letzte 12 Monate)")
                st.dataframe(results['v2_pivot'], use_container_width=True)
                
                if len(results['v2_pivot']) > 0:
                    st.line_chart(results['v2_pivot'])
            
            with tab3:
                st.subheader("Reaktivierungs-Statistiken")
                if len(results['reactivations']) > 0:
                    st.dataframe(results['reactivations'], use_container_width=True)
                    
                    # Details zu Reaktivierungen
                    if len(results['reactivation_events']) > 0:
                        st.subheader("Reaktivierungs-Details (Beispiele)")
                        st.dataframe(
                            results['reactivation_events'].head(20), 
                            use_container_width=True
                        )
                else:
                    st.info("Keine Reaktivierungen in den Daten gefunden.")
            
            with tab4:
                st.subheader("Original Churn Raten (Vertragsbasiert)")
                st.dataframe(results['v1_pivot'], use_container_width=True)
            
            with tab5:
                st.subheader("Churn Events (True Churn)")
                if len(results['churn_events']) > 0:
                    st.dataframe(results['churn_events'], use_container_width=True)
                else:
                    st.info("Keine True Churn Events gefunden.")
                
                st.subheader("Reaktivierungs Events")
                if len(results['reactivation_events']) > 0:
                    st.dataframe(results['reactivation_events'], use_container_width=True)
                else:
                    st.info("Keine Reaktivierungen gefunden.")

    except Exception as e:
        st.error(f"Fehler beim Verarbeiten der Datei: {e}")
        st.exception(e)

# Erklärung in der Sidebar
st.sidebar.markdown("---")
st.sidebar.markdown("### 📖 Erklärung")
st.sidebar.markdown("""
**Original Churn (v1):**
Jeder Vertragsabschluss wird separat betrachtet.

**True Churn (v2):**
Berücksichtigt Kundenverlauf:
- Reaktivierung ≤ 90 Tage = kein Churn
- Reaktivierung > 90 Tage = Churn
- Kein Folgevertrag = Churn

**Vorteil:** Realistischere Churn-Raten für Geschäftsentscheidungen.
""")
